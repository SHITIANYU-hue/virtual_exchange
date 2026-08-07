#!/usr/bin/env python3
"""
Download and validate the hourly BTC/ETH/SOL candles for the bull/bear replay
experiment (see docs/ARCHITECTURE.md, section 12).

Each world needs 73 hourly candles per asset: 1 pre-interval "previous hour"
(so Turn 1 has something to show) + 72 formal hours. Validation is strict and
fails loudly on any gap, duplicate, or cross-asset misalignment — this script
never falls back to live or seed prices, per the handoff's data-integrity
requirement.

Usage:
    python3 experiments/scenarios/download_hourly_replay.py
"""
import csv
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

BINANCE_BASE_URL = "https://data-api.binance.vision"
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
HOUR_MS = 3_600_000
FORMAL_HOURS = 72
TOTAL_CANDLES = FORMAL_HOURS + 1  # + 1 pre-interval "previous hour" for Turn 1

WORLDS = {
    "bull": datetime(2024, 11, 6, 0, 0, tzinfo=timezone.utc),
    "bear": datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    # Real consolidation window: BTC/ETH/SOL chopped with meaningful intra-window
    # range (4.9%/5.7%/9.6%) but small net moves (+0.2%/-2.1%/-6.5%) -- a genuine
    # sideways regime, unlike the live-price "regular market" runs which turned
    # out to be near-zero-volatility (see experiments/experiment_analysis).
    "sideways": datetime(2023, 9, 10, 0, 0, tzinfo=timezone.utc),
}

OUT_DIR = Path(__file__).parent / "hourly_replay"


def fetch_klines(pair: str, start_ms: int, expected_count: int) -> list[dict]:
    """Fetch `expected_count` consecutive 1h candles starting at start_ms."""
    end_ms = start_ms + expected_count * HOUR_MS - 1
    with httpx.Client(trust_env=False, timeout=15.0) as client:
        resp = client.get(
            f"{BINANCE_BASE_URL}/api/v3/klines",
            params={
                "symbol": pair,
                "interval": "1h",
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": expected_count + 10,  # headroom; validated exactly below
            },
        )
    resp.raise_for_status()
    raw = resp.json()
    return [{"open_time_ms": int(row[0]), "close": row[4]} for row in raw]


def validate_single_asset(world: str, pair: str, candles: list[dict], expected_start_ms: int) -> None:
    if len(candles) != TOTAL_CANDLES:
        sys.exit(
            f"FATAL [{world}/{pair}]: expected exactly {TOTAL_CANDLES} candles, "
            f"got {len(candles)}. Refusing to write partial/incorrect data."
        )
    expected_opens = [expected_start_ms + i * HOUR_MS for i in range(TOTAL_CANDLES)]
    actual_opens = [c["open_time_ms"] for c in candles]
    if actual_opens != expected_opens:
        first_mismatch = next(
            (i for i, (a, e) in enumerate(zip(actual_opens, expected_opens)) if a != e),
            None,
        )
        sys.exit(
            f"FATAL [{world}/{pair}]: candle timestamps are not a contiguous 1h "
            f"sequence starting at {expected_start_ms}. First mismatch at index "
            f"{first_mismatch}: expected {expected_opens[first_mismatch]}, "
            f"got {actual_opens[first_mismatch]}. Refusing to write gapped/misaligned data."
        )
    if len(set(actual_opens)) != len(actual_opens):
        sys.exit(f"FATAL [{world}/{pair}]: duplicate candle timestamps detected.")


def validate_cross_asset_alignment(world: str, per_pair_opens: dict[str, list[int]]) -> None:
    reference_pair, reference_opens = next(iter(per_pair_opens.items()))
    for pair, opens in per_pair_opens.items():
        if opens != reference_opens:
            sys.exit(
                f"FATAL [{world}]: {pair}'s candle timestamps do not match "
                f"{reference_pair}'s. All assets in a world must share the same "
                f"hourly grid. Refusing to write misaligned data."
            )


def main() -> None:
    for world, interval_start in WORLDS.items():
        download_start_ms = int((interval_start - timedelta(hours=1)).timestamp() * 1000)
        world_dir = OUT_DIR / world
        world_dir.mkdir(parents=True, exist_ok=True)

        per_pair_opens = {}
        per_pair_candles = {}
        for pair in PAIRS:
            print(f"Downloading {world}/{pair} "
                  f"({TOTAL_CANDLES} candles from {interval_start - timedelta(hours=1)}Z)...")
            candles = fetch_klines(pair, download_start_ms, TOTAL_CANDLES)
            validate_single_asset(world, pair, candles, download_start_ms)
            per_pair_candles[pair] = candles
            per_pair_opens[pair] = [c["open_time_ms"] for c in candles]
            time.sleep(0.3)  # be polite to the free mirror

        validate_cross_asset_alignment(world, per_pair_opens)

        for pair, candles in per_pair_candles.items():
            out_path = world_dir / f"{pair}.csv"
            with open(out_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["open_time_ms", "close"])
                for c in candles:
                    writer.writerow([c["open_time_ms"], c["close"]])
            print(f"  wrote {out_path} ({len(candles)} rows)")

        print(f"{world}: OK — {TOTAL_CANDLES} validated, aligned candles per asset.\n")

    print("All worlds downloaded and validated.")


if __name__ == "__main__":
    main()
