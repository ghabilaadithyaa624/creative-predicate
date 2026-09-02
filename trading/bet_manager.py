"""
Bet sizing and portfolio risk management.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class SizingConfig:
    kelly_fraction: float = 0.25
    max_bet_pct: float = 0.05
    min_bet_amount: float = 1.0
    min_edge: float = 0.02
    max_portfolio_exposure_pct: float = 0.30


class BetManager:
    """
    Manages optimal stake allocation, exposure limits, and position sizing.
    """

    def __init__(self, config: Optional[SizingConfig] = None):
        self.config = config or SizingConfig()

    def calculate_kelly_stake(
        self,
        true_prob: float,
        decimal_odds: float,
        available_bankroll: float,
        fraction: Optional[float] = None,
    ) -> float:
        """
        Calculate stake using Fractional Kelly Criterion:
        f* = (b * p - q) / b
        where:
          b = decimal_odds - 1 (net decimal odds)
          p = true win probability
          q = 1 - p (loss probability)
        """
        if decimal_odds <= 1.0 or true_prob <= 0.0 or true_prob > 1.0:
            return 0.0

        b = decimal_odds - 1.0
        p = true_prob
        q = 1.0 - p

        raw_kelly = (b * p - q) / b
        if raw_kelly <= 0:
            return 0.0

        kelly_frac = fraction if fraction is not None else self.config.kelly_fraction
        target_pct = raw_kelly * kelly_frac

        # Cap by maximum bet percentage
        target_pct = min(target_pct, self.config.max_bet_pct)

        calculated_stake = available_bankroll * target_pct
        if calculated_stake < self.config.min_bet_amount:
            return 0.0

        return round(min(calculated_stake, available_bankroll), 2)

    def allocate_portfolio_bets(
        self,
        opportunities: List[Dict[str, Any]],
        available_bankroll: float,
        current_open_exposure: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Allocates stakes across multiple candidate bets respecting portfolio constraints.
        """
        max_allowed_total = available_bankroll * self.config.max_portfolio_exposure_pct
        remaining_budget = max(0.0, max_allowed_total - current_open_exposure)

        allocated_bets = []
        # Sort opportunities by edge (expected value) descending
        sorted_opps = sorted(opportunities, key=lambda x: x.get("edge", 0.0), reverse=True)

        for opp in sorted_opps:
            edge = opp.get("edge", 0.0)
            if edge < self.config.min_edge:
                continue

            true_prob = opp.get("true_probability", 0.5)
            odds = opp.get("odds", 2.0)

            stake = self.calculate_kelly_stake(true_prob, odds, available_bankroll)
            if stake <= 0:
                continue

            # Limit to remaining portfolio risk budget
            stake = min(stake, remaining_budget)
            if stake < self.config.min_bet_amount:
                continue

            allocated_bets.append({
                **opp,
                "allocated_stake": stake,
            })
            remaining_budget -= stake
            if remaining_budget <= self.config.min_bet_amount:
                break

        return allocated_bets
