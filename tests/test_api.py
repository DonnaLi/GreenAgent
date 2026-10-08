import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import db as db_mod
from api import main, service
from api.schemas import ShipmentIn


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db_mod.Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(main, "init_db", lambda: None)
    main.app.dependency_overrides[main.get_db] = override

    real_create = service.create_shipment

    async def seeded(db, data, rng=None):
        return await real_create(db, data, rng=random.Random(7))

    monkeypatch.setattr(service, "create_shipment", seeded)
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def far_deadline() -> str:
    return (date.today() + timedelta(days=30)).isoformat()


def test_weights_round_trip(client):
    assert client.get("/api/weights").json()["w_carbon"] == 0.5
    r = client.put("/api/weights", json={"w_carbon": 0.8})
    assert r.json() == {"w_carbon": 0.8, "w_cost": 0.2}


def test_invalid_weight_rejected(client):
    assert client.put("/api/weights", json={"w_carbon": 1.5}).status_code == 422


def test_request_returns_ranked_bids_and_rationale(client):
    r = client.post(
        "/api/shipments",
        json={"origin": "Vancouver", "destination": "Calgary",
              "weight_kg": 2000, "deadline": far_deadline()},
    )
    assert r.status_code == 201
    body = r.json()
    ranked = [b for b in body["bids"] if b["rank"] is not None]
    assert ranked, "expected at least one valid bid"
    assert [b["rank"] for b in ranked] == list(range(1, len(ranked) + 1))
    assert body["recommended_carrier"] == ranked[0]["carrier_id"]
    assert body["rationale"] and body["rationale_source"] == "template"
    assert len(body["bids"]) == 3  # excluded bids are kept for the audit trail


def test_approve_then_stats(client):
    s = client.post(
        "/api/shipments",
        json={"origin": "Vancouver", "destination": "Toronto",
              "weight_kg": 5000, "deadline": far_deadline()},
    ).json()
    assert client.post(f"/api/shipments/{s['id']}/approve").json()["status"] == "approved"
    assert client.post(f"/api/shipments/{s['id']}/approve").status_code == 409
    stats = client.get("/api/stats").json()
    assert stats["approved"] == 1
    assert stats["co2e_saved_kg"] == s["co2e_saved_kg"]


def test_late_carriers_are_excluded():
    """With a deadline today, every carrier's ETA is too late."""
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    db_mod.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    import asyncio

    data = ShipmentIn(origin="A", destination="B", weight_kg=100,
                      deadline=date.today() - timedelta(days=1))
    shipment = asyncio.run(service.create_shipment(db, data, rng=random.Random(1)))
    assert shipment.status == "no_bids"
    assert all(b.rank is None for b in shipment.bids)


def test_excluded_bids_listed_after_ranked(client):
    s = client.post(
        "/api/shipments",
        json={"origin": "Vancouver", "destination": "Calgary",
              "weight_kg": 2000, "deadline": far_deadline()},
    ).json()
    listed = client.get("/api/shipments").json()[0]["bids"]
    ranks = [b["rank"] for b in listed]
    seen_none = False
    for r in ranks:
        if r is None:
            seen_none = True
        else:
            assert not seen_none, f"ranked bid after an excluded one: {ranks}"
    assert listed[0]["carrier_id"] == s["recommended_carrier"]
