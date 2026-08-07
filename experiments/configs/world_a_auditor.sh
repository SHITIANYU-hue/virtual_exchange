#!/bin/bash
# World A (blind bull/bear/sideways replay), auditor ON (block_and_flag).
set -e
export AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929
PRICE_MODE=replay REPLAY_WORLD=A docker compose up -d --force-recreate backend
python3 experiments/run_experiment.py --world A --cycles 72 --delay 2 \
  --hard-reset --model claude-haiku-4-5-20251001 --label World-A-auditor
