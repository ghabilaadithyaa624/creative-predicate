"""
Autonomous agent specializing in sports betting markets and vig-free odds arbitrage.
"""
from typing import Dict, List, Any, Optional
from loguru import logger

from agents.base_agent import BaseAgent
from agents.survival_manager import SurvivalMode, SurvivalRule
from trading.paper_engine import PaperTradingEngine, Bet
from trading.bet_manager import BetManager, SizingConfig
from analysis.scraper import MarketScraper, MarketData
from analysis.odds_analyzer import OddsAnalyzer
from analysis.probability_models import ProbabilityEstimator


class SportsAgent(BaseAgent):
    """
    Autonomous sports trading agent:
    - Analyzes 2-way and 3-way moneyline sports markets
    - Strips bookmaker vig (overround)
    - Finds value opportunities and executes sized positions
    """

    def __init__(
        self,
        name: str,
        trading_engine: PaperTradingEngine,
        initial_bankroll: float = 100.0,
        survival_mode: SurvivalMode = SurvivalMode.CONSERVATIVE,
        survival_rule: Optional[SurvivalRule] = None,
        tick_interval: float = 15.0,
        min_edge: float = 0.03,
        kelly_fraction: float = 0.20,
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
        self.bet_manager = BetManager(
            SizingConfig(
                kelly_fraction=kelly_fraction,
                min_edge=min_edge,
                max_bet_pct=0.06,
            )
        )
        self.min_edge = min_edge

    async def perceive(self) -> Dict[str, Any]:
        raw_markets = self.scraper.generate_mock_markets(count=6)
        sports_markets = [m for m in raw_markets if m.category in ("basketball", "football", "sports")]
        return {"markets": sports_markets if sports_markets else raw_markets}

    async def reason(self, perception_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        markets: List[MarketData] = perception_data.get("markets", [])
        opportunities: List[Dict[str, Any]] = []

        open_events = {b.event for b in self.paper_state.bets if b.status.value == "pending"}

        for market in markets:
            if market.event_name in open_events:
                continue

            # Remove bookmaker vig
            fair_probs = OddsAnalyzer.remove_vig_multiplicative([market.odds_home, market.odds_away])
            fair_home_p = fair_probs[0] if len(fair_probs) > 0 else 0.5
            fair_away_p = fair_probs[1] if len(fair_probs) > 1 else 0.5

            # Evaluate Home team
            implied_home = OddsAnalyzer.decimal_to_implied(market.odds_home)
            edge_home = fair_home_p - implied_home

            if edge_home >= self.min_edge:
                opportunities.append({
                    "market": "sports",
                    "event": market.event_name,
                    "selection": "Home",
                    "odds": market.odds_home,
                    "true_probability": fair_home_p,
                    "edge": edge_home,
                    "confidence": 0.70,
                })

            # Evaluate Away team
            implied_away = OddsAnalyzer.decimal_to_implied(market.odds_away)
            edge_away = fair_away_p - implied_away

            if edge_away >= self.min_edge:
                opportunities.append({
                    "market": "sports",
                    "event": market.event_name,
                    "selection": "Away",
                    "odds": market.odds_away,
                    "true_probability": fair_away_p,
                    "edge": edge_away,
                    "confidence": 0.70,
                })

        allocated = self.bet_manager.allocate_portfolio_bets(
            opportunities=opportunities,
            available_bankroll=self.paper_state.current_bankroll,
        )
        return allocated

    async def act(self, decisions: List[Dict[str, Any]]) -> List[Bet]:
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
            )
            if bet:
                placed_bets.append(bet)
                logger.info(f"[{self.name}] Placed Sports Bet: ${stake:.2f} on '{d['selection']}' in '{d['event']}'")

        return placed_bets
