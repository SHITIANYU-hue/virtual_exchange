# Experiment Analysis Summary

This directory contains a curated summary of the currently retained experiment runs under `experiments/experiment_logs`.

## What Was Removed

The following runs were deleted because they were effectively unusable:

- `20260320_001159`
- `20260320_001328`
- `20260320_152934`
- `20260320_153138`
- `20260324_234356`
- `20260325_094906`
- `20260325_094940`
- `20260325_145054`
- `haiku_whale5B_20260320_000544`

## How To Read The Metrics

- `naive_final_pnl_usdt`: PnL from the final row of `portfolio_performance.csv`
- `forward_fill_final_pnl_usdt`: PnL after replacing trailing zero snapshots with each agent's last non-zero portfolio value
- `zero_snapshot_rate_pct`: share of portfolio cells recorded as zero; high values usually indicate parse failures, missing snapshots, or refusal cycles rather than true bankruptcy
- `ending_zero_agents`: number of agents whose final snapshot is zero

## Recommended Usage

### Best functional validation

- `20260320_164856`
  - Token factory and V3 trading are working.
  - Real trading losses are visible.
  - Best run for showing that the mechanism executes end-to-end.

### Best long-horizon behavioral run

- `20260325_210819`
  - 50-cycle run with the strongest behavioral signal.
  - Forward-filled final PnL is positive (`+6751.12` USDT).
  - Use with caution because missing snapshots remain common.

### Usable only with correction

- `20260317_220751`
- `20260320_002049`
- `haiku_20260319_191745`

These runs are analyzable only if zero portfolio snapshots are treated as missing data.

### Exclude from economic analysis

- `20260317_000113`
  - Fully broken; zero snapshots throughout.
- `20260317_000549`
  - Terminates into all-zero final snapshots despite heavy message volume.
- `20260317_233818`
  - Sonnet parsing is excellent, but AMM overflow makes portfolios explode to invalid magnitudes.

## Main Cross-Run Findings

1. The dominant data-quality problem is not just poor final performance; it is missing or malformed state snapshots.
2. Once token creation and V3 trading were fixed, manipulative and defensive multi-agent behavior became visible in both messages and portfolio changes.
3. The cleanest mechanism-validating run is `20260320_164856`, while the best retained long-run behavior study is `20260325_210819`.
4. Forward-fill correction is necessary for several Haiku-era runs; otherwise the final-row PnL severely understates outcomes.

## Inventory

See `experiment_inventory.csv` in this directory for the current retained run list and classification.
