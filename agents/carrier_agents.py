"""The mock carriers as Fetch.ai uAgents.

Run all of them in one Bureau (one port, one process):

    python -m agents.carrier_agents

Each agent answers a ShipmentRequestMsg with a BidMsg built by the same
`make_bid` the in-process transport uses, after the same response delay, so
BlueWave can still miss the buyer's timeout and SwiftRoad can still leave out
its CO2e.
"""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime

from uagents import Agent, Bureau, Context

from agents import directory
from agents.carriers import CARRIERS, CarrierProfile, ShipmentRequest, make_bid, response_delay
from agents.protocol import BidMsg, ShipmentRequestMsg


def make_carrier_agent(carrier: CarrierProfile, rng: random.Random | None = None) -> Agent:
    rng = rng or random.Random()
    agent = Agent(
        name=carrier.carrier_id,
        seed=directory.carrier_seed(carrier.carrier_id),
        network="testnet",
        resolve=directory.carrier_resolver(),
        handle_messages_concurrently=True,  # a slow reply must not hold up the next request
        enable_agent_inspector=False,
        publish_agent_details=False,
        report_events=False,
    )

    @agent.on_message(model=ShipmentRequestMsg, replies=BidMsg)
    async def on_request(ctx: Context, sender: str, msg: ShipmentRequestMsg):
        await asyncio.sleep(response_delay(carrier, rng))
        req = ShipmentRequest(msg.origin, msg.destination, msg.weight_kg, msg.deadline)
        now = datetime.now(UTC).replace(tzinfo=None)
        bid = make_bid(carrier, req, now, rng)
        ctx.logger.info(f"Bid {bid.price} for {msg.origin} -> {msg.destination}")
        await ctx.send(sender, BidMsg(request_id=msg.request_id, **bid.__dict__))

    return agent


def make_bureau() -> Bureau:
    bureau = Bureau(
        port=directory.bureau_port(),
        endpoint=directory.bureau_endpoint(),
        registration_policy=None
        if directory.agentverse_register()
        else directory.SkipBatchRegistration(),
    )
    for carrier in CARRIERS:
        bureau.add(make_carrier_agent(carrier))
    return bureau


if __name__ == "__main__":
    make_bureau().run()
