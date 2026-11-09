#!/usr/bin/env bash
# Create a demo case, generate sample documents into its folder and watch the
# system pick them up. Requires the API to be running (./scripts/run.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
API=${API:-http://127.0.0.1:8000}

echo "==> Creating a demo case"
CASE=$(curl -sS -X POST "$API/api/cases" -H 'Content-Type: application/json' -d '{
  "property_name": "Hosahalli agricultural land (demo)",
  "property_type": "agricultural_land",
  "transaction_type": "purchase",
  "survey_number": "123/4B",
  "village": "Hosahalli",
  "taluk": "Nelamangala",
  "district": "Bengaluru Rural",
  "state": "Karnataka",
  "jurisdiction_code": "KA",
  "claimed_owner": "Latha Rao",
  "seller_name": "Latha Rao",
  "buyer_name": "Anil Shetty",
  "purpose": "Pre-purchase due diligence"
}')

CASE_ID=$(printf '%s' "$CASE" | backend/.venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
FOLDER=$(printf '%s' "$CASE" | backend/.venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["watch_folder"])')
echo "    case $CASE_ID"
echo "    folder $FOLDER"

echo "==> Writing the first batch of sample documents into the folder"
backend/.venv/bin/python backend/samples/generate_samples.py "$FOLDER" --stage initial

echo "==> Waiting for the watcher to process them"
sleep 12
curl -sS "$API/api/cases/$CASE_ID" | backend/.venv/bin/python -m json.tool | head -40

echo
echo "==> Adding the missing parent deed, which should resolve a finding"
backend/.venv/bin/python backend/samples/generate_samples.py "$FOLDER" --stage later
sleep 12

echo
echo "Open the dashboard at $API and look at case $CASE_ID."
