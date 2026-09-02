"""
Odds and Expected Value (EV) mathematical analysis toolkit.
"""
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


class OddsAnalyzer:
    """
    Mathematical toolkit for betting markets analysis:
    - Decimal / American / Implied Odds conversion
    - Vig / Juice removal
    - Expected Value (EV) and Edge quantification
    - Cross-market arbitrage detection
    """

    @staticmethod
    def decimal_to_implied(decimal_odds: float) -> float:
        if decimal_odds <= 0:
            return 0.0
        return 1.0 / decimal_odds

    @staticmethod
    def implied_to_decimal(probability: float) -> float:
        if probability <= 0:
            return 0.0
        return 1.0 / probability

    @staticmethod
    def american_to_decimal(american_odds: float) -> float:
        if american_odds > 0:
            return (american_odds / 100.0) + 1.0
        elif american_odds < 0:
            return (100.0 / abs(american_odds)) + 1.0
        return 1.0

    @staticmethod
    def remove_vig_multiplicative(odds_list: List[float]) -> List[float]:
        """
        Removes bookmaker overround (vig) using standard multiplicative normalization.
        """
        implied_probs = [OddsAnalyzer.decimal_to_implied(o) for o in odds_list if o > 0]
        total_overround = sum(implied_probs)
        if total_overround == 0:
            return implied_probs
        return [p / total_overround for p in implied_probs]

    @staticmethod
    def calculate_expected_value(true_probability: float, decimal_odds: float) -> float:
        """
        Expected Value per 1 unit wagered:
        EV = (p * (odds - 1)) - (1 - p) * 1 = (p * odds) - 1
        """
        return (true_probability * decimal_odds) - 1.0

    @staticmethod
    def calculate_edge(true_probability: float, decimal_odds: float) -> float:
        """
        Edge = True Probability - Implied Market Probability
        """
        implied_prob = OddsAnalyzer.decimal_to_implied(decimal_odds)
        return true_probability - implied_prob

    @staticmethod
    def calculate_kelly(
        true_probability: float,
        decimal_odds: float,
        fraction: float = 0.25,
    ) -> float:
        """
        Fractional Kelly fraction:
        f = fraction * (b*p - q) / b
        """
        if decimal_odds <= 1.0 or true_probability <= 0.0:
            return 0.0
        b = decimal_odds - 1.0
        p = true_probability
        q = 1.0 - p
        kelly = (b * p - q) / b
        return max(0.0, kelly * fraction)

    @staticmethod
    def detect_arbitrage(market_a_odds: float, market_b_odds: float) -> Dict[str, Any]:
        """
        Determines if an arbitrage (surebet) exists across two binary outcomes.
        Arbitrage exists if (1 / odds_a) + (1 / odds_b) < 1.0
        """
        if market_a_odds <= 0 or market_b_odds <= 0:
            return {"arbitrage_found": False, "margin_percent": 0.0}

        inv_sum = (1.0 / market_a_odds) + (1.0 / market_b_odds)
        is_arb = inv_sum < 1.0
        profit_margin = ((1.0 - inv_sum) / inv_sum) * 100.0 if is_arb else 0.0

        stake_a_ratio = (1.0 / market_a_odds) / inv_sum
        stake_b_ratio = (1.0 / market_b_odds) / inv_sum

        return {
            "arbitrage_found": is_arb,
            "margin_percent": round(profit_margin, 2),
            "inv_sum": round(inv_sum, 4),
            "stake_split": {
                "outcome_a": round(stake_a_ratio, 4),
                "outcome_b": round(stake_b_ratio, 4),
            },
        }
