from datetime import UTC, datetime, timedelta

import pytest

from scoring import Bid, rank_bids
from scoring.engine import co2e_saved_vs_cheapest

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

CHEAP_DIRTY = Bid("cheap", price=500, eta=NOW + timedelta(days=3), co2e_kg=120)
MID = Bid("mid", price=650, eta=NOW + timedelta(days=2), co2e_kg=80)
PRICEY_GREEN = Bid("green", price=800, eta=NOW + timedelta(days=4), co2e_kg=40)
BIDS = [CHEAP_DIRTY, MID, PRICEY_GREEN]


def ids(ranked):
    return [s.bid.carrier_id for s in ranked]


def test_cost_only_picks_cheapest():
    assert ids(rank_bids(BIDS, w_carbon=0.0))[0] == "cheap"


def test_carbon_only_picks_greenest():
    assert ids(rank_bids(BIDS, w_carbon=1.0))[0] == "green"


def test_scores_stay_between_zero_and_one():
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        for s in rank_bids(BIDS, w_carbon=w):
            assert 0.0 <= s.score <= 1.0


def test_equal_values_do_not_divide_by_zero():
    same = [Bid(f"c{i}", price=500, eta=NOW, co2e_kg=50) for i in range(3)]
    ranked = rank_bids(same, w_carbon=0.5)
    assert all(s.score == 0.0 for s in ranked)


def test_deadline_filters_late_bids():
    ranked = rank_bids(BIDS, w_carbon=1.0, deadline=NOW + timedelta(days=3))
    assert "green" not in ids(ranked)  # arrives in 4 days, misses deadline


def test_no_eligible_bids_returns_empty():
    assert rank_bids(BIDS, w_carbon=0.5, deadline=NOW) == []


def test_invalid_weight_raises():
    with pytest.raises(ValueError):
        rank_bids(BIDS, w_carbon=1.5)


def test_co2e_saved_against_cheapest():
    assert co2e_saved_vs_cheapest(BIDS, PRICEY_GREEN) == 80
