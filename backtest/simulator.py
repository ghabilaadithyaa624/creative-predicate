"""
Historical backtesting and Monte Carlo simulation engine.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
import numpy as np
import pandas as pd
from loguru import logger
from trading.performance import PerformanceAnalyzer


@dataclass
class BacktestResult:
    initial_bankroll: float
    final_bankroll: float
    total_bets: int
    win_rate: float
    total_profit: float
    roi_percent: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    bets: List[Dict[str, Any]]
    equity_curve: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_bankroll": self.initial_bankroll,
            "final_bankroll": round(self.final_bankroll, 2),
            "total_bets": self.total_bets,
            "win_rate": round(self.win_rate, 4),
            "total_profit": round(self.total_profit, 2),
            "roi_percent": round(self.roi_percent, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "profit_factor": round(self.profit_factor, 2),
        }


class BacktestEngine:
    """
    Simulates trading strategies across historical time-series data.
    """

    def __init__(self, initial_bankroll: float = 100.0):
        self.initial_bankroll = initial_bankroll

    def load_historical_data(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def run_backtest(
        self,
        strategy: Callable[[Dict[str, Any], pd.Series], float],
        data: pd.DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Executes a backtest given a strategy sizing function:
        strategy(state_dict, row_series) -> bet_stake (float)
        """
        df = data.copy()
        if start_date and "timestamp" in df.columns:
            df = df[df["timestamp"] >= start_date]
        if end_date and "timestamp" in df.columns:
            df = df[df["timestamp"] <= end_date]

        bankroll = self.initial_bankroll
        peak_bankroll = bankroll
        bets_record: List[Dict[str, Any]] = []
        equity_curve: List[float] = [bankroll]

        for idx, row in df.iterrows():
            if bankroll <= 1.0:
                # Agent ruined
                break

            state = {
                "bankroll": bankroll,
                "peak_bankroll": peak_bankroll,
                "bets_count": len(bets_record),
            }

            stake = strategy(state, row)

            if stake > 0 and stake <= bankroll:
                bankroll -= stake
                won = bool(row["result"]) if "result" in row else (np.random.random() < row.get("true_prob", 0.5))
                odds = float(row["odds"])

                if won:
                    payout = stake * odds
                    bankroll += payout
                    pnl = payout - stake
                else:
                    pnl = -stake

                if bankroll > peak_bankroll:
                    peak_bankroll = bankroll

                bets_record.append({
                    "timestamp": row.get("timestamp"),
                    "event": row.get("event", f"Event #{idx}"),
                    "odds": odds,
                    "stake": stake,
                    "won": won,
                    "pnl": pnl,
                    "bankroll_after": round(bankroll, 2),
                })
                equity_curve.append(bankroll)

        metrics = PerformanceAnalyzer.compute_all_metrics(
            initial_bankroll=self.initial_bankroll,
            final_bankroll=bankroll,
            bets=bets_record,
        )

        return {
            **metrics,
            "final_bankroll": round(bankroll, 2),
            "bets": bets_record,
            "equity_curve": equity_curve,
        }

    def monte_carlo_simulation(
        self,
        strategy: Callable[[Dict[str, Any], pd.Series], float],
        data: pd.DataFrame,
        n_simulations: int = 500,
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo iterations by bootstrap-resampling the historical sequence.
        """
        final_balances = []
        ruin_count = 0
        profit_count = 0

        for _ in range(n_simulations):
            shuffled_df = data.sample(frac=1.0).reset_index(drop=True)
            res = self.run_backtest(strategy, shuffled_df)
            final_bal = res["final_bankroll"]
            final_balances.append(final_bal)

            if final_bal < (self.initial_bankroll * 0.50):
                ruin_count += 1
            if final_bal > self.initial_bankroll:
                profit_count += 1

        arr = np.array(final_balances)
        return {
            "n_simulations": n_simulations,
            "mean_final_bankroll": round(float(np.mean(arr)), 2),
            "median_final_bankroll": round(float(np.median(arr)), 2),
            "std_final_bankroll": round(float(np.std(arr)), 2),
            "min_final_bankroll": round(float(np.min(arr)), 2),
            "max_final_bankroll": round(float(np.max(arr)), 2),
            "percentile_5th": round(float(np.percentile(arr, 5)), 2),
            "percentile_95th": round(float(np.percentile(arr, 95)), 2),
            "probability_of_profit": round(profit_count / n_simulations, 4),
            "probability_of_ruin": round(ruin_count / n_simulations, 4),
        }
