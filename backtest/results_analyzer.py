"""
Backtest reporting and summary formatting utilities.
"""
from typing import Dict, Any


class ResultsAnalyzer:
    @staticmethod
    def format_summary_table(results: Dict[str, Any]) -> str:
        lines = [
            "========================================",
            "        BACKTEST RESULTS SUMMARY        ",
            "========================================",
            f"Initial Bankroll   : ${results.get('initial_bankroll', 100.0):.2f}",
            f"Final Bankroll     : ${results.get('final_bankroll', 0.0):.2f}",
            f"Total Profit / Loss: ${results.get('total_profit', 0.0):+.2f}",
            f"ROI (%)            : {results.get('roi_percent', 0.0):+.2f}%",
            f"Total Trades       : {results.get('total_bets', 0)}",
            f"Win Rate (%)       : {results.get('win_rate', 0.0)*100:.1f}%",
            f"Profit Factor      : {results.get('profit_factor', 1.0):.2f}",
            f"Sharpe Ratio       : {results.get('sharpe_ratio', 0.0):.2f}",
            f"Sortino Ratio      : {results.get('sortino_ratio', 0.0):.2f}",
            f"Max Drawdown (%)   : {results.get('max_drawdown', 0.0)*100:.1f}%",
            "========================================",
        ]
        return "\n".join(lines)
