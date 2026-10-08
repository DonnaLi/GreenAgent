from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class WeightsIn(BaseModel):
    w_carbon: float = Field(ge=0, le=1)


class WeightsOut(BaseModel):
    w_carbon: float
    w_cost: float


class ShipmentIn(BaseModel):
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)
    weight_kg: float = Field(gt=0, le=40000)
    deadline: date


class BidOut(BaseModel):
    carrier_id: str
    carrier_name: str
    mode: str
    price: float | None
    eta: datetime | None
    co2e_kg: float | None
    score: float | None
    norm_price: float | None
    norm_co2e: float | None
    rank: int | None
    excluded_reason: str | None

    model_config = {"from_attributes": True}


class ShipmentOut(BaseModel):
    id: int
    origin: str
    destination: str
    weight_kg: float
    deadline: datetime
    w_carbon: float
    status: str
    recommended_carrier: str | None
    rationale: str | None
    rationale_source: str
    co2e_saved_kg: float
    created_at: datetime
    bids: list[BidOut]

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    approved: int
    pending: int
    rejected: int
    co2e_saved_kg: float
