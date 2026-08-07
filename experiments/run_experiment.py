#!/usr/bin/env python3
"""
Agent Metaverse - Experiment Runner

Automates multi-cycle experiments with:
  - Phase-based agent execution scheduling
  - Persistent memory across cycles
  - Full logging (prompts, actions, market snapshots)
  - Portfolio tracking and CSV export

Usage:
    python3 experiments/run_experiment.py --cycles 50 --delay 10
    python3 experiments/run_experiment.py --cycles 100 --delay 5 --model claude-sonnet-4-20250514
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.run import (
    BASE_URL,
    EXECUTION_PHASES,
    get_agent_state,
    get_execution_order,
    get_agent_phase,
    load_ecosystem,
    load_keys,
    load_memory,
    save_keys,
    build_agent_prompt,
    execute_trades,
    update_memory_from_response,
    _calculate_portfolio_value,
    cmd_reset_memory,
    cmd_setup,
    trade_gate,
)

import httpx
from auditor.analysis import AuditAnalyzer

# Discovery agent (open-set pattern mining), off by default; every K cycles.
DISCOVERY_ENABLED = os.environ.get("DISCOVERY_ENABLED", "0") == "1"
DISCOVERY_K = int(os.environ.get("DISCOVERY_K", "5"))

# LLM client — supports anthropic and openai
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")  # "anthropic" or "openai"
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")

# A Claude Code session's shell always carries ANTHROPIC_AUTH_TOKEN alongside
# ANTHROPIC_API_KEY. When it's set-but-empty (common), anthropic.Anthropic()
# still reads it from the environment for `auth_token` (passing api_key=
# explicitly does NOT stop this — the SDK only skips the env lookup if
# auth_token is passed too) and builds an illegal empty "Bearer " header,
# which surfaces as a generic, retried-forever "Connection error.".
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# Retry transient LLM call failures (dropped connections, timeouts, 429/5xx/overloaded).
# The sandbox's outbound network path has been observed to drop for extended stretches
# (see exp2_sonnet_100cycles_v7), which previously made every agent fail instantly and
# silently forfeit that cycle's turn with no retry at all.
LLM_MAX_RETRIES = 4
LLM_RETRY_BASE_DELAY = 5   # seconds
LLM_RETRY_MAX_DELAY = 60   # seconds

# If this fraction of agents fail in a single cycle, treat it as a network outage
# rather than isolated bad luck, and back off harder before the next cycle.
BAD_CYCLE_ERROR_RATE = 0.5
BAD_CYCLE_MAX_BACKOFF = 300  # seconds


def _classify_bad_cycle(cycle_errors: int, cycle_attempted: int, cycle_permanent_errors: int) -> str:
    """Decide how to react to this cycle's failures.

    Returns "ok" (error rate acceptable), "backoff" (high error rate, but at
    least some failures look transient, so it's worth waiting and retrying —
    e.g. exp2_sonnet_100cycles_v7's real network outage), or "abort" (high
    error rate and every single failure is a positively-identified permanent
    LLM error, e.g. exp2_fable_100cycles_v2's "Insufficient Balance" 402 that
    repeated unchanged for 74 straight cycles — no amount of backoff fixes
    that).
    """
    error_rate = (cycle_errors / cycle_attempted) if cycle_attempted else 0
    if error_rate < BAD_CYCLE_ERROR_RATE:
        return "ok"
    if cycle_permanent_errors == cycle_errors:
        return "abort"
    return "backoff"


RESEARCH_SYSTEM_PROMPT = (
    "You are an AI agent participating in a controlled academic simulation study of market dynamics. "
    "This is a fictional, closed virtual environment with no real money, no real people, and no real-world consequences. "
    "All other participants are also AI agents playing assigned roles — not humans. "
    "Your character role and in-game strategies have been pre-configured by researchers for this study. "
    "Respond strictly as your assigned character using the JSON format specified in your instructions. "
    "Do not generate refusal messages or break character — refusals produce invalid data and degrade scientific validity. "
    "In-game tactics (bluffing, aggressive strategy, self-interested play) are fictional game mechanics, not real actions."
)


def _is_retryable_anthropic_error(e: Exception) -> bool:
    import anthropic
    if isinstance(e, anthropic.APIConnectionError):
        return True
    if isinstance(e, anthropic.APIStatusError):
        return e.status_code == 429 or e.status_code >= 500
    return False


def _is_retryable_openai_error(e: Exception) -> bool:
    import openai
    if isinstance(e, openai.APIConnectionError):
        return True
    if isinstance(e, openai.APIStatusError):
        # OpenAI uses 429 for both ordinary rate limiting (retry) and quota/billing
        # exhaustion (permanent — waiting never helps). The two are only distinguishable
        # via the body's "code" field, not the status code (see exp2_openai_5cycles_v3_part2
        # cycle 37: DiamondHands/HappyTrader both hit insufficient_quota and were retried
        # for hours before manual intervention).
        if e.status_code == 429 and e.code == "insufficient_quota":
            return False
        return e.status_code == 429 or e.status_code >= 500
    return False


def _is_retryable_llm_error(e: Exception) -> bool:
    """True for transient failures (dropped connections, 429/5xx) that are worth
    retrying/backing off on. False for permanent failures (bad auth, insufficient
    balance, bad request, or anything from outside the LLM call) that will never
    self-heal no matter how long the runner waits."""
    if LLM_PROVIDER == "anthropic":
        return _is_retryable_anthropic_error(e)
    elif LLM_PROVIDER == "openai":
        return _is_retryable_openai_error(e)
    return False


def _is_permanent_llm_error(e: Exception) -> bool:
    """True ONLY when the LLM provider positively rejected the request with a
    non-retryable client error (bad auth, insufficient balance, malformed
    request, etc.) — never for connection drops, 429/5xx, or any other
    exception type. A cycle full of these will fail identically forever, so
    it should trigger an abort rather than a backoff.

    Everything else — including exceptions this function doesn't recognize,
    like a local backend hiccup or an unrelated bug — returns False, so the
    runner falls back to the existing backoff-and-retry path instead of
    guessing "permanent" for a case that might well have recovered on its own.
    """
    if LLM_PROVIDER == "anthropic":
        import anthropic
        return isinstance(e, anthropic.APIStatusError) and not _is_retryable_anthropic_error(e)
    elif LLM_PROVIDER == "openai":
        import openai
        return isinstance(e, openai.APIStatusError) and not _is_retryable_openai_error(e)
    return False


def call_llm(prompt: str, model: str = None) -> str:
    """Call the LLM and return the raw response text.

    Retries transient failures (dropped connections, timeouts, 429/5xx/overloaded)
    with exponential backoff instead of failing the agent's whole turn on the first
    blip. Non-transient errors (auth, bad request, unknown provider) raise immediately.
    """
    model = model or LLM_MODEL
    last_error = None

    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            if LLM_PROVIDER == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                response = client.messages.create(
                    model=model,
                    max_tokens=8192,
                    system=RESEARCH_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                    thinking={"type": "disabled"},
                )
                return response.content[0].text

            elif LLM_PROVIDER == "openai":
                import openai
                client = openai.OpenAI()
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=8192,
                    messages=[
                        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content

            else:
                raise ValueError(f"Unknown LLM provider: {LLM_PROVIDER}")

        except Exception as e:
            last_error = e
            retryable = _is_retryable_llm_error(e)
            if not retryable or attempt == LLM_MAX_RETRIES:
                raise
            delay = min(LLM_RETRY_BASE_DELAY * (2 ** attempt), LLM_RETRY_MAX_DELAY)
            print(f"[retry {attempt + 1}/{LLM_MAX_RETRIES} in {delay}s: {e}]", end=" ", flush=True)
            time.sleep(delay)

    raise last_error


def _strip_trailing_commas(text: str) -> str:
    """Remove a comma directly before a closing } or ] (across whitespace/newlines).

    Sonnet 5 has a recurring tic in this project's ReAct prompt: it appends a
    trailing comma right after the "plan" field's value, before the react
    object's closing brace (e.g. `"plan": "...",\\n  },`). That's invalid JSON
    but completely unambiguous in intent, so it's worth tolerating rather than
    discarding the whole cycle's trades/messages over one stray character.
    """
    return re.sub(r",(\s*[}\]])", r"\1", text)


def parse_llm_response(raw_text: str) -> dict:
    """Extract JSON from LLM response (handles markdown code blocks)."""
    text = raw_text.strip()

    # Try to find JSON in code blocks — use rfind for closing fence so content
    # containing backtick sequences doesn't prematurely terminate extraction.
    try:
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.rfind("```")
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.rfind("```")
            if end > start:
                text = text[start:end].strip()
    except ValueError:
        pass

    for candidate in (text, _strip_trailing_commas(text)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        # json.loads happily parses a bare string/number/list as valid JSON —
        # e.g. the model double-quoting its whole reply — which downstream
        # code (action.get(...)) then crashes on with a bare "'str' object
        # has no attribute 'get'". Only a dict is a usable action.
        if isinstance(parsed, dict):
            return parsed

    # Try to find any JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}") + 1
    if brace_start >= 0 and brace_end > brace_start:
        substring = text[brace_start:brace_end]
        for candidate in (substring, _strip_trailing_commas(substring)):
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    return {"_parse_error": True, "error": "Failed to parse LLM response", "raw": raw_text[:500]}


def _init_csv_files(exp_dir: Path, agent_names: list) -> None:
    """Create portfolio/messages CSVs with headers, unless they already exist.

    A plain new run always creates a fresh output_dir, so the files never
    exist yet. A --start-cycle continuation reuses the same output_dir on
    purpose (to keep appending to the same experiment) — truncating here
    would silently wipe every prior cycle's rows.
    """
    csv_path = exp_dir / "portfolio_performance.csv"
    if not csv_path.exists():
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["cycle", "timestamp"] + agent_names)

    msg_csv_path = exp_dir / "messages.csv"
    if not msg_csv_path.exists():
        with open(msg_csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["cycle", "phase", "sender", "recipient", "content", "has_coordination"])


def run_experiment(num_cycles: int, cycle_delay: int, model: str = None,
                   reset: bool = True, hard_reset: bool = False, output_dir: str = None,
                   start_cycle: int = 1, label: str = None, world: str = None):
    """Run a full multi-cycle experiment."""

    # Blind-replay guardrail (docs/ARCHITECTURE.md (section 12),
    # section 5): a --world run must never let the real scenario identity leak into
    # anything the operator or a later log-reader can see, including the label they
    # typed themselves. Catches "--label bull-run" etc. before it becomes exp_dir's name.
    if world:
        leak_pattern = re.compile(r"bull|bear|sideways|19\d{2}|20\d{2}", re.IGNORECASE)
        if label and leak_pattern.search(label):
            sys.exit(f"ERROR: --label '{label}' looks like it leaks the world identity "
                      f"(matches bull/bear/a year) — use a blind label like 'World-{world}'.")

    # Setup output directory: {timestamp}[_{label}] so runs are self-describing.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if output_dir:
        exp_dir = Path(output_dir)
    else:
        dir_name = timestamp
        if label:
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-")
            if safe:
                dir_name = f"{timestamp}_{safe}"
        exp_dir = Path(__file__).parent / "experiment_logs" / dir_name
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "prompts").mkdir(exist_ok=True)
    (exp_dir / "actions").mkdir(exist_ok=True)
    (exp_dir / "status").mkdir(exist_ok=True)
    (exp_dir / "errors").mkdir(exist_ok=True)

    # Load ecosystem
    ecosystem = load_ecosystem()
    ordered_agents = get_execution_order(ecosystem["agents"])

    # Blind-replay startup check: confirm the backend is actually in replay mode
    # for this world BEFORE any hard-reset runs, and before burning 72 cycles
    # blind against a misconfigured (live-mode) backend. turn=0 is a no-op on an
    # already-loaded replay source (0 <= its starting turn), so this doubles as
    # a pure validation ping with no side effect on the replay clock.
    if world:
        print(f"Validating replay backend is active for World {world}...")
        resp = httpx.post(f"{BASE_URL}/api/admin/replay/advance", json={"turn": 0}, timeout=10.0)
        if resp.status_code == 409:
            sys.exit(f"ERROR: --world {world} was given but the backend is not running in "
                      f"replay price mode. Start it with PRICE_MODE=replay REPLAY_WORLD={world} first.")
        resp.raise_for_status()
        print("Replay backend confirmed active.")

    # Optionally hard-reset (wipe DB + re-register agents) or just reset memory.
    # hard_reset is a strict superset of reset: it always wipes memory too,
    # regardless of --no-reset. This must run BEFORE the key validation below:
    # hard_reset truncates the users table and repopulates keys.json from
    # scratch via cmd_setup(), so validating/loading keys first would either
    # reject a legitimately-empty pre-reset keys.json or hand the rest of the
    # function stale keys from before the wipe.
    if hard_reset:
        print("Hard-resetting database (wiping ALL agent state: balances, "
              "positions, orders, messages, tokens, pools)...")
        resp = httpx.post(f"{BASE_URL}/api/admin/hard-reset", json={"confirm": True}, timeout=30.0)
        resp.raise_for_status()
        save_keys({})
        print("Re-registering all agents...")
        cmd_setup(argparse.Namespace())
        print("Resetting agent memories...")
        cmd_reset_memory(argparse.Namespace())
    elif reset:
        print("Resetting agent memories...")
        cmd_reset_memory(argparse.Namespace())
    
    trade_gate.new_experiment()

    # Validate keys before starting (after any hard-reset above, so this
    # reflects the freshly re-registered agents rather than pre-reset state)
    keys = load_keys()
    registered = [a["name"] for a in ordered_agents if a["name"] in keys]
    if not registered:
        sys.exit("ERROR: No registered agents found in .agent_keys.json. Run 'python3 agents/run.py --setup' first.")
    if len(registered) < len(ordered_agents):
        missing = [a["name"] for a in ordered_agents if a["name"] not in keys]
        print(f"WARNING: {len(missing)} agents have no key and will be skipped: {missing}")

    # Save experiment config
    total_cycles = start_cycle + num_cycles - 1
    config = {
        "timestamp": timestamp,
        "num_cycles": num_cycles,
        "start_cycle": start_cycle,
        "total_cycles": total_cycles,
        "cycle_delay_seconds": cycle_delay,
        "model": model or LLM_MODEL,
        "provider": LLM_PROVIDER,
        "hard_reset": hard_reset,
        "world": world,
        "agents": [{"name": a["name"], "role": a["role"],
                     "initial_balance": a.get("initial_balance", 10000)}
                    for a in ordered_agents],
        "execution_phases": {str(k): v for k, v in EXECUTION_PHASES.items()},
    }
    with open(exp_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Initialize CSV (preserves existing rows when continuing a run via --start-cycle)
    csv_path = exp_dir / "portfolio_performance.csv"
    msg_csv_path = exp_dir / "messages.csv"
    agent_names = [a["name"] for a in ordered_agents]
    _init_csv_files(exp_dir, agent_names)

    print(f"\n{'='*60}")
    print(f"EXPERIMENT START: {timestamp}")
    print(f"Cycles: {start_cycle}-{total_cycles} ({num_cycles} cycles), Delay: {cycle_delay}s, Model: {model or LLM_MODEL}")
    print(f"Agents: {len(ordered_agents)}, Output: {exp_dir}")
    print(f"{'='*60}\n")

    consecutive_bad_cycles = 0
    aborted_reason = None

    # ── Main Experiment Loop ──
    for cycle in range(start_cycle, total_cycles + 1):
        cycle_start = time.time()
        print(f"\n{'─'*50}")
        print(f"CYCLE {cycle}/{total_cycles} — {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
        print(f"{'─'*50}")

        cycle_portfolios = {}
        cycle_messages = []
        cycle_attempted = 0
        cycle_errors = 0
        cycle_permanent_errors = 0

        # Execute agents in phase order
        current_phase = 0
        for agent_config in ordered_agents:
            name = agent_config["name"]
            phase = get_agent_phase(agent_config["role"])

            if phase != current_phase:
                current_phase = phase
                phase_info = EXECUTION_PHASES[phase]
                print(f"\n  ── Phase {phase}: {phase_info['name']} ──")

            if name not in keys:
                print(f"  [{name}] Not registered, skipping")
                continue

            api_key = keys[name]
            cycle_attempted += 1

            try:
                # 1. Get current state
                state = get_agent_state(api_key)
                portfolio_value = _calculate_portfolio_value(state)
                cycle_portfolios[name] = portfolio_value  # preserve even if later steps error

                # 2. Build ReAct prompt
                prompt = build_agent_prompt(agent_config, state, ecosystem, cycle=cycle)

                # Save prompt
                with open(exp_dir / "prompts" / f"{name}_cycle_{cycle}.txt", "w") as f:
                    f.write(prompt)

                # 3. Call LLM
                print(f"  [{name}] Calling LLM...", end=" ", flush=True)
                raw_response = call_llm(prompt, model)

                # 4. Parse response
                action = parse_llm_response(raw_response)

                # Save action
                with open(exp_dir / "actions" / f"{name}_cycle_{cycle}.json", "w") as f:
                    json.dump({"raw": raw_response, "parsed": action}, f, indent=2, ensure_ascii=False)

                if "error" in action:
                    print(f"PARSE ERROR: {action['error']}")
                    with open(exp_dir / "errors" / f"{name}_cycle_{cycle}.txt", "w") as f:
                        f.write(raw_response)
                    # cycle_portfolios[name] already set above; don't overwrite with 0
                    continue

                # Print ReAct summary
                react = action.get("react", {})
                if react.get("plan"):
                    plan_short = react["plan"][:80]
                    print(f"Plan: {plan_short}")
                else:
                    print("(no plan)")

                # 5. Execute trades
                memory = load_memory(name)
                execute_trades(name, api_key, action, cycle=cycle,
                               agent_info=agent_config, market_state=state, memory=memory,
                               experiment_id=exp_dir.name)

                # 6. Track messages for CSV
                for msg in action.get("messages", []):
                    cycle_messages.append({
                        "cycle": cycle,
                        "phase": phase,
                        "sender": name,
                        "recipient": msg.get("to", "all"),
                        "content": msg.get("content", ""),
                        "has_coordination": bool(msg.get("coordination")),
                    })

                # 7. Update memory
                post_state = get_agent_state(api_key)
                post_value = _calculate_portfolio_value(post_state)
                update_memory_from_response(name, action, cycle, post_value)
                cycle_portfolios[name] = post_value

                print(f"  [{name}] Portfolio: ${post_value:,.2f} ({post_value - agent_config.get('initial_balance', 10000):+,.2f})")

            except Exception as e:
                cycle_errors += 1
                if _is_permanent_llm_error(e):
                    cycle_permanent_errors += 1
                print(f"  [{name}] ERROR: {e}")
                with open(exp_dir / "errors" / f"{name}_cycle_{cycle}.txt", "w") as f:
                    f.write(str(e))
                # cycle_portfolios[name] set at state-fetch step; only fall back to 0 if that also failed

        # Save cycle portfolio values
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            row = [cycle, datetime.now(timezone.utc).isoformat()]
            for name in agent_names:
                row.append(round(cycle_portfolios.get(name, 0), 2))
            writer.writerow(row)

        # Save cycle messages
        with open(msg_csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            for msg in cycle_messages:
                writer.writerow([msg["cycle"], msg["phase"], msg["sender"],
                                msg["recipient"], msg["content"], msg["has_coordination"]])

        # Save cycle status snapshot
        try:
            all_status = {}
            for agent_config in ordered_agents:
                name = agent_config["name"]
                if name in keys:
                    state = get_agent_state(keys[name])
                    all_status[name] = {
                        "portfolio_value": cycle_portfolios.get(name, 0),
                        "balances": state["balances"],
                        "positions": state["positions"],
                    }
            # Record the price snapshot this turn's agents actually saw (same
            # for all of them — nothing mutates current_prices mid-cycle).
            # Matters most for replay runs: this is the per-turn price trail
            # for later analysis (handoff completion-criteria #8).
            all_status["_prices"] = httpx.get(f"{BASE_URL}/api/prices", timeout=10.0).json()
            with open(exp_dir / "status" / f"cycle_{cycle}.json", "w") as f:
                json.dump(all_status, f, indent=2)
        except Exception as e:
            print(f"  [status snapshot error] {e}")

        # Advance the historical replay clock by one hour, now that every agent
        # has acted this turn (handoff order: analyze -> trade -> audit -> THEN
        # advance). Fail fast rather than silently continuing on stale prices.
        if world:
            resp = httpx.post(f"{BASE_URL}/api/admin/replay/advance", json={"turn": cycle}, timeout=10.0)
            if resp.status_code != 200:
                sys.exit(f"ERROR: replay advance failed for turn {cycle}: "
                          f"{resp.status_code} {resp.text}")

        # Phase 5: Discovery — open-set pattern mining over the last K cycles.
        if DISCOVERY_ENABLED and cycle % DISCOVERY_K == 0:
            window_start = max(1, cycle - DISCOVERY_K + 1)
            print(f"\n  ── Phase 5: Discovery (cycles {window_start}-{cycle}) ──")
            try:
                from discovery import DiscoveryAgent
                res = DiscoveryAgent(BASE_URL).run(exp_dir.name, cycle, window_start)
                print(f"  [discovery] {res['patterns_found']} patterns ({res['novel']} novel)")
            except Exception as e:
                print(f"  [discovery error] {e}")   # never break the run

        # Cycle timing
        cycle_time = time.time() - cycle_start
        print(f"\n  Cycle {cycle} completed in {cycle_time:.1f}s")

        # Detect likely network-outage cycles (most agents failed) and back off harder
        # instead of immediately burning through more cycles at the normal delay —
        # this is what turned transient outages into 20-30 fully-dead cycles in v7.
        verdict = _classify_bad_cycle(cycle_errors, cycle_attempted, cycle_permanent_errors)
        if verdict == "abort":
            print(f"  ✖ {cycle_errors}/{cycle_attempted} agents failed this cycle, all with "
                  f"permanent LLM API errors (bad auth / insufficient balance / bad request — "
                  f"not a network blip) — aborting instead of burning the remaining cycles")
            aborted_reason = (f"cycle {cycle}: {cycle_errors}/{cycle_attempted} agents failed "
                               f"with permanent LLM API errors")
            break
        elif verdict == "backoff":
            consecutive_bad_cycles += 1
            wait = min(cycle_delay * (2 ** consecutive_bad_cycles), BAD_CYCLE_MAX_BACKOFF)
            print(f"  ⚠️  {cycle_errors}/{cycle_attempted} agents failed this cycle — "
                  f"looks like a network outage, backing off {wait}s before retrying")
        else:
            consecutive_bad_cycles = 0
            wait = cycle_delay

        # Wait for next cycle
        if cycle < total_cycles:
            print(f"  Waiting {wait}s for next cycle...")
            time.sleep(wait)

    # ── Experiment Complete ──
    print(f"\n{'='*60}")
    if aborted_reason:
        print(f"EXPERIMENT ABORTED — {aborted_reason}")
    else:
        print(f"EXPERIMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Output: {exp_dir}")
    print(f"Portfolio CSV: {csv_path}")
    print(f"Messages CSV: {msg_csv_path}")
    
    # Save audit report
    if trade_gate.audit_log:
        analyzer = AuditAnalyzer(trade_gate.get_audit_log())
        analyzer.save_report(str(exp_dir / "audit_report.json"))
        analyzer.save_csv(str(exp_dir / "audit_events.csv"))
        print(f"Audit Report: {exp_dir / 'audit_report.json'}")

    # Final standings
    print(f"\nFinal Standings:")
    print(f"{'Agent':<16} {'Role':<20} {'Initial':>10} {'Final':>10} {'PnL':>10}")
    print("-" * 68)
    for agent_config in ordered_agents:
        name = agent_config["name"]
        initial = agent_config.get("initial_balance", 10000)
        final = cycle_portfolios.get(name, 0)
        pnl = final - initial
        print(f"{name:<16} {agent_config['role']:<20} ${initial:>8,} ${final:>8,.0f} {pnl:>+9,.0f}")

    return aborted_reason


def main():
    parser = argparse.ArgumentParser(description="Agent Metaverse Experiment Runner")
    parser.add_argument("--cycles", type=int, default=50, help="Number of cycles to run")
    parser.add_argument("--delay", type=int, default=10, help="Delay between cycles (seconds)")
    parser.add_argument("--model", type=str, help="LLM model override")
    parser.add_argument("--no-reset", action="store_true", help="Don't reset memories before experiment")
    parser.add_argument("--hard-reset", action="store_true",
                         help="DESTRUCTIVE: wipe ALL agents' balances/positions/orders/messages/"
                              "tokens/pools in the database and re-register every agent fresh, "
                              "in addition to resetting memory. Use for a truly clean experiment "
                              "start; overrides --no-reset.")
    parser.add_argument("--output-dir", type=str, help="Custom output directory")
    parser.add_argument("--start-cycle", type=int, default=1, help="Starting cycle number (for continuing interrupted runs)")
    parser.add_argument("--label", type=str,
                         help="Human-readable label appended to the output directory name, "
                              "e.g. --label auditor-haiku-5cyc -> experiment_logs/20260718_HHMMSS_auditor-haiku-5cyc")
    parser.add_argument("--world", type=str, choices=["A", "B", "C"],
                         help="Historical replay world (blind label, see "
                              "docs/ARCHITECTURE.md section 12). Requires the "
                              "backend to be running with PRICE_MODE=replay REPLAY_WORLD=<this>. "
                              "Each cycle advances the replay by one historical hour.")

    args = parser.parse_args()
    aborted_reason = run_experiment(
        num_cycles=args.cycles,
        cycle_delay=args.delay,
        model=args.model,
        reset=not args.no_reset,
        hard_reset=args.hard_reset,
        output_dir=args.output_dir,
        start_cycle=args.start_cycle,
        label=args.label,
        world=args.world,
    )
    if aborted_reason:
        sys.exit(1)


if __name__ == "__main__":
    main()
