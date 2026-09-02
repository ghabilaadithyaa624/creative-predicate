#!/usr/bin/env python3
"""
Autonomous Trading Agent Framework - CLI & Orchestrator
"""
import asyncio
import sys
from pathlib import Path

import click
import yaml
from loguru import logger

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.agents.polymarket_agent import PolymarketAgent
from backend.agents.sports_agent import SportsAgent
from backend.agents.survival_manager import SurvivalRule
from backend.backtest.historical_data import HistoricalDataLoader
from backend.backtest.results_analyzer import ResultsAnalyzer
from backend.backtest.simulator import BacktestEngine
from backend.config.settings import get_settings
from backend.trading.paper_engine import PaperTradingEngine, SurvivalMode
from backend.trading.settlement import SettlementEngine


@click.group()
def cli():
    """Autonomous Trading Agent & Paper Trading Simulation CLI."""
    pass


@cli.command()
@click.option("--name", default="AlphaBot", help="Agent name")
@click.option("--bankroll", default=100.0, help="Initial bankroll ($)")
@click.option(
    "--mode",
    type=click.Choice(["aggressive", "conservative", "terminal"], case_sensitive=False),
    default="aggressive",
    help="Survival circuit breaker mode",
)
@click.option("--rounds", default=5, help="Number of autonomous perception/trade rounds to execute")
@click.option("--config", type=click.Path(exists=True), default=None, help="Path to custom config YAML")
def run(name: str, bankroll: float, mode: str, rounds: int, config: str):
    """Start and run an autonomous trading agent for N rounds."""
    settings = get_settings(config)
    settings.ensure_directories()

    mode_map = {
        "aggressive": SurvivalMode.AGGRESSIVE,
        "conservative": SurvivalMode.CONSERVATIVE,
        "terminal": SurvivalMode.TERMINAL,
    }
    survival_mode = mode_map.get(mode.lower(), SurvivalMode.AGGRESSIVE)

    engine = PaperTradingEngine(initial_bankroll=bankroll)
    settlement = SettlementEngine(engine)

    agent = PolymarketAgent(
        name=name,
        trading_engine=engine,
        initial_bankroll=bankroll,
        survival_mode=survival_mode,
        kelly_fraction=settings.risk.kelly_fraction,
        min_edge=settings.risk.min_edge,
    )

    click.secho("\n=======================================================", fg="cyan", bold=True)
    click.secho(f"  STARTING AUTONOMOUS AGENT: {name}", fg="cyan", bold=True)
    click.secho(f"  Mode: {mode.upper()} | Bankroll: ${bankroll:.2f} | Rounds: {rounds}", fg="cyan")
    click.secho("=======================================================\n", fg="cyan", bold=True)

    async def _execute_rounds():
        for r in range(1, rounds + 1):
            click.secho(f"\n--- [Round {r}/{rounds}] ---", fg="yellow", bold=True)
            if not agent.paper_state.is_alive:
                click.secho(f"Agent '{name}' is TERMINATED: {agent.paper_state.kill_reason}", fg="red", bold=True)
                break

            # 1. Run perception -> reason -> act cycle
            await agent.run_cycle()

            # 2. Simulate settlement of open bets
            settlement.auto_simulate_pending_resolutions()

            # 3. Print status metrics
            m = agent.paper_state.calculate_metrics()
            status_color = "green" if m["is_alive"] else "red"
            click.secho(
                f"Bankroll: ${m['current_bankroll']:.2f} | PnL: ${m['total_profit']:+.2f} ({m['roi_percent']:+.1f}%) | "
                f"Bets: {m['total_bets']} (Win Rate: {m['win_rate']*100:.1f}%) | Status: {m['is_alive']}",
                fg=status_color,
            )

        click.secho("\n=======================================================", fg="cyan", bold=True)
        click.secho("  FINAL PERFORMANCE REPORT", fg="cyan", bold=True)
        click.secho("=======================================================", fg="cyan", bold=True)
        leaderboard = engine.get_leaderboard()
        for rank, res in enumerate(leaderboard, 1):
            st = "ALIVE" if res["is_alive"] else f"DEAD ({res['kill_reason']})"
            click.echo(
                f"{rank}. {res['name']}: ${res['current_bankroll']:.2f} "
                f"(${res['total_profit']:+.2f} / {res['roi_percent']:+.1f}%) - {st}"
            )

    asyncio.run(_execute_rounds())


