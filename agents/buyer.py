"""The buyer agent: broadcasts a shipment request to every carrier agent.

It runs inside the API process on its own port (BUYER_AGENT_PORT, default
8101), so carriers can send their bids back to it as ordinary uAgents
messages. Each broadcast gets a request_id; a bid is matched to its request by
that id and by the sending carrier's address. A carrier that does not reply
within the timeout gets None, which the request loop logs as an exclusion.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from uagents import Agent, Context
from uagents.communication import send_message
from uagents_core.types import DeliveryStatus, MsgStatus

from agents import directory
from agents.carriers import CARRIERS, RawBid, ShipmentRequest
from agents.protocol import BidMsg, ShipmentRequestMsg

log = logging.getLogger(__name__)


class BuyerAgent:
    def __init__(self):
        self.carrier_addresses = directory.carrier_addresses()
        self._carrier_by_address = {a: cid for cid, a in self.carrier_addresses.items()}
        self._resolver = directory.buyer_resolver()
        self._pending: dict[tuple[str, str], asyncio.Future] = {}
        self._server_task: asyncio.Task | None = None
        self.agent = Agent(
            name="buyer",
            seed=directory.buyer_seed(),
            port=directory.buyer_port(),
            endpoint=directory.buyer_endpoint(),
            network="testnet",
            resolve=self._resolver,
            registration_policy=None
            if directory.agentverse_register()
            else directory.SkipAgentRegistration(),
            loop=asyncio.get_running_loop(),
            enable_agent_inspector=False,
            publish_agent_details=False,
            report_events=False,
        )
        self.agent.on_message(model=BidMsg)(self._on_bid)

    @property
    def address(self) -> str:
        return self.agent.address

    async def start(self) -> None:
        """Start receiving bids. Call from inside the running event loop."""
        self.agent.setup()
        self._server_task = asyncio.create_task(self.agent.start_server())
        log.info("Buyer agent %s listening on %s", self.address, directory.buyer_endpoint())

    async def stop(self) -> None:
        if self._server_task:
            self._server_task.cancel()
            await asyncio.gather(self._server_task, return_exceptions=True)

    async def _on_bid(self, ctx: Context, sender: str, msg: BidMsg):
        carrier_id = self._carrier_by_address.get(sender)
        if carrier_id is None or carrier_id != msg.carrier_id:
            log.warning("Ignoring bid from unknown or mismatched sender %s", sender)
            return
        fut = self._pending.get((msg.request_id, carrier_id))
        if fut is None or fut.done():
            log.info("Late bid from %s for request %s", carrier_id, msg.request_id)
            return
        fut.set_result(
            RawBid(msg.carrier_id, msg.carrier_name, msg.mode, msg.price, msg.eta, msg.co2e_kg)
        )

    async def broadcast(
        self, req: ShipmentRequest, timeout_s: float
    ) -> dict[str, RawBid | None]:
        """carrier_id -> bid, or None if the carrier missed the timeout."""
        loop = asyncio.get_running_loop()
        request_id = uuid.uuid4().hex
        msg = ShipmentRequestMsg(
            request_id=request_id,
            origin=req.origin,
            destination=req.destination,
            weight_kg=req.weight_kg,
            deadline=req.deadline,
        )
        ids = [c.carrier_id for c in CARRIERS]
        futures = {cid: loop.create_future() for cid in ids}
        for cid, fut in futures.items():
            self._pending[(request_id, cid)] = fut

        async def ask(cid: str):
            status = await send_message(
                self.carrier_addresses[cid], msg, sender=self.agent._identity,
                resolver=self._resolver,
            )
            if isinstance(status, MsgStatus) and status.status == DeliveryStatus.FAILED:
                log.warning("Could not reach carrier %s: %s", cid, status.detail)

        try:
            sends = [asyncio.create_task(ask(cid)) for cid in ids]
            await asyncio.wait(futures.values(), timeout=timeout_s)
            for task in sends:
                task.cancel()
            return {cid: fut.result() if fut.done() else None for cid, fut in futures.items()}
        finally:
            for cid in ids:
                self._pending.pop((request_id, cid), None)
