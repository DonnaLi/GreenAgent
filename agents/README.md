# agents

The buyer agent and five mock carrier agents, built on [Fetch.ai uAgents](https://uagents.fetch.ai/docs).

## Decision: uAgents, routed locally for now

The PRD left open whether carriers should be Fetch.ai uAgents over Agentverse or
async FastAPI services. We went with **uAgents**: bids travel as signed agent
messages, carriers have real agent addresses, and moving to Agentverse later is
a configuration change rather than a rewrite.

For development the agents skip Almanac registration and reach each other
directly on localhost, so nothing needs testnet funds, an Agentverse account,
or internet access. The in-process transport (plain async functions) is still
the default so tests and CI stay fast and deterministic.

## Files

| File | What it is |
| --- | --- |
| `carriers.py` | Carrier profiles and the bid logic both transports share |
| `protocol.py` | `ShipmentRequestMsg` and `BidMsg`, the messages agents exchange |
| `carrier_agents.py` | Wraps each carrier as a uAgent; runs them all in one Bureau |
| `buyer.py` | Buyer agent: broadcasts a request (FR-1) and collects bids until the timeout |
| `directory.py` | Seeds, addresses, ports, and local routing for every agent |

## Carriers

| Carrier | Mode | Price | CO2e | Speed | Misbehaves |
| --- | --- | --- | --- | --- | --- |
| SwiftRoad Logistics | Truck | lowest | highest | fast | leaves out CO2e 15% of the time |
| HarbourLink Shortsea | Short-sea + truck | low | high | slowest | |
| BlueWave Intermodal | Truck + rail | mid | mid | mid | answers too late 20% of the time |
| VoltLine Electric | Electric truck | high | low | fast | |
| NorthRail Freight | Rail | highest | lowest | slow | |

Each carrier sits on the cost/carbon trade-off curve, so min-max scores
spread out instead of swinging between two or three points.

## Run the agents

Use the same virtualenv as the API (`pip install -r requirements.txt`).

**Terminal 1, the carriers** (all five in one process on port 8100):

```bash
python -m agents.carrier_agents
```

**Terminal 2, the API with the buyer agent** (buyer listens on port 8101):

```bash
CARRIER_TRANSPORT=uagents uvicorn api.main:app --reload
```

Then send a shipment from the dashboard, or:

```bash
curl -X POST localhost:8000/api/shipments -H 'content-type: application/json' \
  -d '{"origin":"Vancouver","destination":"Toronto","weight_kg":5000,"deadline":"2026-12-01"}'
```

Leave `CARRIER_TRANSPORT` unset (or `local`) to call the carriers in-process
with no agents running.

## How a request flows

1. The API calls `BuyerAgent.broadcast`, which sends one `ShipmentRequestMsg`
   with a fresh `request_id` to every carrier address at once.
2. Each carrier waits its response delay, builds a bid with `make_bid`, and
   replies with a `BidMsg` carrying the same `request_id`.
3. The buyer matches each reply by `request_id` and the sender's address, and
   ignores bids from unknown agents or for requests that already closed.
4. After 2 seconds (`BID_TIMEOUT_S` in `api/service.py`) any carrier that has
   not replied counts as no bid. The request loop stores the reason on the
   bid row and logs it, for example
   `WARNING:api.service:Excluded bluewave: No bid before the timeout`.

## Settings

| Variable | Default | Does |
| --- | --- | --- |
| `CARRIER_TRANSPORT` | `local` | `uagents` to message the carrier agents |
| `CARRIER_BUREAU_HOST` / `CARRIER_BUREAU_PORT` | `127.0.0.1` / `8100` | Where the carriers listen |
| `BUYER_AGENT_HOST` / `BUYER_AGENT_PORT` | `127.0.0.1` / `8101` | Where the buyer listens for bids |
| `AGENT_SEED_PREFIX` | `green-agent-dev` | Seeds every agent's key; both processes must match |
| `AGENTVERSE_REGISTER` | off | `1` to register on the Almanac instead of local routing only |

The default seed prefix is public, so anyone can derive those agent keys. Set
your own `AGENT_SEED_PREFIX` before running agents anywhere but your laptop.

## Next: Agentverse

Set `AGENTVERSE_REGISTER=1`, a private `AGENT_SEED_PREFIX`, and public
endpoints (or a mailbox) for both processes. Carriers then register on the
Almanac and the buyer can resolve them there instead of through
`directory.buyer_resolver()`. Not tested yet.