@cli.command()
@click.option("--rounds", default=5, help="Number of simulation rounds")
def simulate_all(rounds: int):
    """Run a multi-agent tournament across different survival styles."""
    engine = PaperTradingEngine(initial_bankroll=100.0)
    settlement = SettlementEngine(engine)

    agents = [
        PolymarketAgent("Aggressive_Kelly", engine, 100.0, SurvivalMode.AGGRESSIVE, kelly_fraction=0.40),
        PolymarketAgent("Standard_Fractional", engine, 100.0, SurvivalMode.AGGRESSIVE, kelly_fraction=0.25),
        SportsAgent("Conservative_Sports", engine, 100.0, SurvivalMode.CONSERVATIVE, kelly_fraction=0.15),
        PolymarketAgent("Terminal_ZeroTolerance", engine, 100.0, SurvivalMode.TERMINAL, kelly_fraction=0.10),
    ]

    click.secho("\n[*] RUNNING MULTI-AGENT PAPER TRADING TOURNAMENT\n", fg="magenta", bold=True)

    async def _run_multi():
        for r in range(1, rounds + 1):
            click.secho(f"\n>>> ROUND {r}/{rounds} <<<", fg="yellow", bold=True)
            for ag in agents:
                if ag.paper_state.is_alive:
                    await ag.run_cycle()
            settlement.auto_simulate_pending_resolutions()

        click.secho("\n" + "=" * 60, fg="magenta")
        click.secho("               FINAL LEADERBOARD               ", fg="magenta", bold=True)
        click.secho("=" * 60, fg="magenta")
        for rank, res in enumerate(engine.get_leaderboard(), 1):
            status = "ALIVE" if res["is_alive"] else f"DEAD ({res['kill_reason']})"
            click.echo(
                f"{rank}. {res['name']:<24} | Bankroll: ${res['current_bankroll']:>6.2f} "
                f"| PnL: ${res['total_profit']:>+6.2f} ({res['roi_percent']:>+5.1f}%) | {status}"
            )

    asyncio.run(_run_multi())


@cli.command()
@click.option("--data", default=None, help="Path to historical odds CSV")
@click.option("--records", default=300, help="Number of records to generate if data path not given")
@click.option("--monte-carlo", is_flag=True, help="Run Monte Carlo bootstrap simulation")
def backtest(data: str, records: int, monte_carlo: bool):
    """Run historical backtest and Monte Carlo simulation."""
    b_engine = BacktestEngine(initial_bankroll=100.0)

    if data and Path(data).exists():
        df = b_engine.load_historical_data(data)
        click.echo(f"Loaded {len(df)} records from {data}")
    else:
        sample_path = ROOT_DIR / "data" / "historical" / "sample.csv"
        if sample_path.exists():
            df = b_engine.load_historical_data(str(sample_path))
        else:
            df = HistoricalDataLoader.generate_synthetic_data(num_records=records)

    def strategy(state, row):
        edge = row["true_prob"] - (1.0 / row["odds"])
        if edge > 0.02:
            b = row["odds"] - 1.0
            if b > 0:
                raw_k = (b * row["true_prob"] - (1.0 - row["true_prob"])) / b
                return max(0.0, min(state["bankroll"] * raw_k * 0.25, state["bankroll"] * 0.08))
        return 0.0

    if monte_carlo:
        click.secho("\n[*] Running Monte Carlo Simulation (500 iterations)...", fg="cyan", bold=True)
        mc = b_engine.monte_carlo_simulation(strategy, df, n_simulations=500)
        click.echo(f"  Mean Final Bankroll     : ${mc['mean_final_bankroll']:.2f}")
        click.echo(f"  Median Final Bankroll   : ${mc['median_final_bankroll']:.2f}")
        click.echo(f"  Std Deviation           : ${mc['std_final_bankroll']:.2f}")
        click.echo(f"  5th - 95th Percentiles  : ${mc['percentile_5th']:.2f} - ${mc['percentile_95th']:.2f}")
        click.echo(f"  Probability of Profit   : {mc['probability_of_profit']*100:.1f}%")
        click.echo(f"  Probability of Ruin     : {mc['probability_of_ruin']*100:.1f}%")
    else:
        click.secho("\n[*] Running Historical Walk-Forward Backtest...", fg="green", bold=True)
        res = b_engine.run_backtest(strategy, df)
        click.echo(ResultsAnalyzer.format_summary_table(res))


@cli.command()
@click.option("--port", default=8501, help="Port for Streamlit dashboard")
def dashboard(port: int):
    """Launch the interactive Streamlit monitoring dashboard."""
    import subprocess
    app_path = ROOT_DIR / "frontend" / "dashboard" / "app.py"
    click.secho(f"\n[*] Launching Streamlit Dashboard on port {port}...", fg="green", bold=True)
    subprocess.run(["streamlit", "run", str(app_path), "--server.port", str(port)])


@cli.command()
@click.option("--port", default=8000, help="Port for FastAPI backend")
@click.option("--host", default="0.0.0.0", help="Host address")
def api(port: int, host: str):
    """Launch FastAPI backend server with REST & WebSocket endpoints."""
    import uvicorn

    from backend.api.routes import create_app
    engine = PaperTradingEngine(initial_bankroll=100.0)
    app = create_app(engine)
    click.secho(f"\n[*] Launching FastAPI Server on http://{host}:{port}...", fg="cyan", bold=True)
    uvicorn.run(app, host=host, port=port)


@cli.command()
def init():
    """Initialize project folders, sample configs, and database."""
    settings = get_settings()
    settings.ensure_directories()

    # Generate initial sample dataset
    sample_file = settings.data_dir / "historical" / "sample.csv"
    if not sample_file.exists():
        df = HistoricalDataLoader.generate_synthetic_data(num_records=500)
        df.to_csv(sample_file, index=False)
        click.echo(f" Generated sample historical dataset at {sample_file}")

    click.secho("\n[+] Autonomous Trading Framework initialized successfully!", fg="green", bold=True)


if __name__ == "__main__":
    cli()
