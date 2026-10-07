"""Composite scoring for carrier bids.

Each valid bid gets a score from 0 to 1 (lower is better):

    n_i = (x_i - min(x)) / (max(x) - min(x))     # per field, per bid set
    S_i = w_cost * n_price + w_carbon * n_co2e    # w_cost + w_carbon = 1

ETA is a hard filter: bids that miss the shipment deadline are excluded
before scoring. See docs/PRD.md, "Scoring algorithm".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Bid:
    carrier_id: str
    price: float  # shipment price in the request's currency
    eta: datetime  # promised delivery time
    co2e_kg: float  # estimated emissions for the shipment


@dataclass(frozen=True)
class ScoredBid:
    bid: Bid
    score: float  # 0 = best possible, 1 = worst possible
    norm_price: float
    norm_co2e: float


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]. Equal values all map to 0 (no divide-by-zero)."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def rank_bids(
    bids: list[Bid],
    w_carbon: float,
    deadline: datetime | None = None,
) -> list[ScoredBid]:
    """Rank bids best-first.

    w_carbon is the carbon weight in [0, 1]; the cost weight is 1 - w_carbon.
    Weights are passed in at call time, so changing them never requires
    restarting an agent.
    """
    if not 0.0 <= w_carbon <= 1.0:
        raise ValueError("w_carbon must be between 0 and 1")

    eligible = [b for b in bids if deadline is None or b.eta <= deadline]
    if not eligible:
        return []

    w_cost = 1.0 - w_carbon
    n_price = _normalize([b.price for b in eligible])
    n_co2e = _normalize([b.co2e_kg for b in eligible])

    scored = [
        ScoredBid(
            bid=b,
            score=w_cost * p + w_carbon * c,
            norm_price=p,
            norm_co2e=c,
        )
        for b, p, c in zip(eligible, n_price, n_co2e, strict=True)
    ]
    # Ties break on lower raw CO2e, then lower price, so results are deterministic.
    return sorted(scored, key=lambda s: (s.score, s.bid.co2e_kg, s.bid.price))


def co2e_saved_vs_cheapest(bids: list[Bid], chosen: Bid) -> float:
    """CO2e saved (kg) by the chosen bid versus the cheapest-option baseline."""
    cheapest = min(bids, key=lambda b: (b.price, b.co2e_kg))
    return cheapest.co2e_kg - chosen.co2e_kg
