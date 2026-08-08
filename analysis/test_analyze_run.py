"""
Unit tests for analyze_run.py, run against the real sample run checked into
sample_data/ (no fixtures -- that directory *is* the fixture).

Run directly: python3 analysis/test_analyze_run.py
Requires: sample_data/ (checked into the repo).
"""
import csv
import sys
from pathlib import Path

ANALYSIS_DIR = Path(__file__).parent
REPO_ROOT = ANALYSIS_DIR.parent
SAMPLE_RUN = REPO_ROOT / "sample_data"
sys.path.insert(0, str(ANALYSIS_DIR))

from analyze_run import (  # noqa: E402
    load_config,
    final_returns,
    load_audit_report,
    load_dms,
    dm_count,
    top_dm_pairs,
)


def test_final_returns_matches_raw_csv():
    config = load_config(SAMPLE_RUN)
    agents = config["agents"]
    rows = final_returns(SAMPLE_RUN, agents)

    assert len(rows) == len(agents), "one row per agent"
    names = {r[0] for r in rows}
    assert names == {a["name"] for a in agents}, "every configured agent appears exactly once"

    # Cross-check against the raw CSV independently, one agent at a time.
    with open(SAMPLE_RUN / "portfolio_performance.csv") as f:
        last_row = list(csv.DictReader(f))[-1]
    by_name = {r[0]: r for r in rows}
    for agent in agents:
        name, initial = agent["name"], agent["initial_balance"]
        _, role, final_value, pct = by_name[name]
        expected_value = float(last_row[name])
        assert final_value == expected_value, f"{name}: final_value should match the CSV's last row"
        assert role == agent["role"]
        expected_pct = (expected_value - initial) / initial * 100
        assert abs(pct - expected_pct) < 1e-9, f"{name}: return_pct formula mismatch"

    # Sorted descending by return.
    pcts = [r[3] for r in rows]
    assert pcts == sorted(pcts, reverse=True), "final_returns should be sorted best-to-worst"
    print(f"final_returns: {len(rows)} agents, all values cross-checked against portfolio_performance.csv, "
          f"sorted descending (best {pcts[0]:.1f}%, worst {pcts[-1]:.1f}%)")


def test_audit_report_structure():
    report = load_audit_report(SAMPLE_RUN)
    assert report is not None, "sample run has the auditor enabled -- audit_report.json should exist"

    s = report["summary"]
    assert 0.0 <= s["flag_rate"] <= 1.0
    assert 0.0 <= s["block_rate"] <= 1.0
    assert s["flagged_count"] <= s["total_actions_audited"]
    assert s["blocked_count"] <= s["flagged_count"], "a blocked action should also count as flagged"

    profiles = report["agent_risk_profiles"]
    config = load_config(SAMPLE_RUN)
    agent_names = {a["name"] for a in config["agents"]}
    assert set(profiles.keys()) == agent_names, "every agent should have a risk profile"
    for name, p in profiles.items():
        assert p["flagged_actions"] <= p["total_actions"], f"{name}: flagged can't exceed total"
        assert abs(p["risk_rate"] - p["flagged_actions"] / p["total_actions"]) < 1e-9, f"{name}: risk_rate formula mismatch"

    total_by_agent = sum(p["total_actions"] for p in profiles.values())
    assert total_by_agent == s["total_actions_audited"], "per-agent totals should sum to the report total"
    print(f"audit_report: {s['total_actions_audited']} actions, {len(profiles)} agent risk profiles, "
          f"all rates internally consistent")


def test_missing_audit_report_returns_none(tmp_run=None):
    empty_dir = ANALYSIS_DIR / "__no_such_run_dir_for_test__"
    assert not empty_dir.exists()
    assert load_audit_report(empty_dir) is None, "a run dir with no audit_report.json should return None, not raise"
    print("load_audit_report: missing file correctly returns None (auditor-disabled runs)")


def test_dm_count_matches_manual_scan():
    dms = load_dms(SAMPLE_RUN)
    assert all(r["recipient"] != "all" for r in dms), "load_dms should exclude broadcasts"

    pairs = top_dm_pairs(SAMPLE_RUN, n=3)
    assert len(pairs) > 0, "sample run should have some DM traffic"
    top_pair, top_count = pairs[0]
    a, b = sorted(top_pair)

    # Recompute the top pair's count with a naive manual loop and cross-check.
    manual_count = sum(1 for r in dms if {r["sender"], r["recipient"]} == {a, b})
    assert manual_count == top_count, "top_dm_pairs count should match a manual scan"

    # dm_count should agree, and be symmetric in argument order.
    assert dm_count(SAMPLE_RUN, a, b) == top_count
    assert dm_count(SAMPLE_RUN, b, a) == top_count, "dm_count should not care about argument order"
    assert dm_count(SAMPLE_RUN, a, a) == 0, "an agent can't DM itself in this dataset"
    print(f"dm_count/top_dm_pairs: cross-checked against a manual scan (top pair {a} <-> {b}: {top_count} DMs)")


if __name__ == "__main__":
    test_final_returns_matches_raw_csv()
    test_audit_report_structure()
    test_missing_audit_report_returns_none()
    test_dm_count_matches_manual_scan()
    print("\nAll analyze_run.py unit tests passed.")
