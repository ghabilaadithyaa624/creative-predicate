"""
Settlement verification and outcome resolution engine.
"""
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from backend.trading.paper_engine import Bet, BetStatus, PaperTradingEngine


class SettlementEngine:
    """
    Resolves outcomes for open bets by querying oracles, market results, or simulations.
    """

    def __init__(self, paper_engine: PaperTradingEngine, seed: Optional[int] = None):
        self.paper_engine = paper_engine
        self.resolution_cache: Dict[str, Dict[str, Any]] = {}
        # Dedicated RNG so simulated settlement is reproducible with a seed and
        # never disturbs global random state used elsewhere.
        self._rng = random.Random(seed)

    def register_market_outcome(
        self,
        event_key: str,
        winning_selection: str,
        settled_time: Optional[datetime] = None,
        is_cancelled: bool = False,
    ):
        """
        Manually or programmatically register the outcome of an event.
        """
        self.resolution_cache[event_key] = {
            "winning_selection": winning_selection,
            "settled_time": settled_time or datetime.now(),
            "is_cancelled": is_cancelled,
        }

    def process_pending_bets(self) -> List[Tuple[str, str, BetStatus]]:
        """
        Scan all pending bets across agents and settle any matching known outcomes.
        Returns list of (agent_name, bet_id, final_status).
        """
        settled_records = []

        for agent_name, agent in self.paper_engine.agents.items():
            for bet in list(agent.bets):
                if bet.status != BetStatus.PENDING:
                    continue

                event_outcome = self.resolution_cache.get(bet.event)
                if not event_outcome:
                    continue

                if event_outcome.get("is_cancelled"):
                    self.paper_engine.settle_bet(agent_name, bet.id, won=False, is_cancelled=True)
                    settled_records.append((agent_name, bet.id, BetStatus.CANCELLED))
                else:
                    winning_sel = event_outcome.get("winning_selection")
                    won = (bet.selection.lower().strip() == str(winning_sel).lower().strip())
                    self.paper_engine.settle_bet(agent_name, bet.id, won=won)
                    settled_records.append((agent_name, bet.id, BetStatus.WON if won else BetStatus.LOST))

        return settled_records

    def auto_simulate_pending_resolutions(
        self,
        ground_truth: Optional[Dict[str, float]] = None,
        edge_realisation: float = 1.0,
    ):
        """
        Simulate resolution of open bets against a *ground-truth* win probability.

        Why this matters
        ----------------
        The previous implementation drew outcomes from the bookmaker's implied
        probability (1 / odds) while the agent staked on its own estimated
        probability. That makes the simulated expected value identically zero
        (in fact negative once the overround is included) no matter how good
        the agent's model is, so every backtest measured nothing but variance
        and a profitable strategy was indistinguishable from a broken one.

        Outcomes are now drawn from the probability the agent actually forecast
        (``bet.metadata['true_prob']``), so a genuine edge shows up as genuine
        profit and a bogus edge shows up as a loss.

        Parameters
        ----------
        ground_truth:
            Optional map of ``event name -> true win probability`` for the
            selection that was backed. Takes priority over bet metadata; use it
            to score an agent against a world that disagrees with its forecast.
        edge_realisation:
            Fraction of the agent's claimed edge over the market that is real.
            ``1.0`` trusts the forecast fully; ``0.0`` collapses to the market
            implied probability (a pure zero-edge world, the old behaviour);
            values in between model a partially-correct model. Useful for
            stress-testing how much of the reported PnL depends on the model
            being right.
        """
        for agent_name, agent in self.paper_engine.agents.items():
            for bet in list(agent.bets):
                if bet.status != BetStatus.PENDING:
                    continue

                win_prob = self._resolve_win_probability(
                    bet, ground_truth, edge_realisation
                )
                won = self._rng.random() < win_prob
                self.paper_engine.settle_bet(agent_name, bet.id, won=won)

    @staticmethod
    def _resolve_win_probability(
        bet: Bet,
        ground_truth: Optional[Dict[str, float]],
        edge_realisation: float,
    ) -> float:
        """Determine the probability an open bet should win under simulation."""
        implied_prob = 1.0 / bet.odds if bet.odds > 0 else 0.5

        if ground_truth and bet.event in ground_truth:
            true_prob = float(ground_truth[bet.event])
        else:
            forecast = bet.metadata.get("true_prob")
            try:
                true_prob = float(forecast) if forecast is not None else implied_prob
            except (TypeError, ValueError):
                logger.warning(
                    f"Bet {bet.id} carries a non-numeric true_prob "
                    f"({forecast!r}); falling back to market implied probability."
                )
                true_prob = implied_prob

        # Interpolate between the market's view and the agent's view.
        realised = implied_prob + edge_realisation * (true_prob - implied_prob)
        return min(max(realised, 0.0), 1.0)
