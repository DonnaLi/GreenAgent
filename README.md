# Green-Agent

![CI](https://github.com/DonnaLi/GreenAgent/actions/workflows/ci.yml/badge.svg)

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

You need Python 3.11+ and Node 18+.

**Backend** (terminal 1):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # optional: add LLM_API_KEY for AI-written explanations
uvicorn api.main:app --reload     # API on http://localhost:8000, docs at /docs
```

Uses SQLite by default. To use PostgreSQL instead, run `docker compose up -d`
and keep the `DATABASE_URL` from `.env.example`.

**Dashboard** (terminal 2):

```bash
cd web
npm install
npm run dev                       # open http://localhost:5173
```

**Tests:** `pytest`

## API

| Method | Path | Does |
| --- | --- | --- |
| GET / PUT | `/api/weights` | Read or set the carbon weight (0 to 1) |
| POST | `/api/shipments` | Collect bids, score them, and recommend a carrier |
| GET | `/api/shipments` | List recent shipments with their bids |
| POST | `/api/shipments/{id}/approve` | Approve the recommendation |
| POST | `/api/shipments/{id}/reject` | Reject the recommendation |
| GET | `/api/stats` | Approved count and total CO2e saved |

## Status

- [x] Scoring engine with tests
- [x] Data model (SQLite or PostgreSQL)
- [x] Mock carrier agents with timeouts and bad-data handling
- [x] Request loop and REST API
- [x] Rationale (LLM with template fallback)
- [x] Dashboard
- [ ] Real emissions data (Climatiq or GLEC)
- [ ] Fetch.ai uAgents for carrier messaging

## License

MIT
