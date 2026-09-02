"""
Standalone script to execute backtests and Monte Carlo analyses.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backtest.simulator import BacktestEngine
from backtest.results_analyzer import ResultsAnalyzer


def main():
    csv_file = ROOT_DIR / "data" / "historical" / "sample.csv"
    if not csv_file.exists():
        print(f"Dataset not found at {csv_file}. Generating now...")
        from scripts.generate_sample_data import main as gen_data
        gen_data()

    engine = BacktestEngine(initial_bankroll=100.0)
    df = engine.load_historical_data(str(csv_file))

    def kelly_strat(state, row):
        edge = row["true_prob"] - (1.0 / row["odds"])
        if edge > 0.02:
            b = row["odds"] - 1.0
            if b > 0:
                raw_k = (b * row["true_prob"] - (1.0 - row["true_prob"])) / b
                return max(0.0, state["bankroll"] * raw_k * 0.25)
        return 0.0

    print("Running Historical Strategy Backtest...")
    results = engine.run_backtest(kelly_strat, df)
    print(ResultsAnalyzer.format_summary_table(results))

    print("\nRunning Monte Carlo Risk Analysis (500 runs)...")
    mc = engine.monte_carlo_simulation(kelly_strat, df, n_simulations=500)
    print(f"Mean Final Bankroll    : ${mc['mean_final_bankroll']:.2f}")
    print(f"Median Final Bankroll  : ${mc['median_final_bankroll']:.2f}")
    print(f"Probability of Profit  : {mc['probability_of_profit']*100:.1f}%")
    print(f"Probability of Ruin    : {mc['probability_of_ruin']*100:.1f}%")


if __name__ == "__main__":
    main()
