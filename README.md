# Green-Agent

Green-Agent helps shippers pick a freight carrier on cost **and** carbon. Carrier agents bid price, ETA, and CO2e on each shipment, a scoring engine ranks them with shipper-set weights, and an LLM explains the pick before the shipper approves it.

## How it works

1. The dashboard sends a shipment request with the current cost/carbon weights.
2. The buyer agent broadcasts it to carrier agents, which return price, ETA, and CO2e bids.
3. Bids that miss the deadline are dropped; the rest are min-max normalized and scored.
4. An LLM writes a plain-language rationale for the top bid.
5. The shipper approves or rejects, and the dashboard tracks CO2e saved versus the cheapest option.

## Tech stack

Python · FastAPI · PostgreSQL · Fetch.ai uAgents · React · LLM API

## Project structure

```
scoring/   ranking logic (pure Python)
agents/    buyer + carrier agents
api/       FastAPI backend + database models
web/       React dashboard
tests/     pytest suites
docs/      PRD and architecture diagram
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys
docker compose up -d          # starts PostgreSQL
pytest                        # runs the scoring tests
```

## Status

- [x] Scoring engine with tests
- [ ] Data model
- [ ] Mock carrier agents
- [ ] Request loop
- [ ] LLM rationale
- [ ] Dashboard
- [ ] Real emissions data
