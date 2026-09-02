"""
Unit tests for historical backtester and Monte Carlo simulator.
"""
from backtest.historical_data import HistoricalDataLoader
from backtest.simulator import BacktestEngine


def test_backtest_execution():
    engine = BacktestEngine(initial_bankroll=100.0)
    df = HistoricalDataLoader.generate_synthetic_data(num_records=50, base_edge_mean=0.04)

    def dummy_strat(state, row):
        return 2.0  # Constant 2$ stake

    results = engine.run_backtest(dummy_strat, df)
    assert results["total_bets"] > 0
    assert "win_rate" in results
    assert "final_bankroll" in results
    assert "sharpe_ratio" in results


def test_monte_carlo_execution():
    engine = BacktestEngine(initial_bankroll=100.0)
    df = HistoricalDataLoader.generate_synthetic_data(num_records=40)

    def dummy_strat(state, row):
        return 2.0

    mc = engine.monte_carlo_simulation(dummy_strat, df, n_simulations=20)
    assert mc["n_simulations"] == 20
    assert "mean_final_bankroll" in mc
    assert "probability_of_profit" in mc
