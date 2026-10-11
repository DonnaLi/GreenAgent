"""Where the carrier agents live: their seeds, addresses, and local endpoint.

Seeds are derived from AGENT_SEED_PREFIX so the API process can work out every
carrier's address without talking to them first. The default prefix is public
and only fit for local development.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from uagents.resolver import RulesBasedResolver
from uagents_core.identity import Identity
from uagents_core.registration import AgentRegistrationPolicy, BatchRegistrationPolicy

from agents.carriers import CARRIERS

load_dotenv()  # the carrier process doesn't import api/, so read .env here too

DEFAULT_SEED_PREFIX = "green-agent-dev"
DEFAULT_BUREAU_PORT = 8100
DEFAULT_BUYER_PORT = 8101


def seed_prefix() -> str:
    return os.getenv("AGENT_SEED_PREFIX", DEFAULT_SEED_PREFIX)


def carrier_seed(carrier_id: str) -> str:
    return f"{seed_prefix()}-carrier-{carrier_id}"


def buyer_seed() -> str:
    return f"{seed_prefix()}-buyer"


def bureau_port() -> int:
    return int(os.getenv("CARRIER_BUREAU_PORT", DEFAULT_BUREAU_PORT))


def bureau_endpoint() -> str:
    host = os.getenv("CARRIER_BUREAU_HOST", "127.0.0.1")
    return f"http://{host}:{bureau_port()}/submit"


def buyer_port() -> int:
    return int(os.getenv("BUYER_AGENT_PORT", DEFAULT_BUYER_PORT))


def buyer_endpoint() -> str:
    host = os.getenv("BUYER_AGENT_HOST", "127.0.0.1")
    return f"http://{host}:{buyer_port()}/submit"


def buyer_address() -> str:
    return Identity.from_seed(buyer_seed(), 0).address


def carrier_addresses() -> dict[str, str]:
    """carrier_id -> agent address."""
    return {c.carrier_id: Identity.from_seed(carrier_seed(c.carrier_id), 0).address
            for c in CARRIERS}


def agentverse_register() -> bool:
    """Register on the Almanac (needed for Agentverse) instead of local routing only."""
    return os.getenv("AGENTVERSE_REGISTER", "").strip().lower() in ("1", "true", "yes")


def carrier_resolver() -> RulesBasedResolver:
    """Lets carriers reach the buyer without an Almanac lookup."""
    return RulesBasedResolver({buyer_address(): buyer_endpoint()})


def buyer_resolver() -> RulesBasedResolver:
    """Lets the buyer reach every carrier without an Almanac lookup."""
    return RulesBasedResolver({addr: bureau_endpoint() for addr in carrier_addresses().values()})


class SkipAgentRegistration(AgentRegistrationPolicy):
    async def register(self, *args, **kwargs):
        pass


class SkipBatchRegistration(BatchRegistrationPolicy):
    async def register(self):
        pass

    def add_agent(self, agent_info, identity):
        pass
