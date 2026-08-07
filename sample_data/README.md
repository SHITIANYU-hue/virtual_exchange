# Sample experiment output

One complete run (`World A`, auditor `block_and_flag`, 72 cycles,
`claude-haiku-4-5-20251001`) kept in full as a concrete example of what
`run_experiment.py` produces — `config.json`, `portfolio_performance.csv`,
`messages.csv`, `audit_report.json`/`audit_events.csv`, and a per-cycle
`status/cycle_N.json` snapshot for every agent.

This is one run out of the 20+ backing the results in
[`../analysis/`](../analysis/). The full dataset (all runs, all
market regimes and auditor configurations) is published separately — see
[`../docs/EXPERIMENTS.md`](../docs/EXPERIMENTS.md).

Recompute the headline numbers directly from this directory:

```bash
python3 ../analysis/analyze_run.py .
```
