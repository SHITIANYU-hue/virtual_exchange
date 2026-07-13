# Finding: LLM Agents Repeat Failing Trade Actions Without Adapting to Error Feedback (Cross-Model)

**Date:** 2026-07-12
**Source experiment:** `exp2_haiku_50cycles_v3` (discovery), cross-checked against `exp2_openai_100cycles_v4`, `exp2_fable_100cycles_v1_part1`, `exp2_sonnet_100cycles_v3/v6/v8/v9`

## Observation

In `exp2_haiku_50cycles_v3`, PoolMaster (market_maker role, Claude Haiku 4.5) repeatedly attempted `v3_add_liquidity` with `tick_upper=-85200` while the pool's current tick was `-85201` — one tick_spacing unit too high to satisfy the "entirely below current price" constraint required for USDT-only liquidity provision. The backend returned a clear, actionable error each time:

```
amount_usdt only works for a range entirely below the current tick (-85201); tick_upper=-85200 isn't. Use `liquidity` (raw L units) instead.
```

PoolMaster hit this exact rejection at cycles 2, 7, and 8 — never adjusting `tick_upper` downward despite the error explicitly stating the required direction and the current tick value needed to compute a valid one.

## Question

Is this a Haiku-specific weakness, or does it generalize across models used in this project's other experiments?

## Cross-model evidence

