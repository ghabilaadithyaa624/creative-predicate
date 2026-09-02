"""
Standalone test runner for autonomous trading agent test suite.
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.unit.test_agents import (
    test_polymarket_agent_cycle,
    test_sports_agent_cycle,
)
from tests.unit.test_analysis import (
    test_arbitrage_detection,
    test_expected_value_and_edge,
    test_odds_conversions,
    test_vig_removal,
)
from tests.unit.test_backtest import (
    test_backtest_execution,
    test_monte_carlo_execution,
)
from tests.unit.test_institutional import (
    test_advanced_position_sizing,
    test_blockchain_consensus_and_bft,
    test_feeds_and_arbitrage,
    test_monte_carlo_extreme_risk,
    test_reinforcement_learning_env_and_ppo,
    test_sentiment_and_ensemble,
    test_swarm_coordinator,
)
from tests.unit.test_quantum_neuromorphic import (
    test_federated_shamir_and_fedavg,
    test_neuromorphic_lif_and_reservoir,
    test_quantum_machine_learning,
    test_quantum_portfolio_optimization,
)
from tests.unit.test_settlement import (
    test_edge_realisation_zero_collapses_to_market,
    test_genuine_edge_produces_profit,
    test_ground_truth_overrides_agent_forecast,
    test_locked_balance_released_on_every_outcome,
    test_midrange_market_yields_no_claimed_edge,
    test_missing_true_prob_falls_back_to_market,
    test_monte_carlo_produces_real_dispersion,
    test_negative_edge_produces_loss,
    test_no_edge_is_approximately_breakeven,
    test_no_phantom_edge_from_volume_parity,
    test_open_bet_does_not_reduce_equity,
    test_open_bet_does_not_trip_circuit_breaker,
    test_peak_and_drawdown_track_equity_not_default,
    test_settlement_is_reproducible_with_seed,
    test_walk_forward_still_deterministic,
)
from tests.unit.test_trading import (
    test_bet_manager_kelly_sizing,
    test_circuit_breaker_aggressive_kill,
    test_paper_engine_create_agent,
    test_paper_engine_place_and_settle_loss,
    test_paper_engine_place_and_settle_win,
)


def run_all_tests():
    sync_tests = [
        ("Trading: Create Agent", test_paper_engine_create_agent),
        ("Trading: Place & Settle Win", test_paper_engine_place_and_settle_win),
        ("Trading: Place & Settle Loss", test_paper_engine_place_and_settle_loss),
        ("Trading: Circuit Breaker Kill", test_circuit_breaker_aggressive_kill),
        ("Trading: Kelly Bet Sizing", test_bet_manager_kelly_sizing),
        ("Analysis: Odds Conversions", test_odds_conversions),
        ("Analysis: EV and Edge Calculation", test_expected_value_and_edge),
        ("Analysis: Arbitrage Detection", test_arbitrage_detection),
        ("Analysis: Vig Removal", test_vig_removal),
        ("Backtest: Walk-forward Simulation", test_backtest_execution),
        ("Backtest: Monte Carlo Simulation", test_monte_carlo_execution),
        ("Settlement: Genuine Edge Is Profitable", test_genuine_edge_produces_profit),
        ("Settlement: Negative Edge Loses", test_negative_edge_produces_loss),
        ("Settlement: Zero Edge Is Breakeven", test_no_edge_is_approximately_breakeven),
        ("Settlement: Edge Realisation Dial", test_edge_realisation_zero_collapses_to_market),
        ("Settlement: Ground Truth Overrides Forecast", test_ground_truth_overrides_agent_forecast),
        ("Settlement: Seeded Reproducibility", test_settlement_is_reproducible_with_seed),
        ("Settlement: Missing Forecast Fallback", test_missing_true_prob_falls_back_to_market),
        ("Ledger: Open Bet Preserves Equity", test_open_bet_does_not_reduce_equity),
        ("Ledger: Pending Stake Spares Breaker", test_open_bet_does_not_trip_circuit_breaker),
        ("Ledger: Lock Released On All Outcomes", test_locked_balance_released_on_every_outcome),
        ("Ledger: Peak Seeds From Real Bankroll", test_peak_and_drawdown_track_equity_not_default),
        ("Model: No Phantom Volume-Parity Edge", test_no_phantom_edge_from_volume_parity),
        ("Model: Efficient Market Claims No Edge", test_midrange_market_yields_no_claimed_edge),
        ("Backtest: Monte Carlo Has Real Variance", test_monte_carlo_produces_real_dispersion),
        ("Backtest: Walk-Forward Deterministic", test_walk_forward_still_deterministic),
        ("ML Models: Sentiment & Ensemble", test_sentiment_and_ensemble),
        ("Risk: Advanced Sizing (Optimal f, Kelly)", test_advanced_position_sizing),
        ("RL: Trading Environment & PPO", test_reinforcement_learning_env_and_ppo),
        ("Monte Carlo: Extreme Risk & VaR/CVaR", test_monte_carlo_extreme_risk),
        ("Blockchain: Consensus & BFT Voting", test_blockchain_consensus_and_bft),
        ("Quantum: QAOA Portfolio Optimization", test_quantum_portfolio_optimization),
        ("Quantum: VQC Machine Learning Forward", test_quantum_machine_learning),
        ("Federated: Shamir Secret Sharing & FedAvg", test_federated_shamir_and_fedavg),
        ("Neuromorphic: LIF Spikes & Reservoir ESN", test_neuromorphic_lif_and_reservoir),
    ]

    async_tests = [
        ("Agents: Polymarket Autonomous Cycle", test_polymarket_agent_cycle),
        ("Agents: Sports Autonomous Cycle", test_sports_agent_cycle),
        ("Swarm: Coordinator & Consensus", test_swarm_coordinator),
        ("Feeds: Live Stream & Arbitrage", test_feeds_and_arbitrage),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("      AUTONOMOUS TRADING AGENT TEST SUITE      ")
    print("=" * 60)

    for name, fn in sync_tests:
        try:
            fn()
            print(f" [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f" [FAIL] {name}: {e}")
            failed += 1

    for name, afn in async_tests:
        try:
            asyncio.run(afn())
            print(f" [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f" [FAIL] {name}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} PASSED | {failed} FAILED")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
