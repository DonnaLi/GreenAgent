"""Mock carrier agents.

Each carrier answers a shipment request with a bid. The bid logic lives here
so both transports share it: `request_bid` calls it in-process (the default,
used by tests and CI), and `agents/carrier_agents.py` wraps it in Fetch.ai
uAgents that answer over agent messaging.

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
    CarrierProfile("voltline", "VoltLine Electric", "Electric truck", 0.14, 0.040, 700),
    CarrierProfile("harbourlink", "HarbourLink Shortsea", "Short-sea + truck", 0.12, 0.070, 350),
]


def response_delay(carrier: CarrierProfile, rng: random.Random, slow_delay_s: float = 5.0) -> float:
    """How long the carrier takes to answer, in seconds."""
    if rng.random() < carrier.slow_chance:
        return slow_delay_s
    return rng.uniform(0.05, 0.4)


def make_bid(
    carrier: CarrierProfile, req: ShipmentRequest, now: datetime, rng: random.Random
) -> RawBid:
    distance = _distance_km(req.origin, req.destination)
    tonne_km = (req.weight_kg / 1000) * distance
    days = max(1, round(distance / carrier.km_per_day))
    co2e = None if rng.random() < carrier.missing_co2e_chance else round(
        tonne_km * carrier.co2e_per_tkm * rng.uniform(0.95, 1.05), 1
    )
    return RawBid(
        carrier_id=carrier.carrier_id,
        carrier_name=carrier.name,
        mode=carrier.mode,
        price=round(max(150.0, tonne_km * carrier.price_per_tkm * rng.uniform(0.9, 1.1)), 2),
        eta=now + timedelta(days=days),
        co2e_kg=co2e,
    )


async def request_bid(
    carrier: CarrierProfile,
    req: ShipmentRequest,
    now: datetime,
    rng: random.Random,
    slow_delay_s: float = 5.0,
) -> RawBid:
    await asyncio.sleep(response_delay(carrier, rng, slow_delay_s))
    return make_bid(carrier, req, now, rng)
