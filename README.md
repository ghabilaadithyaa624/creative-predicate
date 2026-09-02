# Creative Predicate

A **paper-trading research sandbox** for prediction-market and sports-betting strategy evaluation.

It simulates autonomous agents that estimate probabilities, size positions with fractional Kelly, and settle bets against a ledger with circuit-breaker risk controls. Everything runs on simulated capital.

> **This is a research sandbox, not a trading system.**
> - It never connects to a broker or exchange and cannot place a real order.
> - The perception layer falls back to a small **synthetic market feed** when the Polymarket API is unreachable, which is most of the time.
> - Backtest and Monte Carlo figures describe *simulated* outcomes under assumptions you supply. They are not evidence of edge in a live market.

---

## Quick start

```bash
pip install -e ".[dev]"     # core runtime + test tooling
python main.py init         # create data/logs dirs and a sample dataset

python main.py backtest              # deterministic walk-forward
python main.py backtest --monte-carlo # bootstrap distribution
python main.py simulate-all --rounds 5
pytest tests/                        # 39 tests
```

Installing the package also provides a `creative-predicate` console script equivalent to `python main.py`.

### Optional extras

The core install deliberately excludes heavy dependencies. Every optional stack is guarded by `try/except ImportError`, and CI runs the suite core-only to keep it that way.

| Extra | Install | Enables |
| :--- | :--- | :--- |
| `api` | `pip install -e ".[api]"` | FastAPI REST + WebSocket telemetry |
| `dashboard` | `pip install -e ".[dashboard]"` | Streamlit monitor |
| `ml` | `pip install -e ".[ml]"` | scikit-learn ensembles, PyTorch nets, PPO |
| `vision` | `pip install -e ".[vision]"` | Playwright + OCR browser agent |
| `memory` | `pip install -e ".[memory]"` | Chroma vector store, Redis, SQLAlchemy |

---

## Repository layout

```
backend/     trading engine, agents, analysis, risk, backtesting, API
frontend/    presentation layer (Streamlit dashboard)
scripts/     one-off utilities
tests/       test suite
main.py      CLI entry point
```

The dependency runs one way: `frontend` imports `backend`, never the reverse.
A test enforces this (`tests/unit/test_layout.py`), so the API stays importable
without Streamlit installed.

Imports use the full path, e.g.:

```python
from backend.trading.paper_engine import PaperTradingEngine
from backend.analysis.scraper import MarketScraper
```

---

## What actually runs

These modules are wired into the CLI, the agents, and the API. They are the working system.

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

These are self-contained implementations that **no entry point currently calls**. They are exercised by tests only. Treat them as research spikes, not features:

`backend/quantum/` (QAOA portfolio optimizer, VQC) · `backend/neuromorphic/` (LIF neurons, echo-state reservoir) · `backend/federated/` (Shamir secret sharing, FedAvg) · `backend/blockchain/` (stake-weighted + BFT voting) · `backend/swarm/` (role-based consensus) · `backend/reinforcement_learning/` (PPO trader) · `backend/vision/` (browser/OCR agent)

---

## Understanding the simulation

Two knobs determine whether simulated results mean anything.

**`edge_realisation`** (settlement) controls how much of an agent's claimed edge is real:

```python
settlement.auto_simulate_pending_resolutions(edge_realisation=1.0)  # forecast is perfectly correct
settlement.auto_simulate_pending_resolutions(edge_realisation=0.0)  # forecast has no value; market is right
settlement.auto_simulate_pending_resolutions(ground_truth={"Event": 0.35})  # score against reality
```

At `1.0` you are measuring *"what if my model is exactly right?"* — an upper bound, not a forecast. Sweeping it down toward `0.0` shows how fast the strategy decays as the model degrades. **A strategy that only profits at `edge_realisation=1.0` has no margin for error.**

**`resample_outcomes`** (backtest) controls whether outcomes are replayed or redrawn. Monte Carlo forces it on; a fixed `result` column replayed in shuffled order produces zero variance and a meaningless 0% ruin estimate.

### Why the default agent run places no bets

`python main.py run` typically finishes with an empty leaderboard. This is correct. Against the synthetic feed the largest genuine edge is about **0.68%**, below the 2% `min_edge` floor, so the agent declines to trade.

Earlier versions bet constantly because `estimate_fair_probability` returned a fabricated ±2.5% edge based on whether `int(volume_24h)` was even. That noise was removed. Producing real activity requires a real data source, not a looser threshold.

---

## Development

```bash
make install    # core + dev
make test
make lint
make fmt
```

CI runs on Python 3.10/3.11/3.12: lint, the pytest suite, the legacy `tests/run_tests.py` runner, and a CLI smoke test over every documented command.

## Known gaps

Honest inventory of what is still missing:

- **Perception is mostly synthetic.** The live API path works but usually falls back to six hard-coded markets when the network is unavailable. Synthetic markets are tagged `source="polymarket_simulated"`; pass `allow_synthetic_fallback=False` to `scrape_polymarket()` if you need certainty that prices are real.
- **The 2% edge floor is rarely cleared.** Against correctly-parsed live prices the model produces directionally sensible but small edges (~1.5%), so the agent usually declines to trade. The probability model, not the data, is now the binding constraint.
- **No persistence.** `scripts/setup_db.py` creates SQLite tables nothing writes to. CLI, API and dashboard each build a separate in-memory engine and cannot see each other's agents.
- **The probability model is thin.** A hand-tuned favourite–longshot correction, not a fitted model.
- **~1,000 lines are unwired** (see *Experimental* above).

## License

MIT
