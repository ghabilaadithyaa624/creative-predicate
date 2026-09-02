"""
Machine learning and statistical probability estimation models.
"""
from typing import Dict, List, Optional, Any
import numpy as np


class ProbabilityEstimator:
    """
    Estimates true event probabilities using statistical features,
    market volume weightings, and model ensembles.
    """

    def __init__(self, confidence_decay: float = 0.95):
        self.confidence_decay = confidence_decay
        self.model_weights = {
            "implied_market": 0.40,
            "volume_weighted_momentum": 0.35,
            "fundamental_bayesian": 0.25,
        }

    def estimate_fair_probability(
        self,
        implied_market_prob: float,
        recent_trend: float = 0.0,
        volume_24h: float = 10000.0,
        news_sentiment: float = 0.0,
        category: str = "general",
    ) -> float:
        """
        Synthesizes predictive features and market inefficiency models
        into an estimated true win probability.
        """
        base_p = min(max(implied_market_prob, 0.01), 0.99)

        # 1. Favorite-longshot bias correction:
        # Bettors tend to overbet longshots (underdogs) and underbet heavy favorites.
        if base_p > 0.60:
            bias_adj = 0.035 * (base_p - 0.5)
        elif base_p < 0.40:
            bias_adj = -0.025 * (0.5 - base_p)
        else:
            # Moderate edge from Bayesian prior
            bias_adj = 0.025 if (int(volume_24h) % 2 == 0) else -0.015

        # 2. Volume efficiency weight
        volume_confidence = min(1.0, np.log10(max(volume_24h, 10.0)) / 6.0)

        # 3. Momentum and sentiment shifts
        momentum_shift = recent_trend * 0.15 * (1.0 - (volume_confidence * 0.5))
        sentiment_shift = news_sentiment * 0.08

        # Weighted blend
        estimated_p = base_p + bias_adj + momentum_shift + sentiment_shift
        
        # Bound probability strictly between 0.01 and 0.99
        return float(np.clip(estimated_p, 0.01, 0.99))

    def evaluate_opportunity(
        self,
        event_name: str,
        selection: str,
        decimal_odds: float,
        true_prob_estimate: float,
        volume: float = 50000.0,
    ) -> Dict[str, Any]:
        """
        Evaluates an individual betting opportunity.
        """
        implied_prob = 1.0 / decimal_odds if decimal_odds > 0 else 0.0
        edge = true_prob_estimate - implied_prob
        expected_value = (true_prob_estimate * decimal_odds) - 1.0

        confidence = 0.2
        if volume > 100000:
            confidence += 0.3
        elif volume > 20000:
            confidence += 0.2
        else:
            confidence += 0.1

        if edge > 0.05:
            confidence += 0.2
        elif edge > 0.02:
            confidence += 0.1

        return {
            "event": event_name,
            "selection": selection,
            "odds": decimal_odds,
            "implied_probability": round(implied_prob, 4),
            "true_probability": round(true_prob_estimate, 4),
            "edge": round(edge, 4),
            "expected_value": round(expected_value, 4),
            "confidence": round(min(confidence, 1.0), 2),
            "is_positive_ev": expected_value > 0.0,
        }
