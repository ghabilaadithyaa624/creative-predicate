"""
Unit tests for Autonomous Agents and Lifecycle.
"""
import asyncio

import pytest

from agents.polymarket_agent import PolymarketAgent
from agents.sports_agent import SportsAgent
from trading.paper_engine import PaperTradingEngine, SurvivalMode


@pytest.mark.asyncio
async def test_polymarket_agent_cycle():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = PolymarketAgent(
        name="TestPolyBot",
        trading_engine=engine,
        initial_bankroll=100.0,
        survival_mode=SurvivalMode.AGGRESSIVE,
    )

    success = await agent.run_cycle()
    assert success is True
    assert len(agent.history) == 1
    assert agent.paper_state.is_alive is True


@pytest.mark.asyncio
async def test_sports_agent_cycle():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = SportsAgent(
        name="TestSportsBot",
        trading_engine=engine,
        initial_bankroll=100.0,
        survival_mode=SurvivalMode.CONSERVATIVE,
    )

    success = await agent.run_cycle()
    assert success is True
    assert agent.paper_state.is_alive is True
