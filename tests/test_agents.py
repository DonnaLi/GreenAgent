"""Buyer and carrier agents talking over real uAgents messaging on localhost."""

import asyncio
import socket
from datetime import datetime, timedelta

import pytest

from agents import carrier_agents
from agents.buyer import BuyerAgent
from agents.carriers import CARRIERS, CarrierProfile, ShipmentRequest


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def ports(monkeypatch):
    monkeypatch.setenv("CARRIER_BUREAU_PORT", str(free_port()))
    monkeypatch.setenv("BUYER_AGENT_PORT", str(free_port()))
    monkeypatch.setenv("AGENT_SEED_PREFIX", "green-agent-test")
    monkeypatch.delenv("AGENTVERSE_REGISTER", raising=False)


def run_broadcast(req: ShipmentRequest, timeout_s: float):
    async def main():
        bureau = carrier_agents.make_bureau()
        bureau_task = asyncio.create_task(bureau._server.serve())
        for agent in bureau._agents:
            agent.setup()
        buyer = BuyerAgent()
        await buyer.start()
        await asyncio.sleep(0.5)  # let both servers bind
        try:
            return await buyer.broadcast(req, timeout_s)
        finally:
            await buyer.stop()
            bureau_task.cancel()
            await asyncio.gather(bureau_task, return_exceptions=True)

    return asyncio.run(main())


def test_every_carrier_bids_over_agent_messaging(ports, monkeypatch):
    honest = [CarrierProfile(c.carrier_id, c.name, c.mode, c.price_per_tkm,
                             c.co2e_per_tkm, c.km_per_day) for c in CARRIERS]
    monkeypatch.setattr(carrier_agents, "CARRIERS", honest)
    req = ShipmentRequest("Vancouver", "Calgary", 2000, datetime.now() + timedelta(days=30))

    bids = run_broadcast(req, timeout_s=2.0)

    assert set(bids) == {c.carrier_id for c in CARRIERS}
    for cid, bid in bids.items():
        assert bid is not None, f"{cid} did not bid"
        assert bid.carrier_id == cid
        assert bid.price and bid.eta and bid.co2e_kg


def test_slow_carrier_misses_timeout(ports, monkeypatch):
    slow = [CarrierProfile(c.carrier_id, c.name, c.mode, c.price_per_tkm, c.co2e_per_tkm,
                           c.km_per_day, slow_chance=1.0 if c.carrier_id == "bluewave" else 0.0)
            for c in CARRIERS]
    monkeypatch.setattr(carrier_agents, "CARRIERS", slow)
    req = ShipmentRequest("Vancouver", "Calgary", 2000, datetime.now() + timedelta(days=30))

    bids = run_broadcast(req, timeout_s=1.0)

    assert bids["bluewave"] is None
    assert all(bid is not None for cid, bid in bids.items() if cid != "bluewave")
