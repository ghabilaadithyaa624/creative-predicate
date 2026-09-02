"""
Tests for the live Polymarket feed parser.

Context: this parsing path had never once been exercised against a real
payload. The Gamma API returns `outcomePrices` as a JSON-encoded *string*
(e.g. '["0.945", "0.055"]'), not a list. The original code did
`float(prices[0])`, which indexes the character '[' and raises, and the
handler substituted a fabricated 2.00/2.00 (50/50) price while still
tagging the market source="polymarket".

A market genuinely priced at 94.5% was therefore presented to the agent as a
coin flip -- a 44.5 percentage-point error indistinguishable from real data.
"""
import json
from unittest.mock import patch

import pytest

from backend.analysis.scraper import MarketScraper


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


# Shape mirrors a real gamma-api.polymarket.com/events response.
REAL_PAYLOAD = [
    {
        "id": "12735",
        "slug": "fed-decision-in-september",
        "title": "Fed decision in September?",
        "endDate": "2026-09-17T12:00:00Z",
        "volume": 48213945.72,
        "markets": [
            {
                "id": "253591",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.945", "0.055"]',
                "volume": "31882910.4",
            }
        ],
    },
    {
        "id": "14001",
        "slug": "btc-150k-2026",
        "title": "Will Bitcoin hit $150,000 in 2026?",
        "endDate": "2026-12-31T23:59:00Z",
        "volume": 9120334.11,
        "markets": [
            {
                "id": "260114",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.31", "0.69"]',
            }
        ],
    },
]


# ----------------------------------------------------- outcomePrices parsing

@pytest.mark.parametrize(
    "raw,expected",
    [
        ('["0.945", "0.055"]', [0.945, 0.055]),   # the real wire format
        (["0.945", "0.055"], [0.945, 0.055]),     # list of strings
        ([0.6, 0.4], [0.6, 0.4]),                 # list of floats
    ],
)
def test_parses_valid_price_shapes(raw, expected):
    assert MarketScraper._parse_outcome_prices(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        '["0.9",',           # malformed JSON
        '["0.5"]',           # single outcome
        '["abc", "def"]',    # non-numeric
        '["1.0", "0.0"]',    # already resolved
        '["0.0", "1.0"]',    # zero price -> infinite odds
        '["0.20", "0.20"]',  # prices do not complete
    ],
)
def test_rejects_unusable_prices(raw):
    """Anything unreadable must return None so the market is skipped."""
    assert MarketScraper._parse_outcome_prices(raw) is None


# --------------------------------------------------------- end-to-end parsing

def test_real_payload_prices_are_exact():
    """The regression: 0.945 must not become a 50/50 coin flip."""
    with patch("backend.analysis.scraper.requests.get",
               return_value=_FakeResponse(REAL_PAYLOAD)):
        markets = MarketScraper().scrape_polymarket()

    assert len(markets) == 2
    fed = markets[0]
    assert fed.source == "polymarket"
    # 1 / 0.945 == 1.0582...
    assert fed.odds_home == pytest.approx(1.0582, abs=1e-3)
    assert fed.odds_away == pytest.approx(18.1818, abs=1e-3)
    # Implied probability must round-trip to the true market price.
    assert (1.0 / fed.odds_home) == pytest.approx(0.945, abs=1e-4)
    assert fed.extra_metadata["yes_price"] == 0.945


def test_never_emits_fabricated_even_odds_for_real_source():
    """
    The old failure mode: unreadable prices became 2.00/2.00 but kept
    source="polymarket". A market must be skipped, not invented.
    """
    broken = [
        {
            "title": "Unreadable market",
            "markets": [{"id": "1", "outcomePrices": "not-json"}],
        }
    ]
    with patch("backend.analysis.scraper.requests.get",
               return_value=_FakeResponse(broken)):
        markets = MarketScraper().scrape_polymarket(allow_synthetic_fallback=False)

    assert markets == []


def test_mixed_payload_keeps_good_skips_bad():
    payload = json.loads(json.dumps(REAL_PAYLOAD))
    payload.append({
        "title": "Broken one",
        "markets": [{"id": "9", "outcomePrices": '["1.0", "0.0"]'}],
    })

    with patch("backend.analysis.scraper.requests.get",
               return_value=_FakeResponse(payload)):
        markets = MarketScraper().scrape_polymarket(allow_synthetic_fallback=False)

    assert [m.event_name for m in markets] == [
        "Fed decision in September?",
        "Will Bitcoin hit $150,000 in 2026?",
    ]


def test_volume_falls_back_to_inner_market():
    payload = [{
        "title": "No outer volume",
        "markets": [{"id": "1", "outcomePrices": '["0.5", "0.5"]',
                     "volume": "12345.6"}],
    }]
    with patch("backend.analysis.scraper.requests.get",
               return_value=_FakeResponse(payload)):
        markets = MarketScraper().scrape_polymarket(allow_synthetic_fallback=False)

    assert markets[0].volume == pytest.approx(12345.6)


# ------------------------------------------------------------------ fallback

def test_fallback_is_labelled_as_simulated():
    """Synthetic markets must be distinguishable from real ones."""
    with patch("backend.analysis.scraper.requests.get",
               side_effect=OSError("network unreachable")):
        markets = MarketScraper().scrape_polymarket()

    assert markets, "fallback should still produce a demo feed"
    assert all(m.source == "polymarket_simulated" for m in markets)


def test_fallback_can_be_disabled():
    with patch("backend.analysis.scraper.requests.get",
               side_effect=OSError("network unreachable")):
        markets = MarketScraper().scrape_polymarket(allow_synthetic_fallback=False)

    assert markets == []


def test_non_200_does_not_raise():
    with patch("backend.analysis.scraper.requests.get",
               return_value=_FakeResponse([], status_code=503)):
        markets = MarketScraper().scrape_polymarket(allow_synthetic_fallback=False)

    assert markets == []
