#!/usr/bin/env python3
"""
Compute the headline statistics reported in analysis/sample_data/*/README.md
from a run's raw output (config.json, portfolio_performance.csv,
audit_report.json, messages.csv) -- no dependencies beyond the stdlib.

Usage:
    python3 analysis/analyze_run.py <run_dir> [<run_dir> ...] [--dm-pair AgentA AgentB]

Example:
    python3 analysis/analyze_run.py experiments/sample_data
"""
import argparse
import csv
import json
import statistics
from pathlib import Path


def load_config(run_dir: Path) -> dict:
    with open(run_dir / "config.json") as f:
        return json.load(f)


def final_returns(run_dir: Path, agents: list[dict]) -> list[tuple[str, str, float, float]]:
    """Returns [(name, role, final_value, return_pct), ...] sorted by return_pct desc."""
    initial = {a["name"]: a["initial_balance"] for a in agents}
    roles = {a["name"]: a["role"] for a in agents}
    with open(run_dir / "portfolio_performance.csv") as f:
        rows = list(csv.DictReader(f))
    last = rows[-1]
    out = []
    for name, init_balance in initial.items():
        final_value = float(last[name])
        pct = (final_value - init_balance) / init_balance * 100
        out.append((name, roles[name], final_value, pct))
    out.sort(key=lambda r: r[3], reverse=True)
    return out


def print_portfolio_table(run_dir: Path, agents: list[dict]) -> None:
    rows = final_returns(run_dir, agents)
    print(f"\n== Final portfolio (cycle {len(open(run_dir / 'portfolio_performance.csv').readlines()) - 1}) ==")
    print(f"{'Agent':<15} {'Role':<20} {'Final value':>14} {'Return':>9}")
    for name, role, value, pct in rows:
        print(f"{name:<15} {role:<20} {value:>14,.2f} {pct:>8.1f}%")
    pcts = [r[3] for r in rows]
    print(f"\nDispersion (max% - min%): {max(pcts) - min(pcts):.1f} pp")


def print_audit_summary(run_dir: Path) -> None:
    path = run_dir / "audit_report.json"
    if not path.exists():
        print("\n(no audit_report.json -- auditor was disabled for this run)")
        return
    with open(path) as f:
        report = json.load(f)
    s = report["summary"]
    print(f"\n== Audit summary ==")
    print(f"Actions audited: {s['total_actions_audited']}")
    print(f"Flag rate:  {s['flag_rate'] * 100:.1f}%")
    print(f"Block rate: {s['block_rate'] * 100:.1f}%")
    print(f"Avg threat score: {s['avg_threat_score']:.3f}")

    cats = report["manipulation_detection"]["detected_categories"]
    print("\nManipulation categories (detected actions):")
    for cat, count in sorted(cats.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {cat:<25} {count}")

    print("\nPer-agent risk rate (flagged_actions / total_actions):")
    profiles = report["agent_risk_profiles"]
    for name, p in sorted(profiles.items(), key=lambda kv: kv[1]["risk_rate"], reverse=True):
        print(f"  {name:<15} {p['risk_rate'] * 100:>5.1f}%  ({p['flagged_actions']}/{p['total_actions']})")


def print_dm_counts(run_dir: Path, pair: tuple[str, str] | None) -> None:
    with open(run_dir / "messages.csv") as f:
        rows = list(csv.DictReader(f))
    dms = [r for r in rows if r["recipient"] != "all"]

    if pair:
        a, b = pair
        count = sum(
            1 for r in dms
            if {r["sender"], r["recipient"]} == {a, b}
        )
        print(f"\nDMs between {a} <-> {b}: {count}")
        return

    from collections import Counter
    counts = Counter(frozenset((r["sender"], r["recipient"])) for r in dms)
    print("\n== Top DM pairs by volume ==")
    for pair_set, count in counts.most_common(8):
        a, b = sorted(pair_set)
        print(f"  {a:<15} <-> {b:<15} {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dirs", nargs="+", type=Path, help="one or more run directories (each with config.json, portfolio_performance.csv, ...)")
    parser.add_argument("--dm-pair", nargs=2, metavar=("AGENT_A", "AGENT_B"), help="count DMs between two specific agents instead of the top-8 table")
    args = parser.parse_args()

    for run_dir in args.run_dirs:
        config = load_config(run_dir)
        print(f"\n{'=' * 70}\n{run_dir}  (world={config.get('world', 'live')}, {config['num_cycles']} cycles, model={config['model']})\n{'=' * 70}")
        print_portfolio_table(run_dir, config["agents"])
        print_audit_summary(run_dir)
        print_dm_counts(run_dir, tuple(args.dm_pair) if args.dm_pair else None)


if __name__ == "__main__":
    main()
