"""
Regression tests for settlement expected-value correctness and stake locking.

These cover two classes of bug:

1. Simulated settlement drew outcomes from the market implied probability
   while agents staked on their own forecast, forcing expected value to zero
   and making every backtest pure variance.
2. Stake was deducted from the bankroll on placement, so open positions looked
   like realised losses and could trip the survival circuit breaker.
"""
import pytest

from trading.paper_engine import PaperTradingEngine, SurvivalMode, BetStatus
from trading.settlement import SettlementEngine


def _run_series(true_prob, odds, n=4000, seed=11, edge_realisation=1.0):
    """Place and settle n independent flat-stake bets, return total PnL."""
    engine = PaperTradingEngine(initial_bankroll=100.0)
    engine.create_agent("EVBot", 1_000_000.0)
    settlement = SettlementEngine(engine, seed=seed)

    for _ in range(n):
        engine.place_bet(
            agent_name="EVBot",
            market="test",
            event="Event",
            selection="Yes",
            odds=odds,
            stake=10.0,
            expected_value=0.0,
            metadata={"true_prob": true_prob},
        )
        settlement.auto_simulate_pending_resolutions(
            edge_realisation=edge_realisation
        )

    agent = engine.agents["EVBot"]
    return agent.equity - agent.initial_bankroll


# ---------------------------------------------------------------- EV realism

def test_genuine_edge_produces_profit():
    """A forecast of 60% at even odds must actually make money."""
    pnl = _run_series(true_prob=0.60, odds=2.0)
    # Theoretical EV = 4000 * 10 * (0.6*2 - 1) = +8000
    assert pnl > 4000, f"real edge failed to produce profit (pnl={pnl})"


def test_negative_edge_produces_loss():
    """Backing a 40% shot at even odds must lose money."""
    pnl = _run_series(true_prob=0.40, odds=2.0)
    assert pnl < -4000, f"negative edge failed to produce loss (pnl={pnl})"


def test_no_edge_is_approximately_breakeven():
    """A forecast equal to the market price should drift around zero."""
    pnl = _run_series(true_prob=0.50, odds=2.0)
    assert abs(pnl) < 4000, f"zero-edge series drifted too far (pnl={pnl})"


def test_edge_realisation_zero_collapses_to_market():
    """edge_realisation=0 must ignore the forecast and price at the market."""
    pnl = _run_series(true_prob=0.60, odds=2.0, edge_realisation=0.0)
    assert abs(pnl) < 4000, (
        f"edge_realisation=0 should be a zero-edge world (pnl={pnl})"
    )


def test_ground_truth_overrides_agent_forecast():
    """An agent that claims an edge the world denies must lose."""
    engine = PaperTradingEngine(initial_bankroll=100.0)
    engine.create_agent("Deluded", 1_000_000.0)
    settlement = SettlementEngine(engine, seed=3)

    for _ in range(3000):
        engine.place_bet(
            "Deluded", "test", "Event", "Yes", 2.0, 10.0, 0.0,
            metadata={"true_prob": 0.90},   # wildly overconfident
        )
        settlement.auto_simulate_pending_resolutions(
            ground_truth={"Event": 0.35}    # reality
        )

    agent = engine.agents["Deluded"]
    assert agent.equity - agent.initial_bankroll < 0


def test_settlement_is_reproducible_with_seed():
    a = _run_series(true_prob=0.55, odds=2.0, n=500, seed=99)
    b = _run_series(true_prob=0.55, odds=2.0, n=500, seed=99)
    assert a == b


def test_missing_true_prob_falls_back_to_market():
    """Bets without forecast metadata must not crash settlement."""
    engine = PaperTradingEngine(initial_bankroll=100.0)
    engine.create_agent("Bare", 10_000.0)
    settlement = SettlementEngine(engine, seed=5)

    bet = engine.place_bet("Bare", "test", "E", "Yes", 2.0, 10.0, 0.0)
    settlement.auto_simulate_pending_resolutions()
    assert bet.status in (BetStatus.WON, BetStatus.LOST)


# ------------------------------------------------------- stake locking / equity

def test_open_bet_does_not_reduce_equity():
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = engine.create_agent("LockBot", 100.0)

    engine.place_bet("LockBot", "test", "E", "Yes", 2.0, 40.0, 0.0)

    assert agent.current_bankroll == 60.0   # cash is committed
    assert agent.locked_balance == 40.0
    assert agent.equity == 100.0            # but equity is untouched