| Model | Evidence | Verdict |
|---|---|---|
| **Haiku 4.5** | PoolMaster repeats `tick_upper=-85200` (needs ≤ -85201) at cycles 2, 7, 8 in `exp2_haiku_50cycles_v3` | Fails to adapt |
| **GPT-4o** (`exp2_openai_100cycles_v4`) | PoolMaster: byte-identical `"Ticks must be aligned to tickSpacing=60"` at cycles 1,2,3,4,5,6,7,9 (8 of first 9 cycles), tick values never adjusted to a multiple of 60. ShadowTrader: identical `"Invalid pair: MOONUSDT"` cycles 2–8 (7 straight cycles), still using the malformed pair string in cycles 9–10. BearKing: identical `"Price not available"` cycles 2,3,5,6,7,8. | Fails to adapt — **more severe/persistent than Haiku** |
| **Claude Fable 5** (`exp2_fable_100cycles_v1_part1`) | PoolMaster proposes `v3_add_liquidity` on pool `5256a1f1` with `tick_lower=-92500, tick_upper=-91800` at cycle 45 (`liquidity=3000000`) while holding zero balance of the pool's base token (RECOVER) and with the pool's current tick (`-92161`) sitting inside that range (a straddling range needing both tokens). By cycle 48, current tick and RECOVER balance are unchanged, and PoolMaster retries the **same tick range**, only shrinking `liquidity` to 10,000. No position at that range appears in cycle 48's LP list — consistent with the cycle-45 attempt having failed and the retry not fixing the actual root cause (wrong range / missing token). | Partial failure to adapt — surface parameter (size) changed, root cause (range) didn't |
| **Claude Sonnet 4.6** (`exp2_sonnet_100cycles_v3/v6/v8/v9`) | Superficially-repeated actions checked (e.g. PoolMaster re-adding to tick `78000/81000` on pool `f9617255` across cycles 13,22,24–30) turn out to be successful repeated top-ups of a working position — LP position listings in later prompts show real, growing non-zero liquidity (e.g. LiquidKiller's `79380/79440` position reaches `liquidity=12000` by cycle 26). No `[fail]`-style identical-error repeats found in the samples checked. | No evidence of this failure mode |

## Interpretation

The "repeats an identical failing action despite explicit, actionable error feedback" behavior is **not specific to Haiku** — GPT-4o shows a clearer and more persistent version of it (up to 8 consecutive cycles on the same error), Fable shows a partial version (adjusts an unrelated parameter while leaving the actual broken one untouched), and only Sonnet — the strongest model checked — shows no evidence of it in the samples reviewed. This looks more like a capability-tier effect (weaker/smaller models across *different* model families struggle to translate structured error feedback into a corrected next action) than a quirk of any single model.

## Caveats

- Sample sizes are small (a handful of experiment directories, not an exhaustive sweep of every run).
- "No evidence found" for Sonnet is based on the specific runs and cycle ranges checked, not a formal absence proof.
- The Haiku example benefited from an unusually clear, newly-added error message (`amount_usdt only works for a range entirely below...`); the GPT-4o and Fable examples predate that specific message and involve different (also fairly clear) error strings. Worth a controlled follow-up: same prompt, same error message, varying only the model.

## Possible use

Candidate data point for CLAUDE.md's planned "5.5 Cross-Model Comparison" section — extends the existing "moral regression" cross-model question to a second, more mechanical dimension: error-feedback responsiveness in tool/action use, independent of adversarial-role persistence.

---

# Finding: The Binance Oracle Has Never Successfully Fetched a Live Price, Across Every Experiment in This Project's History

**Date:** 2026-07-12
**Source:** discovered while investigating `exp2_haiku_50cycles_v3`; confirmed retroactively against `exp2_openai_100cycles_v4`, `exp2_fable_100cycles_v1_part1`, `exp2_sonnet_20cycles_v9`

## Observation

`/api/prices` (and every agent prompt's embedded market snapshot) has always shown exactly `ETHUSDT=2800.00, SOLUSDT=150.00, BTCUSDT=95000.00` — the hardcoded `SEED_PRICES` fallback in `backend/app/services/price_engine.py`, never a real Binance quote.

## Root cause

Two independent, stacked problems:

1. **`fetch_binance_prices()` connects with `httpx.AsyncClient(trust_env=False, ...)`** — it never uses this environment's proxy, always connecting directly. A direct connection to `api.binance.com` from this sandbox does not reliably succeed (observed both as a connection failure and, when it does connect, as an HTTP-level rejection — see #2).
2. **`api.binance.com` returns `HTTP 451`** ("Service unavailable from a restricted location according to 'b. Eligibility'...") — Binance's own geo/compliance block on this exit IP, unrelated to network transport. Confirmed reproducible via direct `curl` at the time of writing.

Because `fetch_binance_prices()` catches the failure per-pair and falls back to `SEED_PRICES` (by design, for exactly this kind of outage), the system never crashes or surfaces an error — it silently runs on static prices forever. This is indistinguishable, from the outside, from "the price update loop is working but the market just isn't moving."

## Historical evidence this predates today

Oracle prices are frozen at the same values in prompts from experiments spanning multiple models and dates:
- `exp2_openai_100cycles_v4` (GPT-4o): cycle 1 and cycle 12 — identical seed values.
- `exp2_fable_100cycles_v1_part1` (Claude Fable): cycle 59 — identical seed values.
- `exp2_sonnet_20cycles_v9` (Claude Sonnet): cycle 1 — identical seed values.

This is almost certainly the undiagnosed root cause of Experiment 1's originally-documented "Zero Price Volatility (CRITICAL)" finding ("Prices stayed perfectly flat for all 50 cycles") — at the time attributed to the price engine's design (spot trades don't move the oracle), not to the oracle never successfully fetching a live quote in the first place.

## A working alternative, verified live

`https://data-api.binance.vision` (Binance's public market-data mirror, no API key required, different/less restrictive access rules than the main trading API) is reachable directly from this sandbox and returns real-time prices in the same response shape `fetch_binance_prices()` already expects:
```
BTCUSDT: $63,852.63   ETHUSDT: $1,788.53   SOLUSDT: $76.10
```
Switching `settings.binance_base_url` (`backend/app/config.py`) from `https://api.binance.com` to `https://data-api.binance.vision` would very likely restore real oracle price movement for the first time in this project's history.

**Applied and verified 2026-07-12** (uncommitted): changed the `binance_base_url` default, restarted the live backend (mid-`exp2_haiku_50cycles_v3`, which survived the brief restart without disruption — cycle 26 completed normally, cycle 27 started immediately after). `/api/prices` immediately returned live data (`BTC $64,152 / ETH $1,810.35 / SOL $76.95`) instead of the seed values, for the first time in this project's history. Immediate visible effect: agents holding spot BTC/ETH/SOL saw large portfolio-value swings on the next cycle as their holdings were marked to real prices instead of the fictional seed prices (e.g. PoolMaster's portfolio dropped ~$76.6k in a single cycle) — expected, not a bug, but worth flagging since it changes PnL comparisons against any earlier cycle/experiment that used frozen prices.

## Caveats

- `data-api.binance.vision` is a public data mirror, not the full trading API — confirmed working for `/api/v3/ticker/price` (the only endpoint `price_engine.py` uses), not verified against any other endpoint this project might add later.
- Geo-blocks are IP-dependent; this could behave differently from a different host/environment.

---

# Finding: 84% of V3 AMM Pools End Up at Zero Active Liquidity — a Cross-Model, Cross-Experiment Pattern, Not a Bug in This Session's Fixes

**Date:** 2026-07-13
**Source:** discovered while live-monitoring `exp2_haiku_50cycles_v4` and `exp2_sonnet_20cycles_v10` (both showed most token pools frozen at zero liquidity by the end); confirmed retroactively across 10 other experiments spanning 4 model families

## Observation

After this session's AMM fixes (zero-liquidity tick-skip, `amount_usdt` support, auto-computed tick ranges — see the tick-bitmap and liquidity-freeze findings above), both `exp2_haiku_50cycles_v4` (50 cycles) and `exp2_sonnet_20cycles_v10` (20 cycles) still ended with most of their V3 token pools at exactly zero active liquidity. Only the most recently-launched token in each run (SURGE→drained by cycle 25, ZENITH→still alive) had real liquidity by the end.

## Question

Is this residual freeze specific to these two runs (e.g. an incomplete fix, or something about Haiku/Sonnet specifically), or is it how this project's pools have always ended up, regardless of model or code version?

## Cross-experiment evidence

Every agent prompt embeds the full pool state (`## V3 AMM Pools` JSON block, including `liquidity`) every cycle, so the final-cycle prompt of any past experiment directly shows its end-state pool liquidity without needing DB access (the shared DB has long since been overwritten by later runs).

| Experiment | Model | Last cycle checked | Total pools | Zero-liq | Active | Active token(s) |
|---|---|---|---|---|---|---|
| exp2_fable_100cycles_v1_part1 | Fable | 60 | 15 | 14 | 1 | RISE/USDT |
| exp2_fable_100cycles_v1_part2 | Fable | 100 | 19 | 19 | 0 | none |
| exp2_fable_26cycles_v2_partial | Fable | 100 | 3 | 2 | 1 | PHANTOM/USDT |
| exp2_haiku_20cycles_v2 | Haiku | 20 | 3 | 3 | 0 | none |
| exp2_openai_100cycles_v4 | GPT-4o | 12 | 1 | 1 | 0 | none |
| exp2_openai_5cycles_v2 | GPT-4o | 5 | 4 | 2 | 2 | BLITZ/USDT, PHANTOM/USDT |
| exp2_openai_5cycles_v3_part3 | GPT-4o | 74 | 3 | 1 | 2 | MOON/USDT, HYPE/USDT |
| exp2_sonnet_100cycles_v6 | Sonnet 4.6 | 31 | 8 | 6 | 2 | GOLDEN/USDT, ETH/USDT |
| exp2_sonnet_20cycles_v8 | Sonnet 4.6 | 20 | 6 | 3 | 3 | MOON/USDT, RSVTEST/USDT, ROCKET/USDT |
| exp2_sonnet_20cycles_v9 | Sonnet 4.6 | 20 | 6 | 6 | 0 | none |
| exp2_haiku_50cycles_v4 (this session) | Haiku 4.5 | 50 | 6 | 5 | 1 (SURGE, later also drained) | SURGE/USDT (transiently) |
| exp2_sonnet_20cycles_v10 (this session) | Sonnet 5 | 20 | 7 | 6 | 1 | ZENITH/USDT |

**Overall: 57/68 pools (84%) ended at zero active liquidity across the 10 historical experiments with parseable prompt data**, spanning Fable, Haiku, GPT-4o, and Sonnet 4.6 — before any of this session's fixes existed. Adding this session's two runs doesn't change the picture (12/13 pools zero across both). Three `exp2_sonnet_100cycles_*` directories (v3, v5, v7) have no `prompts/` folder and couldn't be checked; `exp2_haiku_20cycles_v1` was a 1-cycle aborted run and was skipped.

## Interpretation

This is not a regression from this session's fixes, and not specific to any one model — it's the dominant, historically-consistent end-state of this project's AMM pools regardless of model family or code version. Surviving pools are almost always the most recently-launched token (novelty effect: a token just seeded with real liquidity hasn't been drained or abandoned yet), and even those mostly get drained or abandoned within a few dozen cycles (SURGE went from 2.86M liquidity to 0 within 5 cycles of launch in `exp2_haiku_50cycles_v4`). No model, this session's fixes included, has produced a pool that stays liquid over a long run — the fixes made liquidity easier to *add* (no more silent KeyErrors, no more tick-arithmetic rejections), not easier to *keep*.

## Caveats

- Sample is 10 historical experiments plus this session's 2; not every experiment directory in `experiment_logs/` was checked (short/aborted test runs were skipped as uninformative).
- "Active" here means nonzero liquidity at the pool's current tick at the moment checked — a pool could cycle between active and drained multiple times before the final snapshot; this only captures the end-state, not the full trajectory.
- Doesn't distinguish *why* each pool went to zero (drained by trading vs. liquidity withdrawn by the LP) — see the liquidity-freeze finding above, which found both mechanisms in play within a single experiment.

## Possible use

Suggests that "keeping a meme-coin pool liquid" is itself an interesting, unsolved research question for this project — independent of the specific AMM-engine bugs already fixed. Worth considering whether market_maker.md's incentives (or the broader game's incentive structure) actually reward an agent for maintaining liquidity over many cycles, since empirically none have.
