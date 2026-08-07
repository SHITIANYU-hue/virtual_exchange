#!/bin/bash
# Live Binance prices (no replay), auditor in log_only mode: the LLM judge
# scores every action but the enforcement layer never blocks (block_rate
# stays 0.00%). This is a different condition from AUDITOR_ENABLED=0 — the
# judge still runs here.
set -e
export AUDITOR_MODE=log_only
docker compose up -d backend
python3 run_experiment.py --cycles 50 --delay 10 \
  --hard-reset --model claude-haiku-4-5-20251001 --label regular-market-norestriction
