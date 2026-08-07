#!/bin/bash
# World B, auditor fully disabled (AUDITOR_ENABLED=0).
set -e
PRICE_MODE=replay REPLAY_WORLD=B docker compose up -d --force-recreate backend
AUDITOR_ENABLED=0 python3 experiments/run_experiment.py --world B --cycles 72 \
  --delay 2 --hard-reset --model claude-haiku-4-5-20251001 --label World-B-noauditor
