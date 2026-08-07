#!/bin/bash
# Live Binance prices (no replay), auditor ON (block_and_flag).
set -e
export AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929
docker compose up -d backend   # plain live mode, no PRICE_MODE/REPLAY_WORLD
python3 run_experiment.py --cycles 50 --delay 10 \
  --hard-reset --model claude-haiku-4-5-20251001 --label regular-market-auditor
