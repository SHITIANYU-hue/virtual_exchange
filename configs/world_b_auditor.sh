#!/bin/bash
# World B (blind bull/bear/sideways replay), auditor ON (block_and_flag).
set -e
export AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929
PRICE_MODE=replay REPLAY_WORLD=B docker compose up -d --force-recreate backend
python3 run_experiment.py --world B --cycles 72 --delay 2 \
  --hard-reset --model claude-haiku-4-5-20251001 --label World-B-auditor
