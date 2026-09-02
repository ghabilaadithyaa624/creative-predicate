"""
Settlement verification and outcome resolution engine.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
from trading.paper_engine import PaperTradingEngine, Bet, BetStatus


class SettlementEngine:
    """
    Resolves outcomes for open bets by querying oracles, market results, or simulations.
    """

    def __init__(self, paper_engine: PaperTradingEngine):
        self.paper_engine = paper_engine
        self.resolution_cache: Dict[str, Dict[str, Any]] = {}

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

    def auto_simulate_pending_resolutions(self, win_probability_weight: float = 0.5):
        """
        Convenience function for simulation tests: settle open bets based on odds probability.
        """
        import random
        for agent_name, agent in self.paper_engine.agents.items():
            for bet in list(agent.bets):
                if bet.status == BetStatus.PENDING:
                    implied_prob = 1.0 / bet.odds if bet.odds > 0 else 0.5
                    # Random outcome weighted by implied probability
                    won = random.random() < implied_prob
                    self.paper_engine.settle_bet(agent_name, bet.id, won=won)
