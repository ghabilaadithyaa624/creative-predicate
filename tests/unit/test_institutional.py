"""
Unit tests for institutional-grade autonomous agent modules.
"""
import asyncio

import numpy as np
import pytest

from backend.blockchain.decentralized_consensus import BlockchainConsensus, OffChainConsensusBFT
from backend.feeds.websocket_manager import ArbitrageDetector, MarketUpdate, WebSocketFeedManager
from backend.ml_models.probability_engine import EnsembleProbabilityModel, SentimentAnalyzer
from backend.monte_carlo.extreme_risk_simulation import MonteCarloRiskEngine
from backend.notifications.alert_manager import NotificationManager
from backend.reinforcement_learning.trading_agent_rl import PPOTrader, TradingEnvironment
from backend.risk.advanced_position_sizing import PositionSizer
from backend.swarm.coordinator import AgentRole, SwarmCoordinator


def test_sentiment_and_ensemble():
    sa = SentimentAnalyzer()
    res = sa.analyze(["Lakers surge with strong win", "Injury drops team confidence"])
    assert "score" in res
    assert "positive" in res

    ensemble = EnsembleProbabilityModel()
    pred = ensemble.predict({"odds": 2.10, "sentiment": 0.3, "volume": 50000})
    assert 0.01 <= pred["probability"] <= 0.99
    assert "uncertainty" in pred
    assert "confidence" in pred


@pytest.mark.asyncio
async def test_swarm_coordinator():
    coordinator = SwarmCoordinator(min_agents_for_consensus=2)
    coordinator.register_agent("Analyst_1", AgentRole.ANALYST)
    coordinator.register_agent("Analyst_2", AgentRole.ANALYST)

    prop_id = await coordinator.propose_opportunity("Analyst_1", {"id": "opp_1", "odds": 2.0})
    assert prop_id is not None

    await coordinator.vote_on_opportunity("Analyst_1", prop_id, 0.60, 0.90, opportunity_odds=2.0)
    await coordinator.vote_on_opportunity("Analyst_2", prop_id, 0.65, 0.85, opportunity_odds=2.0)

    consensus = coordinator.consensus_pool[prop_id]
    assert consensus.status == "approved"
    assert consensus.consensus_probability > 0.50


@pytest.mark.asyncio
async def test_feeds_and_arbitrage():
    feed = WebSocketFeedManager()
    detector = ArbitrageDetector(feed)

    # Ingest odds that create cross-exchange arbitrage
    upd1 = MarketUpdate("polymarket", "m1", "Event X", odds_home=2.20, odds_away=1.60, volume=10000)
    upd2 = MarketUpdate("betfair", "m1", "Event X", odds_home=1.60, odds_away=2.20, volume=10000)

    await feed.ingest_update(upd1)
    await feed.ingest_update(upd2)

    arbs = detector.scan_all_for_arbitrage()
    assert len(arbs) > 0
    assert arbs[0]["profit_margin_pct"] > 0


def test_advanced_position_sizing():
    sizer = PositionSizer()
    res_k = sizer.calculate_fractional_kelly(bankroll=1000.0, probability=0.60, odds=2.0, fraction=0.25)
    assert res_k["size"] == 50.0  # 5% of 1000 = $50

    res_opt_f = sizer.calculate_optimal_f(bankroll=1000.0, trade_history_pnls=[10, -5, 12, -4, 8, -6, 15])
    assert res_opt_f["size"] > 0

    res_unc = sizer.calculate_uncertainty_adjusted_kelly(bankroll=1000.0, probability=0.60, odds=2.0, uncertainty_std=0.04)
    assert res_unc["size"] > 0


def test_reinforcement_learning_env_and_ppo():
    env = TradingEnvironment(initial_bankroll=100.0)
    state = env.reset()
    assert len(state) == env.state_dim

    action = np.array([0.05, 0.02, 0.0, 0.0, 0.0], dtype=np.float32)
    next_s, reward, done, info = env.step(action)
    assert len(next_s) == env.state_dim
    assert "bankroll" in info

    agent = PPOTrader(env)
    train_res = agent.train_episodes(episodes=3)
    assert train_res["episodes_trained"] == 3


def test_monte_carlo_extreme_risk():
    mc = MonteCarloRiskEngine(n_simulations=1000)
    returns = np.random.normal(0.01, 0.03, size=200)
    var_dict = mc.calculate_var_cvar(returns)
    assert 0.95 in var_dict
    assert var_dict[0.95][0] < 0  # VaR is negative return threshold

    stress = mc.stress_test_scenarios(initial_bankroll=100.0)
    assert "black_swan_crash" in stress


def test_blockchain_consensus_and_bft():
    bc = BlockchainConsensus()
    prop_id = bc.create_proposal("0xAgentA", "polymarket", "Yes", 2.0, 10.0, 0.05)
    bc.cast_vote("0xAgentA", prop_id, approve=True, stake_amount=20.0)
    bc.cast_vote("0xAgentB", prop_id, approve=True, stake_amount=30.0)
    bc.cast_vote("0xAgentC", prop_id, approve=False, stake_amount=10.0)

    eval_res = bc.evaluate_consensus(prop_id)
    assert eval_res["status"] == "approved"
    assert eval_res["yes_ratio"] > 0.60

    bft = OffChainConsensusBFT(n_agents=4, f_byzantine=1)
    bft.submit_vote("p1", "ag1", approve=True)
    bft.submit_vote("p1", "ag2", approve=True)
    r3 = bft.submit_vote("p1", "ag3", approve=True)
    assert r3["finalized"] is True
    assert r3["approved"] is True
