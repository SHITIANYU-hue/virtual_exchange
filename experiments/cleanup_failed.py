#!/usr/bin/env python3
"""
Cleanup agent for failed experiment logs.

Identifies and deletes experiment directories that are:
  1. Explicitly labeled with '-fail-' in the directory name
  2. All-zero portfolio runs (API key was missing or all agents errored out)
  3. Optionally: runs shorter than a minimum cycle threshold

Usage:
    python3 experiments/cleanup_failed.py           # dry run (shows what would be deleted)
    python3 experiments/cleanup_failed.py --delete  # actually delete
    python3 experiments/cleanup_failed.py --min-cycles 5 --delete
"""

import argparse
import csv
import json
import shutil
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "experiment_logs"


def is_all_zero_portfolio(csv_path: Path) -> bool:
    """Return True if every agent's portfolio value is 0 across all cycles."""
    try:
        with open(csv_path) as f:
            reader = csv.reader(f)
            header = next(reader)
            agent_cols = list(range(2, len(header)))
            if not agent_cols:
                return True
            for row in reader:
                if not row:
                    continue
                for col in agent_cols:
                    try:
                        if col < len(row) and float(row[col]) != 0.0:
                            return False
                    except (ValueError, IndexError):
                        pass
        return True
    except Exception:
        return True


def load_config(exp_dir: Path) -> dict:
    config_path = exp_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def is_currently_running(exp_dir: Path) -> bool:
    """True if a process appears to be actively writing to this directory."""
    # If the CSV has a header but no data rows yet, it may be mid-run
    csv_path = exp_dir / "portfolio_performance.csv"
    if not csv_path.exists():
        return False
    try:
        with open(csv_path) as f:
            lines = [l for l in f if l.strip()]
        # Header only = experiment started but no cycle completed yet
        return len(lines) == 1
    except Exception:
        return False


def has_analysis(exp_dir: Path) -> bool:
    """True if the directory contains a researcher-written analysis file."""
    return (exp_dir / "ANALYSIS.md").exists()


def classify_experiment(exp_dir: Path, min_cycles: int) -> tuple[bool, str]:
    """
    Returns (should_delete, reason).

    Safety rules (always protect):
      - Directories with ANALYSIS.md (researcher has reviewed them)
      - Directories with '-success-' in name
      - Directories that appear to be currently running
    """
    name = exp_dir.name

    # Safety: never delete analysed or success-labeled experiments
    if has_analysis(exp_dir):
        return False, ""
    if "-success-" in name:
        return False, ""
    if is_currently_running(exp_dir):
        return False, ""

    # Rule 1: explicit fail label in directory name
    if "-fail-" in name:
        return True, "explicitly labeled as failure (-fail- in name)"

    # Rule 2: all-zero portfolios (API key was missing or all agents errored)
    csv_path = exp_dir / "portfolio_performance.csv"
    if csv_path.exists() and is_all_zero_portfolio(csv_path):
        return True, "all portfolio values are zero (agents never ran)"

    # Rule 3: too few cycles completed
    if min_cycles > 0 and csv_path.exists():
        try:
            with open(csv_path) as f:
                rows = sum(1 for row in csv.reader(f)) - 1  # subtract header
            config = load_config(exp_dir)
            planned = config.get("num_cycles", 0)
            if rows < min_cycles and (planned == 0 or rows < planned):
                return True, f"only {rows} cycles completed (threshold: {min_cycles})"
        except Exception:
            pass

    return False, ""


def main():
    parser = argparse.ArgumentParser(description="Cleanup failed experiment logs")
    parser.add_argument("--delete", action="store_true",
                        help="Actually delete (default is dry run)")
    parser.add_argument("--min-cycles", type=int, default=0,
                        help="Also delete runs with fewer than N completed cycles")
    parser.add_argument("--logs-dir", type=str, default=str(LOGS_DIR),
                        help=f"Experiment logs directory (default: {LOGS_DIR})")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    if not logs_dir.exists():
        print(f"Logs directory not found: {logs_dir}")
        return

    experiments = sorted(p for p in logs_dir.iterdir() if p.is_dir())

    if not experiments:
        print("No experiment directories found.")
        return

    to_delete = []
    to_keep = []

    for exp_dir in experiments:
        should_delete, reason = classify_experiment(exp_dir, args.min_cycles)
        config = load_config(exp_dir)
        size_mb = sum(f.stat().st_size for f in exp_dir.rglob("*") if f.is_file()) / 1e6

        if should_delete:
            to_delete.append((exp_dir, reason, size_mb, config))
        else:
            to_keep.append((exp_dir, size_mb, config))

    # Report
    print(f"\n{'='*65}")
    print(f"EXPERIMENT CLEANUP — {'DRY RUN' if not args.delete else 'DELETE MODE'}")
    print(f"{'='*65}")

    if to_keep:
        print(f"\n[KEEP] {len(to_keep)} experiment(s):")
        for exp_dir, size_mb, config in to_keep:
            model = config.get("model", "?")
            cycles = config.get("num_cycles", "?")
            agents = len(config.get("agents", []))
            print(f"  ✓  {exp_dir.name:<50}  {size_mb:5.1f}MB  ({agents} agents, {cycles} cycles, {model})")

    if to_delete:
        print(f"\n[DELETE] {len(to_delete)} experiment(s):")
        total_mb = sum(mb for _, _, mb, _ in to_delete)
        for exp_dir, reason, size_mb, config in to_delete:
            model = config.get("model", "?")
            cycles = config.get("num_cycles", "?")
            print(f"  ✗  {exp_dir.name:<50}  {size_mb:5.1f}MB  → {reason}")

        print(f"\n  Total to free: {total_mb:.1f} MB")

        if args.delete:
            print("\nDeleting...")
            deleted = 0
            for exp_dir, reason, size_mb, _ in to_delete:
                try:
                    shutil.rmtree(exp_dir)
                    print(f"  [deleted] {exp_dir.name}")
                    deleted += 1
                except Exception as e:
                    print(f"  [error]   {exp_dir.name}: {e}")
            print(f"\nDone. {deleted}/{len(to_delete)} directories deleted.")
        else:
            print("\nRun with --delete to actually remove these.")
    else:
        print("\nNothing to delete.")


if __name__ == "__main__":
    main()
