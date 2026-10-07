#!/usr/bin/env bash
# Creates labels and one issue per PRD requirement using the GitHub CLI.
# Run from the repo root after `gh auth login`:  bash scripts/create_issues.sh
set -euo pipefail

gh label create P0 --color B60205 --description "Required for MVP" --force
gh label create P1 --color FBCA04 --description "After the core loop works" --force

issue() { gh issue create --title "$1" --label "$2" --body "$3"; }

issue "FR-1: Buyer agent broadcasts shipment requests" P0 "Broadcast origin, destination, weight, and deadline over Agentverse."
issue "FR-2: Carrier agents return bids within a timeout" P0 "Each bid includes price, ETA, and CO2e."
issue "FR-3: Exclude and log late or incomplete bids" P0 "Bids after the timeout or missing a field are dropped and logged."
issue "FR-4: Rank bids with the scoring engine" P0 "Min-max normalization plus current cost/carbon weights."
issue "FR-5: Change weights without restarting agents" P0 "Weights are read at scoring time from the dashboard setting."
issue "FR-6: LLM rationale for the top-ranked carrier" P0 "Pass only the bid table and weights into the prompt."
issue "FR-7: Rationale beside bid table with Approve/Reject" P0 "Dashboard view for reviewing a recommendation."
issue "FR-8: Approved shipments move to live view" P0 "Rejected ones return to pending."
issue "FR-9: CO2e saved versus cheapest-option baseline" P0 "Per shipment and in total."
issue "FR-10: Fallback when the LLM call fails" P1 "Show the ranking with a fallback message."
issue "FR-11: Saved weight presets" P1 "For example Cost-first and Green-first."
issue "FR-12: CSV emissions report export" P1 "Export completed shipments."

echo "Done. Add these issues to a GitHub Project board from the repo's Projects tab."
