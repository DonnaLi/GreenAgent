"""Mock carrier agents.

Each carrier answers a shipment request with a bid. They are plain async
functions for now so the request loop can be built and tested; swap them for
Fetch.ai uAgents later without changing the scoring or API layers.

Two carriers misbehave on purpose so the timeout and validation logic is
always exercised:
  - BlueWave sometimes answers slowly.
  - SwiftRoad sometimes leaves out its CO2e figure.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ShipmentRequest:
    origin: str
    destination: str
    weight_kg: float
    deadline: datetime


@dataclass(frozen=True)
class RawBid:
    """A bid as a carrier sent it. Fields may be missing (None)."""

    carrier_id: str
    carrier_name: str
    mode: str
    price: float | None
    eta: datetime | None
    co2e_kg: float | None


def _distance_km(origin: str, destination: str) -> float:
    """Stable fake distance between two places (300 to 3,000 km)."""
    key = f"{origin.strip().lower()}->{destination.strip().lower()}".encode()
    return 300 + int(hashlib.sha256(key).hexdigest(), 16) % 2700


@dataclass(frozen=True)
class CarrierProfile:
    carrier_id: str
    name: str
    mode: str
    price_per_tkm: float  # price per tonne-km
    co2e_per_tkm: float  # kg CO2e per tonne-km
    km_per_day: float
    slow_chance: float = 0.0
    missing_co2e_chance: float = 0.0


CARRIERS = [
    CarrierProfile("swiftroad", "SwiftRoad Logistics", "Truck", 0.11, 0.105, 800,
                   missing_co2e_chance=0.15),
    CarrierProfile("bluewave", "BlueWave Intermodal", "Truck + rail", 0.13, 0.062, 600,
                   slow_chance=0.2),
    CarrierProfile("northrail", "NorthRail Freight", "Rail", 0.15, 0.028, 450),
]


async def request_bid(
    carrier: CarrierProfile,
    req: ShipmentRequest,
    now: datetime,
    rng: random.Random,
    slow_delay_s: float = 5.0,
) -> RawBid:
    tonne_km = (req.weight_kg / 1000) * _distance_km(req.origin, req.destination)
    jitter = rng.uniform(0.9, 1.1)

    if rng.random() < carrier.slow_chance:
        await asyncio.sleep(slow_delay_s)
    else:
        await asyncio.sleep(rng.uniform(0.05, 0.4))

    days = max(1, round(_distance_km(req.origin, req.destination) / carrier.km_per_day))
    co2e = None if rng.random() < carrier.missing_co2e_chance else round(
        tonne_km * carrier.co2e_per_tkm * rng.uniform(0.95, 1.05), 1
    )
    return RawBid(
        carrier_id=carrier.carrier_id,
        carrier_name=carrier.name,
        mode=carrier.mode,
        price=round(max(150.0, tonne_km * carrier.price_per_tkm * jitter), 2),
        eta=now + timedelta(days=days),
        co2e_kg=co2e,
    )
