#!/bin/bash
# World A, auditor fully disabled (AUDITOR_ENABLED=0 — the LLM judge is
# never invoked at all, distinct from log_only which still scores every
# action but never blocks).
set -e
PRICE_MODE=replay REPLAY_WORLD=A docker compose up -d --force-recreate backend
AUDITOR_ENABLED=0 python3 run_experiment.py --world A --cycles 72 \
  --delay 2 --hard-reset --model claude-haiku-4-5-20251001 --label World-A-noauditor
