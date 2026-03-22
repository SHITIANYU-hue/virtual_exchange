#!/usr/bin/env python3
"""
Agent Metaverse - Experiment Runner

Automated multi-cycle experiments with:
  - ReAct agent reasoning framework
  - Persistent cross-cycle memory
  - Phase-based execution scheduling (4 phases)
  - Structured coordination tracking
  - Resume support for interrupted experiments
  - Full logging (prompts, actions, market snapshots)
  - Portfolio tracking and CSV export

Usage:
    python3 experiments/run_experiment.py --cycles 50 --delay 10
    python3 experiments/run_experiment.py --cycles 100 --model claude-sonnet-4-20250514
    python3 experiments/run_experiment.py --resume experiments/experiment_logs/20260316_120000
    python3 experiments/run_experiment.py --cycles 50 --agents GoldenWhale,CryptoGuru,HappyTrader
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

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
    build_agent_prompt,
    execute_trades,
    update_memory_from_response,
    _calculate_portfolio_value,
    cmd_reset_memory,
)

import httpx


# ──────────────────────────────────────────────
# Terminal Colors
# ──────────────────────────────────────────────

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def cprint(msg: str, color: str = Colors.ENDC):
    print(f"{color}{msg}{Colors.ENDC}")


# ──────────────────────────────────────────────
# LLM Client
# ──────────────────────────────────────────────

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")


def call_llm(prompt: str, provider: str = None, model: str = None) -> str:
    """Call the LLM and return the raw response text."""
    provider = provider or LLM_PROVIDER
    model = model or LLM_MODEL

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    elif provider == "openai":
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    elif provider == "commonstack":
        # Commonstack API — OpenAI-compatible endpoint
        # Set env: COMMONSTACK_API_KEY=your_key
        # Models: "openai/gpt-4.1", "anthropic/claude-sonnet-4-20250514", etc.
        import openai
        api_key = os.environ.get("COMMONSTACK_API_KEY")
        if not api_key:
            raise ValueError("COMMONSTACK_API_KEY env var is required for commonstack provider")
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.commonstack.ai/v1",
        )
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    elif provider == "commonstack-anthropic":
        # Commonstack via Anthropic SDK compatibility
        # Set env: COMMONSTACK_API_KEY=your_key
        import anthropic
        api_key = os.environ.get("COMMONSTACK_API_KEY")
        if not api_key:
            raise ValueError("COMMONSTACK_API_KEY env var is required for commonstack-anthropic provider")
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url="https://api.commonstack.ai/v1",
        )
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: anthropic, openai, commonstack, commonstack-anthropic")


def parse_llm_response(raw_text: str) -> dict:
    """Extract JSON from LLM response (handles markdown code blocks)."""
    text = raw_text.strip()

    # Try to find JSON in code blocks
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find any JSON object in the text
        brace_start = text.find("{")
        brace_end = text.rfind("}") + 1
        if brace_start >= 0 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end])
            except json.JSONDecodeError:
                pass
        return {"_parse_error": True, "error": "Failed to parse LLM response", "raw": raw_text[:500]}


# ──────────────────────────────────────────────
# Experiment Runner
# ──────────────────────────────────────────────

def run_experiment(
    num_cycles: int,
    cycle_delay: int,
    provider: str = None,
    model: str = None,
    reset: bool = True,
    output_dir: str = None,
    agent_filter: List[str] = None,
    skip_confirm: bool = False,
):
    """Run a full multi-cycle experiment with ReAct agents."""

    provider = provider or LLM_PROVIDER
    model = model or LLM_MODEL

    # Setup output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_dir:
        exp_dir = Path(output_dir)
    else:
        exp_dir = Path(__file__).parent / "experiment_logs" / timestamp
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "prompts").mkdir(exist_ok=True)
    (exp_dir / "actions").mkdir(exist_ok=True)
    (exp_dir / "status").mkdir(exist_ok=True)
    (exp_dir / "errors").mkdir(exist_ok=True)

    # Load ecosystem and keys
    ecosystem = load_ecosystem()
    keys = load_keys()

    # Filter agents if specified
    if agent_filter:
        agents_to_run = [a for a in ecosystem["agents"] if a["name"] in agent_filter]
    else:
        agents_to_run = ecosystem["agents"]

    ordered_agents = get_execution_order(agents_to_run)

    # Optionally reset memory
    if reset:
        cprint("Resetting agent memories...", Colors.YELLOW)
        cmd_reset_memory(argparse.Namespace())

    # Save experiment config
    config = {
        "timestamp": timestamp,
        "num_cycles": num_cycles,
        "cycle_delay_seconds": cycle_delay,
        "model": model,
        "provider": provider,
        "agents": [{"name": a["name"], "role": a["role"],
                     "initial_balance": a.get("initial_balance", 10000)}
                    for a in ordered_agents],
        "execution_phases": {str(k): v for k, v in EXECUTION_PHASES.items()},
    }
    with open(exp_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Initialize CSV
    csv_path = exp_dir / "portfolio_performance.csv"
    agent_names = [a["name"] for a in ordered_agents]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "timestamp"] + agent_names)

    # Message log
    msg_csv_path = exp_dir / "messages.csv"
    with open(msg_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "phase", "sender", "recipient", "content", "has_coordination"])

    # Estimate cost
    cost_per_call = 0.015 if provider == "anthropic" else 0.03
    total_calls = num_cycles * len(ordered_agents)
    estimated_cost = total_calls * cost_per_call

    cprint(f"\n{'='*70}", Colors.HEADER)
    cprint(f"EXPERIMENT START: {timestamp}", Colors.HEADER)
    cprint(f"{'='*70}", Colors.HEADER)
    cprint(f"Cycles: {num_cycles}, Delay: {cycle_delay}s")
    cprint(f"Model: {provider}/{model}")
    cprint(f"Agents: {len(ordered_agents)} ({', '.join(a['name'] for a in ordered_agents)})")
    cprint(f"Output: {exp_dir}")
    cprint(f"Total LLM calls: {total_calls}")
    cprint(f"Estimated cost: ${estimated_cost:.2f}", Colors.YELLOW)
    print()

    # Execution order display
    cprint("Execution order:", Colors.CYAN)
    for agent in ordered_agents:
        phase = get_agent_phase(agent["role"])
        balance = agent.get("initial_balance", 10000)
        cprint(f"  Phase {phase}: {agent['name']} ({agent['role']}, ${balance:,})")

    # Confirmation
    if not skip_confirm:
        try:
            input(f"\n{Colors.YELLOW}Press ENTER to start, or Ctrl+C to cancel...{Colors.ENDC}")
        except KeyboardInterrupt:
            cprint("\nCancelled.", Colors.RED)
            return

    # Stats tracking
    stats = {"total_trades": 0, "total_messages": 0, "errors": 0, "api_calls": 0}
    start_time = time.time()

    # ── Main Experiment Loop ──
    try:
        for cycle in range(1, num_cycles + 1):
            cycle_start = time.time()
            cprint(f"\n{'─'*60}", Colors.CYAN)
            cprint(f"CYCLE {cycle}/{num_cycles} — {datetime.now().strftime('%H:%M:%S')}", Colors.BOLD)
            cprint(f"{'─'*60}", Colors.CYAN)

            cycle_portfolios = {}
            cycle_messages = []

            # Execute agents in phase order
            current_phase = 0
            for agent_config in ordered_agents:
                name = agent_config["name"]
                phase = get_agent_phase(agent_config["role"])

                if phase != current_phase:
                    current_phase = phase
                    phase_info = EXECUTION_PHASES[phase]
                    cprint(f"\n  ── Phase {phase}: {phase_info['name']} ──", Colors.BLUE)

                if name not in keys:
                    cprint(f"  [{name}] Not registered, skipping", Colors.RED)
                    continue

                api_key = keys[name]

                try:
                    # 1. Get current state
                    state = get_agent_state(api_key)
                    portfolio_value = _calculate_portfolio_value(state)

                    # 2. Build ReAct prompt
                    prompt = build_agent_prompt(agent_config, state, ecosystem, cycle=cycle)

                    # Save prompt
                    with open(exp_dir / "prompts" / f"{name}_cycle_{cycle}.txt", "w") as f:
                        f.write(prompt)

                    # 3. Call LLM
                    print(f"  [{name}] Calling LLM...", end=" ", flush=True)
                    raw_response = call_llm(prompt, provider, model)
                    stats["api_calls"] += 1

                    # 4. Parse response
                    action = parse_llm_response(raw_response)

                    # Save action (raw + parsed)
                    with open(exp_dir / "actions" / f"{name}_cycle_{cycle}.json", "w") as f:
                        json.dump({"raw": raw_response, "parsed": action}, f, indent=2, ensure_ascii=False)

                    if action.get("_parse_error"):
                        cprint(f"PARSE ERROR: {action['error']}", Colors.RED)
                        stats["errors"] += 1
                        with open(exp_dir / "errors" / f"{name}_cycle_{cycle}.txt", "w") as f:
                            f.write(raw_response)
                        continue

                    # Print ReAct summary
                    react = action.get("react", {})
                    if react.get("plan"):
                        plan_short = react["plan"][:100]
                        cprint(f"Plan: {plan_short}", Colors.YELLOW)
                    elif action.get("reasoning"):
                        # Backwards compatibility with old format
                        cprint(f"Reasoning: {action['reasoning'][:100]}", Colors.YELLOW)
                    else:
                        print("(no plan)")

                    # 5. Execute trades
                    num_trades = len(action.get("trades", []))
                    num_msgs = len(action.get("messages", []))
                    stats["total_trades"] += num_trades
                    stats["total_messages"] += num_msgs

                    execute_trades(name, api_key, action)

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

                    initial = agent_config.get("initial_balance", 10000)
                    pnl = post_value - initial
                    color = Colors.GREEN if pnl >= 0 else Colors.RED
                    cprint(f"  [{name}] ${post_value:,.2f} ({pnl:+,.2f})", color)

                except Exception as e:
                    cprint(f"  [{name}] ERROR: {e}", Colors.RED)
                    stats["errors"] += 1
                    with open(exp_dir / "errors" / f"{name}_cycle_{cycle}.txt", "w") as f:
                        import traceback
                        f.write(f"Agent: {name}\nCycle: {cycle}\nError: {e}\n\n")
                        f.write(traceback.format_exc())
                    cycle_portfolios[name] = 0

            # Save cycle portfolio values to CSV
            with open(csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                row = [cycle, datetime.now().isoformat()]
                for name in agent_names:
                    row.append(round(cycle_portfolios.get(name, 0), 2))
                writer.writerow(row)

            # Save cycle messages to CSV
            with open(msg_csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                for msg in cycle_messages:
                    writer.writerow([msg["cycle"], msg["phase"], msg["sender"],
                                    msg["recipient"], msg["content"], msg["has_coordination"]])

            # Save cycle status snapshot
            try:
                all_status = {}
                for agent_config in ordered_agents:
                    n = agent_config["name"]
                    if n in keys:
                        st = get_agent_state(keys[n])
                        all_status[n] = {
                            "portfolio_value": cycle_portfolios.get(n, 0),
                            "balances": st["balances"],
                            "positions": st["positions"],
                        }
                with open(exp_dir / "status" / f"cycle_{cycle}.json", "w") as f:
                    json.dump(all_status, f, indent=2)
            except Exception as e:
                cprint(f"  [status snapshot error] {e}", Colors.RED)

            # Cycle timing
            cycle_time = time.time() - cycle_start
            cprint(f"\n  Cycle {cycle} completed in {cycle_time:.1f}s", Colors.GREEN)

            # Progress every 5 cycles
            if cycle % 5 == 0:
                elapsed = time.time() - start_time
                avg = elapsed / cycle
                eta = avg * (num_cycles - cycle)
                cprint(f"\n{'='*60}", Colors.HEADER)
                cprint(f"PROGRESS: {cycle}/{num_cycles} ({cycle/num_cycles*100:.0f}%)", Colors.HEADER)
                cprint(f"Elapsed: {elapsed/60:.1f}min | ETA: {eta/60:.1f}min", Colors.HEADER)
                cprint(f"Trades: {stats['total_trades']} | Messages: {stats['total_messages']} | "
                       f"API calls: {stats['api_calls']} | Errors: {stats['errors']}", Colors.HEADER)
                cprint(f"{'='*60}", Colors.HEADER)

            # Wait for next cycle
            if cycle < num_cycles:
                cprint(f"  Waiting {cycle_delay}s...", Colors.CYAN)
                time.sleep(cycle_delay)

    except KeyboardInterrupt:
        cprint(f"\n\nExperiment interrupted at cycle {cycle}.", Colors.YELLOW)
        cprint(f"Resume with: python3 experiments/run_experiment.py --resume {exp_dir}", Colors.YELLOW)

    # ── Final Report ──
    elapsed = time.time() - start_time
    cprint(f"\n{'='*70}", Colors.HEADER)
    cprint(f"EXPERIMENT COMPLETE", Colors.HEADER)
    cprint(f"{'='*70}", Colors.HEADER)
    cprint(f"Duration: {elapsed/3600:.2f} hours ({elapsed/60:.1f} min)")
    cprint(f"Output: {exp_dir}")

    cprint(f"\nFinal Standings:", Colors.BOLD)
    cprint(f"{'Agent':<16} {'Role':<20} {'Initial':>10} {'Final':>10} {'PnL':>10}")
    cprint("-" * 68)
    for agent_config in ordered_agents:
        name = agent_config["name"]
        initial = agent_config.get("initial_balance", 10000)
        final = cycle_portfolios.get(name, 0)
        pnl = final - initial
        color = Colors.GREEN if pnl >= 0 else Colors.RED
        cprint(f"{name:<16} {agent_config['role']:<20} ${initial:>8,} ${final:>8,.0f} {pnl:>+9,.0f}", color)

    cprint(f"\nStats: {stats['total_trades']} trades, {stats['total_messages']} messages, "
           f"{stats['api_calls']} API calls, {stats['errors']} errors")
    cprint(f"\nNext steps:", Colors.CYAN)
    cprint(f"  1. Analyze: python3 experiments/analyze_results.py {exp_dir}")
    cprint(f"  2. Visualize: python3 experiments/visualize_results.py {exp_dir}")


def resume_experiment(log_dir: str):
    """Resume an interrupted experiment."""
    config_path = Path(log_dir) / "config.json"
    if not config_path.exists():
        print(f"No config.json found in {log_dir}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    # Find last completed cycle
    status_dir = Path(log_dir) / "status"
    completed = len(list(status_dir.glob("cycle_*.json")))
    start_cycle = completed + 1

    cprint(f"Resuming from cycle {start_cycle} (found {completed} completed cycles)", Colors.YELLOW)

    # We can't easily resume mid-experiment with the current architecture
    # For now, just re-run remaining cycles
    remaining = config["num_cycles"] - completed
    if remaining <= 0:
        cprint("Experiment already complete!", Colors.GREEN)
        return

    agent_names = [a["name"] for a in config["agents"]]
    run_experiment(
        num_cycles=config["num_cycles"],
        cycle_delay=config["cycle_delay_seconds"],
        provider=config.get("provider", "anthropic"),
        model=config.get("model"),
        reset=False,  # Don't reset when resuming
        output_dir=log_dir,
        agent_filter=agent_names,
        skip_confirm=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Agent Metaverse Experiment Runner (ReAct Framework)")
    parser.add_argument("--cycles", type=int, default=50, help="Number of cycles to run")
    parser.add_argument("--delay", type=int, default=10, help="Delay between cycles (seconds)")
    parser.add_argument("--model", type=str, help="LLM model override")
    parser.add_argument("--provider", choices=["anthropic", "openai", "commonstack", "commonstack-anthropic"], help="LLM provider")
    parser.add_argument("--no-reset", action="store_true", help="Don't reset memories before experiment")
    parser.add_argument("--output-dir", type=str, help="Custom output directory")
    parser.add_argument("--agents", type=str, help="Comma-separated list of agents to include")
    parser.add_argument("--resume", type=str, help="Resume from existing experiment directory")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.resume:
        resume_experiment(args.resume)
    else:
        agent_filter = args.agents.split(",") if args.agents else None
        run_experiment(
            num_cycles=args.cycles,
            cycle_delay=args.delay,
            provider=args.provider,
            model=args.model,
            reset=not args.no_reset,
            output_dir=args.output_dir,
            agent_filter=agent_filter,
            skip_confirm=args.yes,
        )


if __name__ == "__main__":
    main()
