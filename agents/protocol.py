"""Messages the buyer and carrier agents exchange over uAgents."""

from __future__ import annotations

from datetime import datetime

from uagents import Model


class ShipmentRequestMsg(Model):
    request_id: str
    origin: str
    destination: str
    weight_kg: float
    deadline: datetime


class BidMsg(Model):
    """A carrier's reply. Fields may be missing, just like `RawBid`."""

    request_id: str
    carrier_id: str
    carrier_name: str
    mode: str
    price: float | None = None
    eta: datetime | None = None
    co2e_kg: float | None = None
