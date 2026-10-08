"""Plain-language explanation of the recommended carrier.

Uses an LLM when LLM_API_KEY is set; otherwise (or if the call fails) falls
back to a template built only from the bid data (PRD FR-6 and FR-10).
The prompt contains only the ranked bids and weights, so the model has no
other facts to draw on.
"""

from __future__ import annotations

import os

import httpx

from scoring import ScoredBid

LLM_URL = "https://api.anthropic.com/v1/messages"


def _bid_table(ranked: list[ScoredBid], names: dict[str, str]) -> str:
    rows = ["rank | carrier | price | eta | co2e_kg | score"]
    for i, s in enumerate(ranked, start=1):
        b = s.bid
        rows.append(
            f"{i} | {names[b.carrier_id]} | ${b.price:,.2f} | {b.eta:%b %d} | "
            f"{b.co2e_kg:,.1f} | {s.score:.2f}"
        )
    return "\n".join(rows)


def template_rationale(
    ranked: list[ScoredBid], names: dict[str, str], w_carbon: float, saved_kg: float
) -> str:
    top = ranked[0].bid
    name = names[top.carrier_id]
    weights = f"{round((1 - w_carbon) * 100)}% cost / {round(w_carbon * 100)}% carbon"
    if len(ranked) == 1:
        return f"{name} was the only carrier with a valid bid that meets the deadline."
    cheapest = min(ranked, key=lambda s: s.bid.price).bid
    if top.carrier_id == cheapest.carrier_id:
        return (
            f"{name} ranks first at {weights}: it is the cheapest bid at "
            f"${top.price:,.2f}, and at this weighting the extra cost of a "
            f"lower-carbon carrier outweighs its emissions savings."
        )
    extra = top.price - cheapest.price
    return (
        f"{name} ranks first at {weights}. It costs ${extra:,.2f} more than the "
        f"cheapest bid but emits {saved_kg:,.1f} kg less CO2e, and it still meets "
        f"the deadline."
    )


async def llm_rationale(
    ranked: list[ScoredBid], names: dict[str, str], w_carbon: float
) -> str | None:
    key = os.getenv("LLM_API_KEY")
    if not key:
        return None
    prompt = (
        "You explain freight carrier recommendations to a logistics coordinator.\n"
        f"Weights: cost {1 - w_carbon:.2f}, carbon {w_carbon:.2f}. Lower score is better.\n"
        f"Ranked bids:\n{_bid_table(ranked, names)}\n\n"
        "In 2 sentences, explain why the rank 1 carrier was recommended. Use only "
        "numbers from the table. Plain language, no preamble."
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                LLM_URL,
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"),
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            parts = resp.json().get("content", [])
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            return text.strip() or None
    except (httpx.HTTPError, ValueError):
        return None
