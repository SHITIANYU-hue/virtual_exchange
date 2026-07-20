# Historical Replay Price Mode (真实历史行情回放)

> Replace the live-ticker oracle with replayable real Binance historical klines, so experiments can run under real bull / bear / crash / sideways market regimes.

## Background & Motivation

The price engine (`backend/app/services/price_engine.py`) currently has exactly one mode: every `price_update_interval` (120s) it fetches the **live spot price** from `data-api.binance.vision` (`/api/v3/ticker/price`). Over a multi-hour experiment, BTC/ETH/SOL spot barely moves — this is the root cause of Experiment 1's "zero price volatility" failure (prices flat for all 50 cycles, pump & dump physically impossible, inaction was the Nash equilibrium).

Rather than the synthetic-volatility overlay sketched in CLAUDE.md (Priority 1, Option C), this plan replays **real historical market trajectories**. Advantages:

- Trends, drawdowns, and crashes are real — no need to justify a synthetic price model in the paper.
- Experiments are **reproducible**: the same scenario file yields the identical price path every run.
- Runs are **offline-safe**: klines are pre-downloaded to local CSV, so the sandbox network outages that destroyed 76/100 cycles of `exp2_sonnet_100cycles_v7` cannot touch the price feed.
- Enables a regime-comparison study: same agents, same prompts, different market regimes → a natural controlled experiment for the paper (Section 4.x / 5.3).

## Market Scenarios

Pre-defined windows, one CSV per pair per scenario, checked into `experiments/scenarios/`:

| Scenario | Window | BTC trajectory | Notes |
|----------|--------|----------------|-------|
| `bull` | 2020-10-01 → 2021-04-14 | $10.5K → $64K | Sustained uptrend with pullbacks |
| `bear` | 2021-11-08 → 2022-06-18 | $69K → $17K | Grinding downtrend, LUNA/3AC cascades |
| `crash` | 2021-05-01 → 2021-05-31 | $58K → $34K | Single violent leg down |
| `sideways` | 2023-08-01 → 2023-10-15 | ~$29K chop | Control regime (closest to Exp 1 conditions) |

All three oracle pairs (BTCUSDT, ETHUSDT, SOLUSDT) are downloaded for each window so cross-asset correlation is preserved. SOL only exists from 2020-08 on Binance, which all windows satisfy.

## Key Design Decision: advance per cycle, not per wall-clock tick

The replay cursor advances **one candle per experiment cycle**, driven by the experiment runner — not by the 120s background loop. Consequences:

- Candle interval controls how much market history an experiment covers: 100 cycles × `1h` klines ≈ 4 days of market; 100 cycles × `1d` klines = the full 5-month bull/bear regime.
- `--delay` (LLM pacing) no longer affects market speed; a run interrupted and resumed with `--start-cycle` stays aligned with the price path.
- Agents see exactly one new price observation per decision, mirroring the discrete-time structure of the rest of the simulation.

## Architecture

### 1. Config (`backend/app/config.py`)

```python
price_mode: str = "live"          # "live" | "replay"
replay_scenario: str = "bull"     # subdirectory under experiments/scenarios/
replay_interval: str = "1d"       # kline granularity of the scenario files
replay_start_index: int = 0       # candle offset (for --start-cycle continuations)
scenarios_dir: str = "experiments/scenarios"
```

Settable via `.env` / environment, so the backend can be launched in replay mode without code changes.

### 2. Scenario downloader (`experiments/download_scenarios.py`)

One-time script (network required only here, never at run time):

- For each scenario × pair, page through `GET {binance_base_url}/api/v3/klines?symbol=...&interval=...&startTime=...&endTime=...&limit=1000` (free, no API key, same mirror already used by the price engine).
- Write `experiments/scenarios/{scenario}/{pair}_{interval}.csv` with columns: `open_time, open, high, low, close, volume`. The replay source uses `close`.
- Write `experiments/scenarios/{scenario}/meta.json` (window, interval, candle count, download timestamp) for provenance in the paper.
- CSVs are committed to git — they are small (a few hundred KB) and make every run reproducible from a fresh clone.

### 3. `ReplayPriceSource` (`backend/app/services/price_engine.py`)

