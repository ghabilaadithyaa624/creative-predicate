"""
Specialized autonomous agent for prediction markets (e.g. Polymarket).
"""
from typing import Dict, List, Any, Optional
from loguru import logger

from agents.base_agent import BaseAgent, AgentStatus
from agents.survival_manager import SurvivalMode, SurvivalRule
from trading.paper_engine import PaperTradingEngine, Bet
from trading.bet_manager import BetManager, SizingConfig
from analysis.scraper import MarketScraper, MarketData
from analysis.odds_analyzer import OddsAnalyzer
from analysis.probability_models import ProbabilityEstimator


class PolymarketAgent(BaseAgent):
    """
    Autonomous agent targeting prediction markets:
    - Scrapes & tracks orderbook spreads
    - Estimates true probabilities with volume weighting & sentiment
    - Places positive EV bets sized via fractional Kelly
    """

    def __init__(
        self,
        name: str,
        trading_engine: PaperTradingEngine,
        initial_bankroll: float = 100.0,
        survival_mode: SurvivalMode = SurvivalMode.AGGRESSIVE,
        survival_rule: Optional[SurvivalRule] = None,
        tick_interval: float = 10.0,
        min_edge: float = 0.02,
        kelly_fraction: float = 0.25,
        max_concurrent_bets: int = 5,
    ):
        super().__init__(
            name=name,
            trading_engine=trading_engine,
            initial_bankroll=initial_bankroll,
            survival_mode=survival_mode,
            survival_rule=survival_rule,
            tick_interval=tick_interval,
        )
        self.scraper = MarketScraper()
        self.prob_estimator = ProbabilityEstimator()
        self.odds_analyzer = OddsAnalyzer()
        self.bet_manager = BetManager(
            SizingConfig(
                kelly_fraction=kelly_fraction,
                min_edge=min_edge,
                max_bet_pct=0.08,
            )
        )
        self.min_edge = min_edge
        self.max_concurrent_bets = max_concurrent_bets

    async def perceive(self) -> Dict[str, Any]:
        """Perceive prediction markets."""
        markets = self.scraper.scrape_polymarket()
        return {"markets": markets}

    async def reason(self, perception_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reason about market mispricings and identify positive EV opportunities."""
        markets: List[MarketData] = perception_data.get("markets", [])
        opportunities: List[Dict[str, Any]] = []

        # Current open pending bets to avoid double-betting on same event
        open_events = {b.event for b in self.paper_state.bets if b.status.value == "pending"}

        for market in markets:
            if market.event_name in open_events:
                continue

            # Evaluate YES outcome
            implied_yes = OddsAnalyzer.decimal_to_implied(market.odds_home)
            fair_prob_yes = self.prob_estimator.estimate_fair_probability(
                implied_market_prob=implied_yes,
                volume_24h=market.volume or 10000.0,
            )
            eval_yes = self.prob_estimator.evaluate_opportunity(
                event_name=market.event_name,
                selection="Yes",
                decimal_odds=market.odds_home,
                true_prob_estimate=fair_prob_yes,
                volume=market.volume or 10000.0,
            )

            if eval_yes["edge"] >= self.min_edge:
                opportunities.append({
                    "market": market.source,
                    "event": market.event_name,
                    "selection": "Yes",
                    "odds": market.odds_home,
                    "true_probability": fair_prob_yes,
                    "edge": eval_yes["edge"],
                    "confidence": eval_yes["confidence"],
                })

            # Evaluate NO outcome
            implied_no = OddsAnalyzer.decimal_to_implied(market.odds_away)
            fair_prob_no = self.prob_estimator.estimate_fair_probability(
                implied_market_prob=implied_no,
                volume_24h=market.volume or 10000.0,
            )
            eval_no = self.prob_estimator.evaluate_opportunity(
                event_name=market.event_name,
                selection="No",
                decimal_odds=market.odds_away,
                true_prob_estimate=fair_prob_no,
                volume=market.volume or 10000.0,
            )

            if eval_no["edge"] >= self.min_edge:
                opportunities.append({
                    "market": market.source,
                    "event": market.event_name,
                    "selection": "No",
                    "odds": market.odds_away,
                    "true_probability": fair_prob_no,
                    "edge": eval_no["edge"],
                    "confidence": eval_no["confidence"],
                })

        # Allocate stakes via BetManager
        allocated = self.bet_manager.allocate_portfolio_bets(
            opportunities=opportunities,
            available_bankroll=self.paper_state.current_bankroll,
        )
        return allocated[:self.max_concurrent_bets]

    async def act(self, decisions: List[Dict[str, Any]]) -> List[Bet]:
        """Place paper trades for all allocated decisions."""
        placed_bets: List[Bet] = []
        for d in decisions:
            stake = d.get("allocated_stake", 0.0)
            if stake <= 0:
                continue

            bet = self.trading_engine.place_bet(
                agent_name=self.name,
                market=d["market"],
                event=d["event"],
                selection=d["selection"],
                odds=d["odds"],
                stake=stake,
                expected_value=d["edge"],
                metadata={"confidence": d.get("confidence", 0.5), "true_prob": d.get("true_probability")},
            )
            if bet:
                placed_bets.append(bet)
                logger.info(f"[{self.name}] Placed Bet: ${stake:.2f} on '{d['selection']}' for '{d['event']}' @ {d['odds']}x (Edge: +{d['edge']*100:.1f}%)")

        return placed_bets
