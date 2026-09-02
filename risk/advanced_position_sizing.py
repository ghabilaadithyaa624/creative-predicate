"""
Advanced position sizing algorithms:
- Fractional Kelly Criterion
- Ralph Vince's Optimal f (Maximizing Terminal Wealth Relative)
- Confidence-Adjusted Kelly for prediction uncertainty
- Portfolio Kelly allocation across correlated bets
"""
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger
from scipy.optimize import minimize, minimize_scalar


class PositionSizer:
    """
    Quantitative position sizing engine.
    """

    def __init__(self, default_strategy: str = "fractional_kelly"):
        self.default_strategy = default_strategy

    def calculate_fractional_kelly(
        self,
        bankroll: float,
        probability: float,
        odds: float,
        fraction: float = 0.25,
        simultaneous_bets: int = 1,
    ) -> Dict[str, float]:
        b = odds - 1.0
        p = probability
        q = 1.0 - p

        if b <= 0 or p <= 0 or p >= 1:
            return {'size': 0.0, 'fraction': 0.0, 'edge': 0.0}

        raw_kelly = (b * p - q) / b
        if raw_kelly <= 0:
            return {'size': 0.0, 'fraction': 0.0, 'edge': 0.0}

        # Correlation dampening for simultaneous positions
        if simultaneous_bets > 1:
            raw_kelly /= (simultaneous_bets ** 0.5)

        target_fraction = max(0.0, min(raw_kelly * fraction, 0.20))
        size = round(bankroll * target_fraction, 2)
        growth_rate = p * np.log(1 + target_fraction * b) + q * np.log(max(1e-6, 1 - target_fraction))

        return {
            'size': size,
            'fraction': round(target_fraction, 4),
            'full_kelly': round(raw_kelly, 4),
            'edge': round(b * p - q, 4),
            'expected_growth_rate': round(float(growth_rate), 4),
        }

    def calculate_optimal_f(
        self,
        bankroll: float,
        trade_history_pnls: List[float],
        max_risk_cap: float = 0.25,
    ) -> Dict[str, float]:
        """
        Ralph Vince's Optimal f algorithm to maximize Terminal Wealth Relative (TWR).
        """
        if len(trade_history_pnls) < 5:
            default_f = 0.03
            return {'size': round(bankroll * default_f, 2), 'fraction': default_f, 'f': default_f}

        returns = np.array(trade_history_pnls)
        min_loss = abs(min(returns)) if min(returns) < 0 else 1.0

        def negative_twr(f):
            if f <= 0 or f > max_risk_cap:
                return 0.0
            hprs = 1.0 + f * (returns / min_loss)
            if np.any(hprs <= 0):
                return 1e9
            return -float(np.prod(hprs))

        res = minimize_scalar(negative_twr, bounds=(0.01, max_risk_cap), method='bounded')
        opt_f = float(res.x) if res.success else 0.03
        bet_size = round(bankroll * opt_f, 2)

        return {
            'size': bet_size,
            'fraction': round(opt_f, 4),
            'f': round(opt_f, 4),
            'twr': round(-float(res.fun), 4) if res.success else 1.0,
        }

    def calculate_uncertainty_adjusted_kelly(
        self,
        bankroll: float,
        probability: float,
        odds: float,
        uncertainty_std: float,
        confidence_z: float = 1.96,
    ) -> Dict[str, float]:
        """
        Sizes conservatively by taking the lower confidence bound of estimated probability.
        """
        conservative_p = max(0.01, probability - (confidence_z * uncertainty_std))
        cons_res = self.calculate_fractional_kelly(bankroll, conservative_p, odds)
        base_res = self.calculate_fractional_kelly(bankroll, probability, odds)

        blended_size = round((cons_res['size'] + base_res['size']) / 2.0, 2)
        return {
            'size': blended_size,
            'fraction': round(blended_size / bankroll, 4) if bankroll > 0 else 0.0,
            'point_estimate_prob': round(probability, 4),
            'conservative_bound_prob': round(conservative_p, 4),
            'uncertainty_std': round(uncertainty_std, 4),
        }
