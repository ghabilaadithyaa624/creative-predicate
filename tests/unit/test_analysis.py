"""
Unit tests for Odds Analyzer and Probability Estimator.
"""
from analysis.odds_analyzer import OddsAnalyzer
from analysis.probability_models import ProbabilityEstimator


def test_odds_conversions():
    assert OddsAnalyzer.decimal_to_implied(2.0) == 0.5
    assert OddsAnalyzer.implied_to_decimal(0.5) == 2.0
    assert round(OddsAnalyzer.american_to_decimal(150), 2) == 2.5
    assert round(OddsAnalyzer.american_to_decimal(-200), 2) == 1.5


def test_expected_value_and_edge():
    # 55% true win prob at 2.0 odds
    ev = OddsAnalyzer.calculate_expected_value(true_probability=0.55, decimal_odds=2.0)
    assert round(ev, 2) == 0.10  # 10% expected return

    edge = OddsAnalyzer.calculate_edge(true_probability=0.55, decimal_odds=2.0)
    assert round(edge, 2) == 0.05  # 5% edge over 50% implied


def test_arbitrage_detection():
    # Book A: 2.10, Book B: 2.10 -> 1/2.10 + 1/2.10 = 0.952 < 1 -> Arbitrage exists!
    arb = OddsAnalyzer.detect_arbitrage(2.10, 2.10)
    assert arb["arbitrage_found"] is True
    assert arb["margin_percent"] > 4.0

    # Book A: 1.80, Book B: 1.80 -> 1/1.8 + 1/1.8 = 1.11 > 1 -> No arbitrage
    no_arb = OddsAnalyzer.detect_arbitrage(1.80, 1.80)
    assert no_arb["arbitrage_found"] is False


def test_vig_removal():
    # Overround odds: 1.90 and 1.90
    fair_probs = OddsAnalyzer.remove_vig_multiplicative([1.90, 1.90])
    assert len(fair_probs) == 2
    assert round(sum(fair_probs), 4) == 1.0
    assert round(fair_probs[0], 2) == 0.50
