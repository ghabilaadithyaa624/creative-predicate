"""
Unit tests for Paper Trading Engine and Bet Manager.
"""
import pytest
from trading.paper_engine import PaperTradingEngine, SurvivalMode, BetStatus
from trading.bet_manager import BetManager, SizingConfig
from trading.performance import PerformanceAnalyzer


def test_paper_engine_create_agent():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = engine.create_agent("TestBot", initial_bankroll=150.0, survival_mode=SurvivalMode.AGGRESSIVE)
    assert agent.name == "TestBot"
    assert agent.current_bankroll == 150.0
    assert agent.is_alive is True


def test_paper_engine_place_and_settle_win():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    engine.create_agent("WinBot", 100.0)

    bet = engine.place_bet(
        agent_name="WinBot",
        market="polymarket",
        event="Event A",
        selection="Yes",
        odds=2.0,
        stake=10.0,
        expected_value=0.05,
    )
    assert bet is not None
    assert engine.agents["WinBot"].current_bankroll == 90.0

    # Settle Win
    settled = engine.settle_bet("WinBot", bet.id, won=True)
    assert settled.status == BetStatus.WON
    assert engine.agents["WinBot"].current_bankroll == 110.0
    assert settled.pnl == 10.0


def test_paper_engine_place_and_settle_loss():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    engine.create_agent("LossBot", 100.0)

    bet = engine.place_bet(
        agent_name="LossBot",
        market="polymarket",
        event="Event B",
        selection="No",
        odds=2.0,
        stake=10.0,
        expected_value=0.05,
    )
    assert engine.agents["LossBot"].current_bankroll == 90.0

    # Settle Loss
    settled = engine.settle_bet("LossBot", bet.id, won=False)
    assert settled.status == BetStatus.LOST
    assert engine.agents["LossBot"].current_bankroll == 90.0
    assert settled.pnl == -10.0


def test_circuit_breaker_aggressive_kill():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = engine.create_agent("RiskBot", 100.0, survival_mode=SurvivalMode.AGGRESSIVE)

    # Place 60$ bet and lose -> bankroll 40$ (< 50$)
    bet = engine.place_bet("RiskBot", "polymarket", "Event C", "Yes", 2.0, 60.0, 0.05)
    engine.settle_bet("RiskBot", bet.id, won=False)

    assert agent.is_alive is False
    assert "threshold" in agent.kill_reason.lower()


def test_bet_manager_kelly_sizing():
    bm = BetManager(SizingConfig(kelly_fraction=0.25, max_bet_pct=0.10))
    # True prob 60%, odds 2.0 -> b = 1, p = 0.6, q = 0.4 -> Kelly = 0.20 -> 0.25 Kelly = 0.05 (5%)
    stake = bm.calculate_kelly_stake(true_prob=0.60, decimal_odds=2.0, available_bankroll=100.0)
    assert stake == 5.0
