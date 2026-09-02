"""
Performance analytics and quantitative metrics calculations.
"""
from typing import Any, Dict, List

import numpy as np
import pandas as pd


class PerformanceAnalyzer:
    """
    Computes statistical and financial metrics for trading agents.
    """

    @staticmethod
    def compute_all_metrics(
        initial_bankroll: float,
        final_bankroll: float,
        bets: List[Dict[str, Any]],
        risk_free_rate: float = 0.02,
    ) -> Dict[str, Any]:
        if not bets:
            return {
                "total_bets": 0,
                "win_rate": 0.0,
                "profit": final_bankroll - initial_bankroll,
                "roi_pct": ((final_bankroll - initial_bankroll) / initial_bankroll * 100) if initial_bankroll > 0 else 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 1.0,
            }

        df = pd.DataFrame(bets)
        total_bets = len(df)

        # Calculate winning / losing.
        # The `won` fallback is coerced to a real boolean mask: comparing a
        # possibly-missing column against True/False silently yields a scalar
        # (not a mask) when the column is absent, which raises on indexing.
        if "status" in df.columns:
            won_bets = df[df["status"] == "won"]
            lost_bets = df[df["status"] == "lost"]
        elif "won" in df.columns:
            won_mask = df["won"].fillna(False).astype(bool)
            won_bets = df[won_mask]
            lost_bets = df[~won_mask]
        else:
            won_bets = df.iloc[0:0]
            lost_bets = df.iloc[0:0]

        win_count = len(won_bets)
        loss_count = len(lost_bets)
        win_rate = (win_count / total_bets) if total_bets > 0 else 0.0

        pnls = df["pnl"] if "pnl" in df.columns else df.apply(
            lambda r: (r["bet_size"] * (r["odds"] - 1)) if r.get("won", False) else -r["bet_size"], axis=1
        )

        gross_profit = pnls[pnls > 0].sum()
        gross_loss = abs(pnls[pnls < 0].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        # Equity progression & Drawdown
        cum_pnl = pnls.cumsum()
        equity_curve = initial_bankroll + cum_pnl
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (running_max - equity_curve) / running_max
        max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Returns and Sharpe / Sortino
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            excess_returns = returns - (risk_free_rate / 252.0)
            sharpe_ratio = float(np.sqrt(252.0) * excess_returns.mean() / returns.std())

            # Downside deviation for Sortino
            downside_returns = returns[returns < 0]
            downside_std = downside_returns.std()
            sortino_ratio = float(np.sqrt(252.0) * excess_returns.mean() / downside_std) if (downside_std and downside_std > 0) else sharpe_ratio
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

        total_profit = final_bankroll - initial_bankroll
        roi_pct = (total_profit / initial_bankroll * 100.0) if initial_bankroll > 0 else 0.0

        return {
            "total_bets": total_bets,
            "won_bets": win_count,
            "lost_bets": loss_count,
            "win_rate": round(win_rate, 4),
            "total_profit": round(total_profit, 2),
            "roi_percent": round(roi_pct, 2),
            "max_drawdown": round(max_drawdown, 4),
            "profit_factor": round(float(profit_factor), 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "avg_stake": round(float(df["stake"].mean()) if "stake" in df.columns else float(df["bet_size"].mean()) if "bet_size" in df.columns else 0.0, 2),
            "avg_odds": round(float(df["odds"].mean()), 2) if "odds" in df.columns else 0.0,
        }
