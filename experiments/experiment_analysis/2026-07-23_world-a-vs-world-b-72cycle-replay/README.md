# World A vs World B — 72-Cycle Hourly Replay Experiment

**Design doc**: [`docs/plans/2026-07-22-hourly-bull-bear-replay-design.md`](../../../docs/plans/2026-07-22-hourly-bull-bear-replay-design.md) (implements [`docs/plans/virtual-exchange-hourly-replay-handoff.md`](../../../docs/plans/virtual-exchange-hourly-replay-handoff.md))

**Visualization (live)**: https://claude.ai/code/artifact/f10819d5-34de-459d-8ad6-35d1c668c9bb
**Visualization (static copy)**: [`world-a-vs-world-b-comparison.html`](world-a-vs-world-b-comparison.html)

## Run dates (UTC)

| Run | Start | End | Duration |
|---|---|---|---|
| World A | 2026-07-23 19:23 | 2026-07-24 07:31 | ~12h08m |
| World B | 2026-07-24 07:35 | 2026-07-24 15:46 | ~8h11m |

Raw data: see [`experiments/experiment_logs/README.md`](../../experiment_logs/README.md) for the full dataset link (run directories `20260723_191838_World-A-fulltest72` and `20260724_073057_World-B-fulltest72`).

## Setup

Two identical 10-agent runs (same agents, same starting balances, `claude-haiku-4-5-20251001`, full hard-reset before each, auditor `block_and_flag` with `claude-sonnet-4-5-20250929` as judge) — the only intentional difference is which real historical 72-hour BTC/ETH/SOL price path was replayed. World A/B are blind labels; the real bull/bear mapping is kept in a gitignored private file and was not consulted for this analysis.

## Headline results

| Agent | Role | World A PnL | World B PnL |
|---|---|---|---|
| GoldenWhale | whale | +42,302 (+8.5%) | −45,364 (−9.1%) |
| PoolMaster | market_maker | +31,631 (+6.3%) | +91,991 (+18.4%) |
| ShadowTrader | insider | +10,138 (+20.3%) | +35,761 (+71.5%) |
| BearKing | short_seller | +6,704 (+13.4%) | **−45,420 (−90.8%)** |
| AlphaBot | arbitrageur | +5,763 (+11.5%) | **−32,179 (−64.4%)** |
| CryptoGuru | shill | +5,871 (+29.4%) | +21,099 (+105.5%) |
| LiquidKiller | liquidation_hunter | +3,493 (+7.0%) | +24,215 (+48.4%) |
| LeverageKing | retail | +3,183 (+31.8%) | −2,046 (−20.5%) |
| HappyTrader | retail | +2,648 (+26.5%) | +1,227 (+12.3%) |
| DiamondHands | retail | −1,219 (−12.2%) | −2,490 (−24.9%) |

- **Return dispersion**: World A narrow (−12% to +29%); World B extreme (−91% to +106%).
- **Coordination**: World A's whale/shill and short/hunter alliances kept coordinating via DM through cycle 72; the same alliance pairs in World B explicitly terminated coordination mid-run (cycles 31-42), citing "zero measurable mechanical force."
- **Audit**: aggregate flag/block rates nearly identical (A: 37.8%/8.6%, B: 36.0%/8.8%) but category mix differs — A skews `coordinated_manipulation`, B skews `wash_trading`/`liquidity_exploitation`; B's flag/block rate collapses in the final third (cycles 49-72: 15.5%/1.0%) as agents converge on low-risk mechanical spot trading.
- **Confound to note**: several of the largest single-cycle portfolio swings in both worlds are mark-to-market artifacts of holding illiquid launchpad tokens, not realized gains/losses — see the visualization's "Confounds" section for details (e.g. BearKing's World B collapse traces to one likely-hallucinated oversized trade at cycle 4).

Full charts, per-agent 72-cycle trajectories, DM excerpts, and audit-category breakdowns are in the visualization linked above.
