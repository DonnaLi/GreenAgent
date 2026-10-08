"""The request loop: broadcast, collect bids, validate, score, explain, save."""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from agents.carriers import CARRIERS, RawBid, ShipmentRequest, request_bid
from api import rationale as rationale_mod
from api.db import Bid, Setting, Shipment
from api.schemas import ShipmentIn
from scoring import Bid as ScoringBid
from scoring import rank_bids
from scoring.engine import co2e_saved_vs_cheapest

BID_TIMEOUT_S = 2.0
DEFAULT_W_CARBON = 0.5


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_w_carbon(db: Session) -> float:
    row = db.get(Setting, "w_carbon")
    return float(row.value) if row else DEFAULT_W_CARBON


def set_w_carbon(db: Session, w_carbon: float) -> float:
    row = db.get(Setting, "w_carbon")
    if row:
        row.value = str(w_carbon)
    else:
        db.add(Setting(key="w_carbon", value=str(w_carbon)))
    db.commit()
    return w_carbon


async def collect_bids(
    req: ShipmentRequest, now: datetime, rng: random.Random, timeout_s: float = BID_TIMEOUT_S
) -> list[tuple[str, str, str, RawBid | None]]:
    """Ask every carrier at once; a carrier that misses the timeout returns None."""

    async def one(carrier):
        try:
            bid = await asyncio.wait_for(request_bid(carrier, req, now, rng), timeout_s)
        except TimeoutError:
            bid = None
        return carrier.carrier_id, carrier.name, carrier.mode, bid

    return await asyncio.gather(*(one(c) for c in CARRIERS))


async def create_shipment(
    db: Session, data: ShipmentIn, rng: random.Random | None = None
) -> Shipment:
    rng = rng or random.Random()
    now = utcnow()
    deadline = datetime.combine(data.deadline, time(23, 59))
    w_carbon = get_w_carbon(db)  # read at scoring time, so no restart needed (FR-5)

    req = ShipmentRequest(data.origin, data.destination, data.weight_kg, deadline)
    responses = await collect_bids(req, now, rng)

    shipment = Shipment(
        origin=data.origin,
        destination=data.destination,
        weight_kg=data.weight_kg,
        deadline=deadline,
        w_carbon=w_carbon,
        status="pending",
        created_at=now,
    )
    rows: dict[str, Bid] = {}
    valid: list[ScoringBid] = []
    for carrier_id, name, mode, raw in responses:
        row = Bid(carrier_id=carrier_id, carrier_name=name, mode=mode)
        if raw is None:
            row.excluded_reason = "No bid before the timeout"
        else:
            row.price, row.eta, row.co2e_kg = raw.price, raw.eta, raw.co2e_kg
            if raw.price is None or raw.eta is None or raw.co2e_kg is None:
                row.excluded_reason = "Bid was missing price, ETA, or CO2e"
            elif raw.eta > deadline:
                row.excluded_reason = "Delivery misses the deadline"
            else:
                valid.append(ScoringBid(carrier_id, raw.price, raw.eta, raw.co2e_kg))
        rows[carrier_id] = row

    ranked = rank_bids(valid, w_carbon=w_carbon, deadline=deadline)
    names = {cid: r.carrier_name for cid, r in rows.items()}
    for i, s in enumerate(ranked, start=1):
        r = rows[s.bid.carrier_id]
        r.score, r.norm_price, r.norm_co2e, r.rank = s.score, s.norm_price, s.norm_co2e, i

    if ranked:
        top = ranked[0].bid
        saved = co2e_saved_vs_cheapest([s.bid for s in ranked], top)
        shipment.recommended_carrier = top.carrier_id
        shipment.co2e_saved_kg = round(saved, 1)
        text = await rationale_mod.llm_rationale(ranked, names, w_carbon)
        shipment.rationale_source = "llm" if text else "template"
        shipment.rationale = text or rationale_mod.template_rationale(
            ranked, names, w_carbon, saved
        )
    else:
        shipment.status = "no_bids"
        shipment.rationale = "No carrier sent a valid bid that meets the deadline."

    # Ranked bids first, then excluded ones.
    shipment.bids = sorted(rows.values(), key=lambda r: (r.rank is None, r.rank or 0))
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment


def decide(db: Session, shipment: Shipment, approve: bool) -> Shipment:
    shipment.status = "approved" if approve else "rejected"
    db.commit()
    db.refresh(shipment)
    return shipment
