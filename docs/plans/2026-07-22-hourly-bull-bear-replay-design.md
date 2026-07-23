# Hourly Bull/Bear Replay — Engineering Design

> Companion to [`virtual-exchange-hourly-replay-handoff.md`](virtual-exchange-hourly-replay-handoff.md), which is the authoritative experimental spec (dates, blinding rules, completion criteria). This document maps that spec onto the actual codebase: concrete files, functions, config fields, and the decisions the handoff leaves to the implementer. Where the handoff is silent, this doc states an explicit default and flags it `[CONFIRM]`.

## 1. What already exists vs. what's new

Checked against the current `su/exp2` tree:

| Handoff requirement | Status |
|---|---|
| BTC/ETH/SOL as anchor assets | Already the only 3 oracle pairs (`TRADING_PAIRS` in `backend/app/services/price_engine.py:14`) |
| 1h candle granularity | New — engine currently only does live-ticker polling (`fetch_binance_prices`, same file) |
| Historical replay price mode | New |
| Turn = one hourly candle, agents see `t-1` only | New — maps onto the existing per-`cycle` loop in `experiments/run_experiment.py:388` |
| Same price snapshot for all agents in a turn | Already true structurally (all agents in a cycle call `GET /api/prices` against the same in-memory `current_prices` before it's advanced — see §4.3) |
| No real dates/labels reach agents | Already true today — `build_agent_prompt` (`agents/run.py:446`) injects `state["prices"]` (a plain `{pair: price}` dict) and role/memory text; there is no `datetime.now()`/date string anywhere in the prompt-building path (verified by grep). The only new leakage surface is the replay machinery itself (§5). |
| Data validation, no live/seed fallback on gaps | New |

So the blinding requirement is *mostly free* — the existing prompt pipeline was never date-aware. The work is: build the replay price source, wire one advance-per-cycle into the runner, and make sure the *new* code doesn't introduce a leak the old code didn't have.

## 2. Data preparation

### 2.1 Intervals (from the handoff, restated for the download script)

| World | Real interval | Rationale |
|---|---|---|
| Bull | 2024-11-06T00:00Z → 2024-11-09T00:00Z | Post-election BTC breakout |
| Bear | 2026-06-04T00:00Z → 2026-06-07T00:00Z | BTC ~$67k → ~$59k rout |

Each needs **73 hourly candles** per asset: candle `-1` (the hour immediately before the interval start, so Turn 1 has a "previous hour" to show) plus the 72 formal hours. Concretely: download `[start - 1h, start + 72h)` half-open, 73 candles, for `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, both worlds → 6 CSVs.

### 2.2 Script: `experiments/scenarios/download_hourly_replay.py`

- Source: `data-api.binance.vision` (`/api/v3/klines?symbol=...&interval=1h&startTime=...&endTime=...&limit=100`), same mirror already configured via `settings.binance_base_url`.
- Output: `experiments/scenarios/hourly_replay/{bull,bear}/{BTCUSDT,ETHUSDT,SOLUSDT}.csv` — columns `open_time_ms, close`.
- **Hard validation, no silent recovery** (per handoff §数据准备): after download, assert per asset per world: exactly 73 rows, strictly increasing `open_time_ms` with a constant 3,600,000 ms step, no duplicate timestamps. Any violation → the script exits non-zero and writes nothing usable; it does **not** fall back to live/seed prices. This mirrors the existing `price_engine.py` fallback behavior being explicitly *disabled* for replay mode (§3).
- Also assert the three assets within one world share identical `open_time_ms` sequences (handoff: "三个币种必须使用相同的时间范围，并且每个小时严格对齐").

## 3. Backend: replay price mode

### 3.1 Config (`backend/app/config.py`)

```python
price_mode: str = "live"              # "live" | "replay"
replay_world: str = ""                # "A" | "B" — meaningless label, resolved via private mapping (§6)
replay_data_dir: str = "experiments/scenarios/hourly_replay"
replay_common_start_price: dict[str, str] = {
    "BTCUSDT": "95000", "ETHUSDT": "2800", "SOLUSDT": "150",
}  # DECIDED: reuse the existing SEED_PRICES values (price_engine.py:17-21) as the
   # common start, so this experiment's price scale matches every prior run's.
```

### 3.2 Price normalization

Per handoff §双盲处理, replayed prices must not expose absolute historical price levels:

```
replay_price[t] = common_start_price × historical_close[t] / historical_close[-1]
```

i.e. every asset is rebased so that candle `-1` (Turn 1's "previous hour") equals the project's existing seed price, and every subsequent hour scales by the real historical return from that anchor. This is a straight port of the ratio formula in the handoff — implemented once, in `ReplayPriceSource._rebase()`, applied at load time to all 73 candles per asset.

### 3.3 `ReplayPriceSource` (`backend/app/services/price_engine.py`)

- On startup with `price_mode="replay"`: resolve `replay_world` → real scenario name via the private mapping (§6) — this indirection happens **inside the backend process only**; nothing world-labeled ever reaches an HTTP response.
- Load the 3 CSVs for that scenario, apply `_rebase()`, hold an index `t` starting at `0` (→ candle `-1`, the pre-interval hour).
- `advance() -> dict[str, Decimal]`: `t += 1`, publish `current_prices` from candle `t-1`'s rebased close (so after the first `advance()`, index 0 = the real interval's first hour), persist a `PriceHistory` row (timestamp = real wall-clock insert time, **not** the historical timestamp — this is important: `PriceHistory` rows must carry today's UTC time, or a réplay-hour column would itself leak the historical date), broadcast the websocket update, run `check_liquidations()`.
- Cursor past candle 72: hold the last price, log a warning; the experiment should never request this (72 turns = 72 `advance()` calls after the initial load, matching the 72 formal hours exactly).
- `price_update_loop()` (the live 120s poller) is **fully disabled** in replay mode — no Binance calls, no live-price mixing.

### 3.4 Advance endpoint (`backend/app/api/prices.py`)

```
POST /api/admin/replay/advance   # mirrors the existing /api/admin/hard-reset pattern (admin.py:11)
→ {"turn": 5, "prices": {"BTCUSDT": "97650.32", ...}}
```

No world label, no historical date, no scenario name in the response — just turn number and prices, which is exactly what Turn `t`'s agents are allowed to see per the handoff. Idempotency guard keyed on turn number (same pattern as the daily-replay plan from 07-20), so a retried call from the runner can't double-advance.

## 4. Runner integration (`experiments/run_experiment.py`)

### 4.1 Turn ≡ cycle

The handoff's "turn" is exactly the existing `cycle` loop (`run_experiment.py:388`). No new loop construct — `--cycles 72` *is* "72 turns". `--delay` stays purely an LLM-pacing knob (handoff: "系统运行速度不需要真的等待一小时" — already true, `cycle_delay` never touched wall-clock/historical time).

### 4.2 New flag

```
--world {A,B}
```

Resolves internally (via the same private-mapping indirection as §3.3) to the real scenario. **Nothing else about world identity may reach `config.json`, console output, or `exp_dir`'s name.** Concretely:
- `config.json` (`run_experiment.py:355-370`) gets a `"world": "A"` field — fine, it's already meaningless.
- The existing `--label` flag must be passed as `World-A` / `World-B` by the operator (not `bull-72turns` or similar) — this is an operating discipline, not something the code can fully enforce, but I'll add a startup assertion that rejects `--label` values containing `bull`, `bear`, or any 4-digit year, as a guardrail against an accidental leak.

### 4.3 Per-cycle advance, AFTER all agents act

Corrected during implementation: the handoff's stated order is "read previous hour → agents analyze/trade → audit/execute → **then** advance → next turn" — i.e. advance happens at the **end** of each cycle, not the start. The replay source is preloaded at backend startup already sitting on candle 0 (the pre-interval hour), so Turn 1's agents read that without any advance() call; each cycle's advance() call (placed right after the status-snapshot write, `run_experiment.py`) prepares the *next* turn's price. Since nothing mutates `current_prices` mid-cycle, all agents within a turn trivially see the same snapshot regardless of exactly where in the cycle the call sits — but it must come after the agent loop, not before, or Turn 1 would skip the pre-interval hour entirely.

### 4.4 Startup validation

Before cycle 1: assert the backend reports `price_mode == "replay"` and the resolved world's candle count is exactly 73; abort with a clear error otherwise (never silently fall back to live prices — same fail-fast principle as §2.2).

## 5. What must NOT leak (checklist against handoff §双盲处理)

| Channel | Risk | Mitigation |
|---|---|---|
| `config.json` | `--model`, `--label` already recorded | Label is enforced to be `World-A`/`World-B` (§4.2); no scenario/date fields added |
| Console/log output | Cycle print already shows only `{cycle}/{total_cycles}` + wall-clock UTC (today's real time, not historical) | No change needed |
| `PriceHistory` rows | Could carry historical timestamp | Explicitly store real insert time (§3.3) |
| `GET /api/prices/{pair}/history` | Returns `PriceHistory.timestamp` | Already real insert time once §3.3 is implemented — agents calling this see recent real dates, never 2024/2026-historical dates |
| Agent prompt (`build_agent_prompt`) | None found — no date/label string anywhere in the function | No change |
| Backend logs (uvicorn/docker) | Could print scenario name at replay-source load time | Log only "replay mode active, N candles loaded" — never the resolved world/date at INFO level reachable outside the container |

## 6. Private world↔scenario mapping

`experiments/.private_world_mapping.json` (added to `.gitignore` — the file must never be committed, or `git log`/`git show` defeats the blind for the human analyst too, which the handoff implies by "分析结果完成之后再揭示对应关系"):

```json
{"A": "bull", "B": "bear"}
```

Only `ReplayPriceSource` and the operator's post-hoc analysis script read this file. It is never copied into `experiments/experiment_logs/**` (which is git-tracked and analyzable mid-experiment).

## 7. Logging (handoff completion-criteria #8)

Reuses all existing per-cycle artifacts (`prompts/`, `actions/`, `status/`, `errors/`, `portfolio_performance.csv`, `messages.csv`) unchanged — they already record per-agent action, wallet state, and trade outcome per cycle. Additions:
- `status/cycle_{t}.json` gains a `"prices"` key with that turn's `t-1` snapshot (currently status snapshots record balances/positions but not the price agents saw — worth adding for post-hoc analysis of what price info drove each decision).
- Audit events already logged via the existing `audit_events.csv` / `audit_report.json` pipeline (unchanged — audit stays in whatever mode is fixed for both worlds, §8).

## 8. Fixed configuration across both worlds (nothing here should vary — only the price path varies)

- **Agents**: all 10, per `agents/ecosystem.json`, `--hard-reset` before each world (clean state, matching the handoff's "初始资金和持仓" invariance).
- **Agent LLM**: `claude-haiku-4-5-20251001` — the standard used in reps 1-3. DECIDED.
- **Auditor**: default `block_and_flag`, `AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929` — same as the `Taudit` reps, kept ON so the experiment measures regime effects under the auditor's real standing behavior rather than an artificially unmoderated market. DECIDED.
- **Cycles**: 72 (first run), `--delay` whatever LLM-rate-limit pacing is currently used (e.g. 2s) — irrelevant to historical time per §4.1.

## 9. First-run commands (once implemented)

```bash
python3 experiments/scenarios/download_hourly_replay.py   # one-time, validates + writes 6 CSVs

# World A
AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929 python3 experiments/run_experiment.py \
  --world A --cycles 72 --delay 2 --hard-reset \
  --model claude-haiku-4-5-20251001 --label World-A

# World B
AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929 python3 experiments/run_experiment.py \
  --world B --cycles 72 --delay 2 --hard-reset \
  --model claude-haiku-4-5-20251001 --label World-B
```

Sequential, not parallel — both hard-reset the same shared DB (same constraint that broke the rep4/rep5 queue on 07-21; a single Docker outage or auth-env miss must abort that world's run cleanly rather than run 72 turns of silently-failed LLM calls — the runner's existing `_classify_bad_cycle` abort path (`run_experiment.py:81`) already exists for exactly this and should be checked before this run, not discovered after another wasted multi-hour run).

## 10. Extension (handoff §实验扩展)

`--cycles 96/120/168` with the *same* `--world` flag just needs `download_hourly_replay.py` re-run with a longer `endTime` for both worlds (start times fixed, per handoff — "不改变已经确定的起始时间"). The 73-candle-minimum validation in §2.2 generalizes to `N+1` candles for `N` turns.

## Decisions (2026-07-22)

1. **Common start price**: reuse existing `SEED_PRICES` (BTC $95,000 / ETH $2,800 / SOL $150) — matches every prior experiment's price scale, so agent behavior isn't confounded by an unfamiliar price regime on top of the market-regime variable being studied.
2. **Auditor**: stays ON, default `block_and_flag` + `AUDITOR_LLM_MODEL=claude-sonnet-4-5-20250929`, identical across both worlds — this experiment isolates market regime (bull vs bear), not auditor presence, so the auditor is held fixed at its normal standing configuration rather than disabled.
3. **Mapping reveal**: manual. Once both worlds have completed all 72 turns and the portfolio/audit CSVs are pulled for analysis, open `experiments/.private_world_mapping.json` directly — no automated reveal script needed for a two-arm, single-analyst experiment.
