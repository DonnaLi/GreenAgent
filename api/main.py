from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api import service
from api.db import SessionLocal, Shipment, init_db
from api.schemas import ShipmentIn, ShipmentOut, StatsOut, WeightsIn, WeightsOut


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Green-Agent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


@app.get("/api/weights", response_model=WeightsOut)
def read_weights(db: DB):
    w = service.get_w_carbon(db)
    return WeightsOut(w_carbon=w, w_cost=round(1 - w, 4))


@app.put("/api/weights", response_model=WeightsOut)
def update_weights(body: WeightsIn, db: DB):
    w = service.set_w_carbon(db, body.w_carbon)
    return WeightsOut(w_carbon=w, w_cost=round(1 - w, 4))


@app.post("/api/shipments", response_model=ShipmentOut, status_code=201)
async def create_shipment(body: ShipmentIn, db: DB):
    return await service.create_shipment(db, body)


@app.get("/api/shipments", response_model=list[ShipmentOut])
def list_shipments(db: DB):
    return db.scalars(select(Shipment).order_by(Shipment.created_at.desc()).limit(50)).all()


def _get(db: Session, shipment_id: int) -> Shipment:
    shipment = db.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    return shipment


@app.post("/api/shipments/{shipment_id}/approve", response_model=ShipmentOut)
def approve(shipment_id: int, db: DB):
    shipment = _get(db, shipment_id)
    if shipment.status != "pending":
        raise HTTPException(409, f"Shipment is already {shipment.status}")
    return service.decide(db, shipment, approve=True)


@app.post("/api/shipments/{shipment_id}/reject", response_model=ShipmentOut)
def reject(shipment_id: int, db: DB):
    shipment = _get(db, shipment_id)
    if shipment.status != "pending":
        raise HTTPException(409, f"Shipment is already {shipment.status}")
    return service.decide(db, shipment, approve=False)


@app.get("/api/stats", response_model=StatsOut)
def stats(db: DB):
    counts = dict(db.execute(select(Shipment.status, func.count()).group_by(Shipment.status)).all())
    saved = db.scalar(
        select(func.coalesce(func.sum(Shipment.co2e_saved_kg), 0.0)).where(
            Shipment.status == "approved"
        )
    )
    return StatsOut(
        approved=counts.get("approved", 0),
        pending=counts.get("pending", 0),
        rejected=counts.get("rejected", 0),
        co2e_saved_kg=round(saved or 0.0, 1),
    )