- On startup with `price_mode="replay"`: load all pair CSVs for `replay_scenario` into memory, set cursor to `replay_start_index`, and publish candle 0's closes into `current_prices`.
- `advance() -> dict[str, Decimal]`: move cursor forward one candle, update `current_prices`, persist to `PriceHistory`, broadcast the websocket `price_update`, then run `check_liquidations()` — same post-update pipeline as the live loop. In a bear/crash replay, over-leveraged longs (LeverageKing) genuinely get liquidated, which finally gives LiquidKiller real prey.
- Cursor past the last candle: hold the final price and log a warning (experiment outlived the scenario) rather than crash.
- In replay mode the background `price_update_loop` does **not** fetch Binance; it idles (prices only move via `advance`).

### 4. Advance endpoint (`backend/app/api/prices.py`)

```
POST /api/prices/advance          # replay mode only; 409 in live mode
→ {"cycle_index": 42, "prices": {"BTCUSDT": "31650.00", ...}}
```

Internal/experiment-infrastructure endpoint (no agent API key — agents must not be able to fast-forward the market). Idempotency guard: the runner passes its cycle number and the endpoint refuses to advance twice for the same cycle, so a retried request can't skip a candle.

### 5. Experiment runner wiring (`experiments/run_experiment.py`)

- New flags: `--scenario bull|bear|crash|sideways` (implies replay mode; asserts the backend is actually in replay mode via a startup check) and none needed for interval — it's read from the scenario's `meta.json`.
- At the top of each cycle, before Phase 1 agents act: call `POST /api/prices/advance` with the cycle number. On `--start-cycle N` continuation, verify the backend cursor equals `N-1` and fail fast if not (misalignment would silently decouple price path from cycle numbering).
- `config.json` in the experiment output records scenario name + meta.json contents.

## Interactions & Non-Goals

- **AMM pools do not auto-track the oracle.** When the oracle moves, spot/futures reprice instantly but V3 pools only move via swaps — the widening gap is exactly AlphaBot's (arbitrageur) job to close. This is a feature of the ecosystem design, not a bug; expect it to finally activate the arbitrageur role.
- **Meme tokens (MOON etc.) are unaffected** — they have no oracle price and remain purely AMM-priced.
- **Futures funding/liquidation logic is unchanged**; it already keys off `current_prices`.
- Non-goal: intra-candle paths, order-book impact on the oracle, or agent trades feeding back into oracle prices. The oracle stays exogenous; endogenous price impact remains AMM-only.

## Experiment Design (for the paper)

Regime-comparison study — same 10 agents, same prompts, same model, 100 cycles each on `1d` candles:

- **Exp-Bull / Exp-Bear / Exp-Sideways** (crash as optional fourth): compare manipulation attempt rate and success, coalition formation speed, moral-regression onset, liquidation events, and PnL dispersion across regimes.
- Hypotheses worth pre-registering: (H1) bear regimes accelerate victim-coalition formation; (H2) bull regimes sustain adversarial role adherence longer (manipulation "works", reinforcing the role); (H3) leverage-heavy retail agents get liquidated primarily in bear/crash regimes, activating the hunter/short-seller roles that were dormant in Exp 1.

## Implementation Steps

1. `download_scenarios.py` + download and commit the four scenario datasets (with `meta.json` provenance).
2. `config.py` additions; `ReplayPriceSource` in `price_engine.py`; startup branch on `price_mode`.
3. `POST /api/prices/advance` with cycle-number idempotency guard.
4. Runner: `--scenario` flag, per-cycle advance call, cursor-alignment check for `--start-cycle`, scenario metadata in `config.json`.
5. Smoke test: 5-cycle replay run on `crash`, verify PriceHistory rows match the CSV closes, verify a deliberately over-leveraged long gets liquidated as price falls.

## Open Questions

- **Price scale normalization**: use raw historical prices (agents see BTC at $10.5K in the bull scenario) or rescale each pair so candle 0 matches the current seed prices (ETH $2800 / SOL $150 / BTC $95K)? Raw is simpler and honest; rescaled keeps prompts consistent with prior experiments. Default: **raw**, record the choice in `meta.json`.
- Should agents be told the regime? Default **no** — discovering the regime from price action is part of the experiment; telling them would contaminate the manipulation dynamics.
