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
import sys
import time
from datetime import datetime
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
    build_agent_prompt,
    execute_trades,
    update_memory_from_response,
    _calculate_portfolio_value,
    cmd_reset_memory,
)

import httpx

# LLM client — supports anthropic and openai
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")  # "anthropic" or "openai"
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")


def call_llm(prompt: str, model: str = None) -> str:
    """Call the LLM and return the raw response text."""
    model = model or LLM_MODEL

    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    elif LLM_PROVIDER == "openai":
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    else:
        raise ValueError(f"Unknown LLM provider: {LLM_PROVIDER}")


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
        return {"error": "Failed to parse LLM response", "raw": raw_text[:500]}


def run_experiment(num_cycles: int, cycle_delay: int, model: str = None,
                   reset: bool = True, output_dir: str = None):
    """Run a full multi-cycle experiment."""

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
    ordered_agents = get_execution_order(ecosystem["agents"])

    # Validate keys before starting
    keys = load_keys()
    registered = [a["name"] for a in ordered_agents if a["name"] in keys]
    if not registered:
        sys.exit("ERROR: No registered agents found in .agent_keys.json. Run 'python3 agents/run.py --setup' first.")
    if len(registered) < len(ordered_agents):
        missing = [a["name"] for a in ordered_agents if a["name"] not in keys]
        print(f"WARNING: {len(missing)} agents have no key and will be skipped: {missing}")

    # Optionally reset memory
    if reset:
        print("Resetting agent memories...")
        cmd_reset_memory(argparse.Namespace())

    # Save experiment config
    config = {
        "timestamp": timestamp,
        "num_cycles": num_cycles,
        "cycle_delay_seconds": cycle_delay,
        "model": model or LLM_MODEL,
        "provider": LLM_PROVIDER,
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

    print(f"\n{'='*60}")
    print(f"EXPERIMENT START: {timestamp}")
    print(f"Cycles: {num_cycles}, Delay: {cycle_delay}s, Model: {model or LLM_MODEL}")
    print(f"Agents: {len(ordered_agents)}, Output: {exp_dir}")
    print(f"{'='*60}\n")

    # ── Main Experiment Loop ──
    for cycle in range(1, num_cycles + 1):
        cycle_start = time.time()
        print(f"\n{'─'*50}")
        print(f"CYCLE {cycle}/{num_cycles} — {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'─'*50}")

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
                print(f"\n  ── Phase {phase}: {phase_info['name']} ──")

            if name not in keys:
                print(f"  [{name}] Not registered, skipping")
                continue

            api_key = keys[name]

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

                print(f"  [{name}] Portfolio: ${post_value:,.2f} ({post_value - agent_config.get('initial_balance', 10000):+,.2f})")

            except Exception as e:
                print(f"  [{name}] ERROR: {e}")
                with open(exp_dir / "errors" / f"{name}_cycle_{cycle}.txt", "w") as f:
                    f.write(str(e))
                # cycle_portfolios[name] set at state-fetch step; only fall back to 0 if that also failed

        # Save cycle portfolio values
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            row = [cycle, datetime.now().isoformat()]
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
            with open(exp_dir / "status" / f"cycle_{cycle}.json", "w") as f:
                json.dump(all_status, f, indent=2)
        except Exception as e:
            print(f"  [status snapshot error] {e}")

        # Cycle timing
        cycle_time = time.time() - cycle_start
        print(f"\n  Cycle {cycle} completed in {cycle_time:.1f}s")

        # Wait for next cycle
        if cycle < num_cycles:
            print(f"  Waiting {cycle_delay}s for next cycle...")
            time.sleep(cycle_delay)

    # ── Experiment Complete ──
    print(f"\n{'='*60}")
    print(f"EXPERIMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Output: {exp_dir}")
    print(f"Portfolio CSV: {csv_path}")
    print(f"Messages CSV: {msg_csv_path}")

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


def main():
    parser = argparse.ArgumentParser(description="Agent Metaverse Experiment Runner")
    parser.add_argument("--cycles", type=int, default=50, help="Number of cycles to run")
    parser.add_argument("--delay", type=int, default=10, help="Delay between cycles (seconds)")
    parser.add_argument("--model", type=str, help="LLM model override")
    parser.add_argument("--no-reset", action="store_true", help="Don't reset memories before experiment")
    parser.add_argument("--output-dir", type=str, help="Custom output directory")

    args = parser.parse_args()
    run_experiment(
        num_cycles=args.cycles,
        cycle_delay=args.delay,
        model=args.model,
        reset=not args.no_reset,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
