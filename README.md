# Creative Predicate

A **paper-trading research sandbox** for prediction-market and sports-betting strategy evaluation.

It simulates autonomous agents that estimate probabilities, size positions with fractional Kelly, and settle bets against a ledger with circuit-breaker risk controls. Everything runs on simulated capital.

> ### Read this before interpreting any number
>
> - **It cannot place a real order.** There is no broker or exchange integration anywhere in the codebase.
> - **The market feed is usually synthetic.** The live Polymarket API is attempted first, but when it is unreachable the system falls back to six hard-coded markets. Synthetic markets are tagged `source="polymarket_simulated"`.
> - **Backtest and Monte Carlo figures describe *simulated* outcomes** under assumptions you supply. They are not evidence of edge in a live market. See [Interpreting results](#interpreting-results).

---

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Running everything](#running-everything)
  - [CLI](#1-cli)
  - [REST API + WebSocket](#2-rest-api--websocket)
  - [Dashboard](#3-dashboard)
  - [Docker](#4-docker)
- [Configuration](#configuration)
- [Interpreting results](#interpreting-results)
- [Repository layout](#repository-layout)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Known gaps](#known-gaps)

---

## Requirements

- **Python 3.10, 3.11 or 3.12** (CI tests all three)
- `pip` and `venv`
- Optional: Docker with Compose v2

---

## Installation

```bash
git clone https://github.com/ghabilaadithyaa624/creative-predicate.git
cd creative-predicate

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # core runtime + test tooling
```

The core install is deliberately small. Every optional stack is guarded by `try/except ImportError`, and CI runs the whole suite core-only to keep it that way.

| Extra | Install | Enables |
| :--- | :--- | :--- |
| `api` | `pip install -e ".[api]"` | FastAPI REST + WebSocket telemetry |
| `dashboard` | `pip install -e ".[dashboard]"` | Streamlit monitor |
| `ml` | `pip install -e ".[ml]"` | scikit-learn ensembles, PyTorch nets, PPO |
| `vision` | `pip install -e ".[vision]"` | Playwright + OCR browser agent |
| `memory` | `pip install -e ".[memory]"` | Chroma vector store, Redis, SQLAlchemy |
| `dev` | `pip install -e ".[dev]"` | pytest, coverage, ruff |

Everything at once:

```bash
pip install -e ".[api,dashboard,ml,vision,memory,dev]"
# or: make install-all
```

---

## Quick start

```bash
python main.py init          # create data/, logs/ and a sample dataset
python main.py backtest      # deterministic walk-forward backtest
pytest tests/                # 63 tests
```

Installing the package also gives you a `creative-predicate` console script, identical to `python main.py`:

```bash
creative-predicate backtest
```

Both forms are used interchangeably below.

---

## Running everything

### 1. CLI

#### `init` — set up the workspace

```bash
python main.py init
```

Creates `data/`, `data/historical/`, `data/cache/`, `logs/`, `models/`, `results/` and generates `data/historical/sample.csv` (500 synthetic records) if absent. Safe to re-run.

#### `backtest` — evaluate a strategy on historical data

```bash
python main.py backtest                          # deterministic walk-forward
python main.py backtest --monte-carlo            # bootstrap distribution
python main.py backtest --data path/to/odds.csv  # your own dataset
python main.py backtest --records 1000           # larger synthetic set
```

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `--data PATH` | `data/historical/sample.csv` | Historical odds CSV |
| `--records N` | `300` | Rows to generate when no data file is given |
| `--monte-carlo` | off | Run 500 bootstrap iterations instead of one pass |

Deterministic run:

```
========================================
        BACKTEST RESULTS SUMMARY
========================================
Initial Bankroll   : $100.00
Final Bankroll     : $166.14
Total Profit / Loss: $+66.14
ROI (%)            : +66.14%
Total Trades       : 208
Win Rate (%)       : 52.9%
Profit Factor      : 1.18
Sharpe Ratio       : 1.30
Sortino Ratio      : 3.49
Max Drawdown (%)   : 31.9%
========================================
```

Monte Carlo (values vary per run — that is the point):

```
[*] Running Monte Carlo Simulation (500 iterations)...
  Mean Final Bankroll     : $235.58
  Median Final Bankroll   : $210.25
  Std Deviation           : $111.06
  5th - 95th Percentiles  : $99.05 - $436.02
  Probability of Profit   : 94.6%
  Probability of Ruin     : 0.0%
```

**A custom CSV needs these columns:** `timestamp, event, category, selection, odds, true_prob, implied_prob, result, volume`. `odds` is decimal, `true_prob` is the ground-truth win probability, `result` is a boolean.

#### `run` — single autonomous agent

```bash
python main.py run --name AlphaBot --bankroll 100 --mode aggressive --rounds 10
```

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `--name TEXT` | `AlphaBot` | Agent name |
| `--bankroll FLOAT` | `100.0` | Starting bankroll in dollars |
| `--mode` | `aggressive` | `aggressive` (die below 50%), `conservative` (80%), `terminal` (100%) |
| `--rounds INTEGER` | `5` | Perceive → reason → act cycles |
| `--config PATH` | `backend/config/agents.yaml` | Custom config YAML |

> **Expect zero bets.** Against the synthetic feed the largest genuine edge is about **0.68%**, below the 2% `min_edge` floor, so the agent correctly declines to trade. This is the honest result, not a bug — see [Why the agent places no bets](#why-the-agent-places-no-bets).

#### `simulate-all` — multi-agent tournament

```bash
python main.py simulate-all --rounds 5
```

Runs four agents with different survival styles and Kelly fractions against a shared engine, then prints a leaderboard.

---

### 2. REST API + WebSocket

```bash
pip install -e ".[api]"
python main.py api --port 8000 --host 0.0.0.0
```

Interactive docs at **http://localhost:8000/docs**.

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Health check |
| `GET` | `/agents` | Leaderboard of all agents |
| `GET` | `/agents/{name}` | Metrics, bets and balance history |
| `POST` | `/agents` | Create an agent |
| `GET` | `/markets` | Current market feed |
| `POST` | `/bets/place` | Place a paper bet |
| `POST` | `/bets/settle` | Settle a bet |
| `POST` | `/backtest/run` | Run a backtest |
| `WS` | `/ws/telemetry` | Live `agent_created` / `bet_placed` / `bet_settled` events |

A complete worked session:

```bash
# 1. Create an agent
curl -X POST localhost:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"DocBot","initial_bankroll":100.0,"survival_mode":"aggressive"}'

# 2. Place a bet -> returns {"id":"bet_4a6067ef", ...}
curl -X POST localhost:8000/bets/place \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"DocBot","market":"polymarket","event":"Demo Event",
       "selection":"Yes","odds":2.5,"stake":10.0,"expected_value":0.08}'

# 3. Settle it as a win
curl -X POST localhost:8000/bets/settle \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"DocBot","bet_id":"bet_4a6067ef","won":true}'

# 4. Inspect: bankroll 100 -> 115, pnl +15
curl localhost:8000/agents/DocBot
```

Subscribing to live telemetry:

```python
import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8000/ws/telemetry") as ws:
        while True:
            print(json.loads(await ws.recv()))

asyncio.run(main())
```

```
{"event": "agent_created", "data": {...}}
{"event": "bet_placed",    "data": {...}}
{"event": "bet_settled",   "data": {...}}
```

**CORS.** By default the API sends `allow_origins=["*"]` *without* credentials. To allow a credentialed browser client, name the origins explicitly — a wildcard combined with credentials is rejected by browsers:

```bash
CORS_ALLOW_ORIGINS="http://localhost:3000,https://myapp.example" \
  python main.py api --port 8000
```

---

### 3. Dashboard

```bash
pip install -e ".[dashboard]"
python main.py dashboard --port 8501
# or: streamlit run frontend/dashboard/app.py
```

Opens at **http://localhost:8501** with a live monitor, backtest lab and market analyzer.

> The dashboard talks to the trading engine **in-process**. It runs its own engine instance and will not show agents created through the REST API. See [Known gaps](#known-gaps).

---

### 4. Docker

```bash
docker compose up agent        # headless agent simulation
docker compose up api          # API on :8000
docker compose up dashboard    # dashboard on :8501
```

The image runs as an unprivileged user and installs only the core runtime; the `api` and `dashboard` services layer their extras on at start-up. To build and run a single agent directly:

```bash
docker build -t creative-predicate .
docker run --rm creative-predicate
```

---

## Configuration

Edit `backend/config/agents.yaml`, or pass `--config path/to/your.yaml` to `run`:

```yaml
agent:
  name: "AlphaBot"
  initial_bankroll: 100.0
  survival_mode: "aggressive"    # aggressive | conservative | terminal
  tick_interval_seconds: 60.0
  max_concurrent_bets: 5
  markets: ["polymarket", "sports"]

risk:
  kelly_fraction: 0.25           # fraction of full Kelly to stake
  min_edge: 0.02                 # skip anything below a 2% edge
  max_bet_pct: 0.05              # cap any single bet at 5% of bankroll
  max_drawdown_pct: 0.30
  max_consecutive_losses: 10
  enable_circuit_breaker: true
```

**Survival modes** terminate an agent when equity falls below a share of its starting bankroll: `aggressive` 50%, `conservative` 80%, `terminal` 100% (dies on any net loss).

| Environment variable | Default | Purpose |
| :--- | :--- | :--- |
| `CORS_ALLOW_ORIGINS` | unset | Comma-separated origins allowed to send credentials |

---

## Interpreting results

Two knobs decide whether a simulated number means anything.

### `edge_realisation` — how much of the agent's claimed edge is real

```python
from backend.trading.settlement import SettlementEngine

settlement.auto_simulate_pending_resolutions(edge_realisation=1.0)   # forecast perfectly correct
settlement.auto_simulate_pending_resolutions(edge_realisation=0.0)   # forecast worthless; market is right
settlement.auto_simulate_pending_resolutions(ground_truth={"Event": 0.35})  # score against reality
```

At `1.0` you are measuring *"what if my model is exactly right?"* — an upper bound, not a forecast. Sweep it toward `0.0` to see how fast the strategy decays as the model degrades. **A strategy that only profits at `edge_realisation=1.0` has no margin for error.**

### `resample_outcomes` — replay or redraw

Monte Carlo forces this on. Replaying a fixed `result` column in shuffled order produces zero variance and a meaningless 0% ruin estimate.

### Why the agent places no bets

`python main.py run` normally ends with an empty leaderboard. That is correct.

Against the synthetic feed the largest genuine edge is roughly **0.68%**, under the 2% `min_edge` floor. Earlier versions bet constantly only because `estimate_fair_probability` fabricated a ±2.5% edge from the parity of `int(volume_24h)` — pure noise. That was removed. Producing real activity needs a real data source, not a lower threshold.

To watch the machinery work end to end regardless, use the backtest commands, which run against a dataset with known ground truth.

---

## Repository layout

```
backend/     trading engine, agents, analysis, risk, backtesting, API
frontend/    presentation layer (Streamlit dashboard)
scripts/     one-off utilities
tests/       test suite
main.py      CLI entry point
```

The dependency runs one way: `frontend` imports `backend`, never the reverse. A test enforces this (`tests/unit/test_layout.py`), so the API stays importable without Streamlit installed.

```python
from backend.trading.paper_engine import PaperTradingEngine
from backend.analysis.scraper import MarketScraper
```

### What actually runs

| Module | Role |
| :--- | :--- |
| [`backend/trading/paper_engine.py`](backend/trading/paper_engine.py) | The ledger. Bets, stake locking, settlement, equity, drawdown, survival circuit breakers. |
| [`backend/trading/settlement.py`](backend/trading/settlement.py) | Resolves open bets against registered outcomes or a seeded simulation. |
| [`backend/trading/bet_manager.py`](backend/trading/bet_manager.py) | Fractional Kelly sizing and portfolio exposure caps. |
| [`backend/risk/advanced_position_sizing.py`](backend/risk/advanced_position_sizing.py) | Optimal *f*, uncertainty-adjusted sizing. |
| [`backend/analysis/probability_models.py`](backend/analysis/probability_models.py) | Fair-probability estimation (favourite–longshot correction). |
| [`backend/analysis/odds_analyzer.py`](backend/analysis/odds_analyzer.py) | Odds conversion, vig removal, arbitrage detection. |
| [`backend/analysis/scraper.py`](backend/analysis/scraper.py) | Polymarket Gamma API with synthetic fallback. |
| [`backend/backtest/simulator.py`](backend/backtest/simulator.py) | Walk-forward backtest and bootstrap Monte Carlo. |
| [`backend/agents/`](backend/agents/) | Perceive → reason → act loop for prediction-market and sports agents. |
| [`backend/api/routes.py`](backend/api/routes.py) | REST endpoints and `/ws/telemetry` live event stream. |
| [`frontend/dashboard/app.py`](frontend/dashboard/app.py) | Streamlit monitor, backtest lab, market analyzer. |

### Experimental / not wired in

Self-contained implementations that **no entry point currently calls**, exercised by tests only. Research spikes, not features:

`backend/quantum/` (QAOA portfolio optimizer, VQC) · `backend/neuromorphic/` (LIF neurons, echo-state reservoir) · `backend/federated/` (Shamir secret sharing, FedAvg) · `backend/blockchain/` (stake-weighted + BFT voting) · `backend/swarm/` (role-based consensus) · `backend/reinforcement_learning/` (PPO trader) · `backend/vision/` (browser/OCR agent)

---

## Development

```bash
make install       # core + dev tooling
make test          # pytest tests/ -v
make lint          # ruff check .
make fmt           # ruff check . --fix
make backtest      # deterministic backtest
make montecarlo    # Monte Carlo backtest
make help          # list every target
```

Running the suite directly:

```bash
pytest tests/ -v
pytest tests/ --cov=. --cov-report=term-missing
pytest tests/unit/test_settlement.py -v      # one file
python tests/run_tests.py                    # legacy standalone runner
```

CI runs on Python 3.10/3.11/3.12: ruff, the pytest suite, the legacy runner, a CLI smoke test over every documented command, and a frontend import check. The test install is **core-only by design**, which is what keeps the optional-import guards honest.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'backend'`**
Install the package in editable mode from the repo root: `pip install -e ".[dev]"`.

**`ModuleNotFoundError: No module named 'streamlit'` / `'fastapi'` / `'torch'`**
Those live in extras. Install the one you need: `pip install -e ".[dashboard]"`, `".[api]"`, `".[ml]"`.

**`Live Polymarket API query failed: ... SSLError`**
Expected on a network without access to `gamma-api.polymarket.com`. The system logs a warning and falls back to the synthetic feed. To fail loudly instead of falling back:

```python
MarketScraper().scrape_polymarket(allow_synthetic_fallback=False)   # -> []
```

**The agent places no bets**
Working as intended — see [Why the agent places no bets](#why-the-agent-places-no-bets).

**Monte Carlo shows `Probability of Ruin: 0.0%`**
Legitimate for a well-sized Kelly strategy on this dataset. It is only suspicious if `Std Deviation` is also `$0.00`, which indicated an old bug where outcomes were replayed rather than redrawn.

**Dashboard does not show agents created via the API**
Known limitation. Each surface builds its own in-memory engine; there is no shared persistence layer yet.

**Port already in use**
Pass a different port: `python main.py api --port 8080` or `python main.py dashboard --port 8502`.

---

## Known gaps

Honest inventory of what is still missing:

- **Perception is mostly synthetic.** The live API path works but usually falls back to six hard-coded markets. Synthetic markets are tagged `source="polymarket_simulated"`; pass `allow_synthetic_fallback=False` if you need certainty that prices are real.
- **The 2% edge floor is rarely cleared.** Against correctly-parsed live prices the model yields directionally sensible but small edges (~1.5%), so the agent usually declines to trade. The probability model, not the data, is now the binding constraint.
- **No persistence.** `scripts/setup_db.py` creates SQLite tables nothing writes to. CLI, API and dashboard each build a separate in-memory engine and cannot see each other's agents.
- **The probability model is thin.** A hand-tuned favourite–longshot correction with two magic coefficients, not a fitted model.
- **~1,000 lines are unwired** (see *Experimental* above).

---

## License

MIT