def test_open_bet_does_not_trip_circuit_breaker():
    """
    A 60% stake must not kill an AGGRESSIVE agent (50% floor) while the bet is
    still pending. Only a realised loss should.
    """
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = engine.create_agent("RiskBot", 100.0, survival_mode=SurvivalMode.AGGRESSIVE)

    bet = engine.place_bet("RiskBot", "test", "E", "Yes", 2.0, 60.0, 0.0)
    agent.check_survival()
    assert agent.is_alive is True, "pending stake wrongly triggered the breaker"

    engine.settle_bet("RiskBot", bet.id, won=False)
    assert agent.is_alive is False, "realised loss should trigger the breaker"


def test_locked_balance_released_on_every_outcome():
    for kwargs in ({"won": True}, {"won": False},
                   {"won": False, "is_push": True},
                   {"won": False, "is_cancelled": True}):
        engine = PaperTradingEngine(initial_bankroll=100.0)
        agent = engine.create_agent("R", 100.0)
        bet = engine.place_bet("R", "test", "E", "Yes", 2.0, 10.0, 0.0)
        engine.settle_bet("R", bet.id, **kwargs)
        assert agent.locked_balance == 0.0, f"lock leaked for {kwargs}"
        assert agent.current_bankroll == agent.equity


def test_peak_and_drawdown_track_equity_not_default():
    """peak_bankroll must seed from actual bankroll, not the magic 100.0."""
    engine = PaperTradingEngine(initial_bankroll=100.0)
    agent = engine.create_agent("Big", 5000.0)
    assert agent.peak_bankroll == 5000.0
    assert agent.calculate_metrics()["current_drawdown"] == 0.0

    small = engine.create_agent("Small", 10.0)
    assert small.peak_bankroll == 10.0
    assert small.calculate_metrics()["current_drawdown"] == 0.0


# ------------------------------------------------- probability model integrity

def test_no_phantom_edge_from_volume_parity():
    """
    The mid-range branch of estimate_fair_probability used to return
    +2.5% or -1.5% based on whether int(volume_24h) was even -- pure noise
    that fabricated a tradable edge on half of all coin-flip markets.

    Two volumes differing by 1 must not produce different fair probabilities.
    """
    from analysis.probability_models import ProbabilityEstimator

    est = ProbabilityEstimator()
    for implied in (0.45, 0.50, 0.55):
        even = est.estimate_fair_probability(implied, volume_24h=100000.0)
        odd = est.estimate_fair_probability(implied, volume_24h=100001.0)
        assert even == odd, (
            f"volume parity still shifts the estimate at p={implied}: "
            f"{even} vs {odd}"
        )


def test_midrange_market_yields_no_claimed_edge():
    """An efficiently-priced coin-flip market must show ~zero edge."""
    from analysis.probability_models import ProbabilityEstimator

    est = ProbabilityEstimator()
    fair = est.estimate_fair_probability(0.50, volume_24h=250000.0)
    assert abs(fair - 0.50) < 1e-9


# ------------------------------------------------------- monte carlo variance

def test_monte_carlo_produces_real_dispersion():
    """
    Bootstrap reshuffling of rows carrying a frozen `result` column used to
    reorder the same wins and losses, so every iteration ended at an identical
    bankroll: std 0, ruin probability 0. Outcomes must be redrawn per bet.
    """
    from backtest.simulator import BacktestEngine
    from backtest.historical_data import HistoricalDataLoader

    df = HistoricalDataLoader.generate_synthetic_data(num_records=150)
    engine = BacktestEngine(initial_bankroll=100.0)

    def strategy(state, row):
        edge = row["true_prob"] - (1.0 / row["odds"])
        if edge > 0.02:
            b = row["odds"] - 1.0
            if b > 0:
                k = (b * row["true_prob"] - (1.0 - row["true_prob"])) / b
                return max(0.0, min(state["bankroll"] * k * 0.25,
                                    state["bankroll"] * 0.08))
        return 0.0

    mc = engine.monte_carlo_simulation(strategy, df, n_simulations=60, seed=42)
    assert mc["std_final_bankroll"] > 0.0, "Monte Carlo still has zero variance"
    assert mc["percentile_95th"] > mc["percentile_5th"]


def test_walk_forward_still_deterministic():
    """A plain backtest must keep replaying the fixed result column exactly."""
    from backtest.simulator import BacktestEngine
    from backtest.historical_data import HistoricalDataLoader

    df = HistoricalDataLoader.generate_synthetic_data(num_records=120)
    engine = BacktestEngine(initial_bankroll=100.0)

    def strategy(state, row):
        return 1.0

    a = engine.run_backtest(strategy, df)["final_bankroll"]
    b = engine.run_backtest(strategy, df)["final_bankroll"]
    assert a == b
