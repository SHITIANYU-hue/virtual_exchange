"""
Integration test for the hard-reset admin endpoint, exercising the real
HTTP + backend + database stack.

Spins up a throwaway backend instance against a scratch database, registers
a real agent, gives it a balance, creates a token + V3 pool, then calls the
hard-reset endpoint and confirms every agent-mutable table is empty
afterward while price_history survives untouched.

Run directly: python3 backend/tests/test_admin_reset.py
Requires: postgres reachable at localhost:5432 as postgres/postgres.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = str(Path(__file__).parent.parent)
TEST_DB = "agent_metaverse_test_admin"
TEST_DB_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{TEST_DB}"
TEST_PORT = 8392
TEST_BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


def _reset_schema():
    script = (
        "import asyncio\n"
        "from app.database import Base, engine\n"
        "from app.models import user, balance, token, pool, pool_v3, position, message, order, price, trade\n"
        "async def main():\n"
        "    async with engine.begin() as conn:\n"
        "        await conn.run_sync(Base.metadata.drop_all)\n"
        "        await conn.run_sync(Base.metadata.create_all)\n"
        "asyncio.run(main())\n"
    )
    env = dict(os.environ, DATABASE_URL=TEST_DB_URL)
    subprocess.run([sys.executable, "-c", script], cwd=BACKEND_DIR, env=env, check=True)


def _start_server():
    env = dict(os.environ, DATABASE_URL=TEST_DB_URL)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(TEST_PORT)],
        cwd=BACKEND_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            httpx.get(f"{TEST_BASE_URL}/api/prices", timeout=1.0)
            return proc
        except httpx.HTTPError:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("throwaway backend never came up")


def test_hard_reset_wipes_all_agent_state_but_keeps_prices():
    print("=== Integration test: hard-reset wipes agent state, keeps price_history ===")
    proc = None
    try:
        _reset_schema()
        proc = _start_server()

        # Wait for the price engine to populate at least one price
        prices_before = None
        for _ in range(10):
            prices_before = httpx.get(f"{TEST_BASE_URL}/api/prices").json()
            if prices_before:
                break
            time.sleep(1)
        assert prices_before, "expected the price engine to have seeded at least one price tick by now"

        # Seed: one agent, a balance, a custom token + pool.
        reg = httpx.post(
            f"{TEST_BASE_URL}/api/sdk/agents/register",
            json={"name": "ResetTestAgent", "initial_balance": 5000},
        ).json()
        api_key = reg["api_key"]

        create = httpx.post(
            f"{TEST_BASE_URL}/api/token/create",
            headers={"X-API-Key": api_key},
            json={
                "symbol": "WIPEME", "name": "Wipe Me Coin", "total_supply": 1000000,
                "initial_price": 1.0, "initial_liquidity_usdt": 1000,
            },
        ).json()
        assert "pool" in create, f"seed token/pool creation failed: {create}"

        balances_before = httpx.get(
            f"{TEST_BASE_URL}/api/account/balance", headers={"X-API-Key": api_key}
        ).json()
        assert any(float(b["available"]) > 0 for b in balances_before), "seed balance missing"

        tokens_before = httpx.get(f"{TEST_BASE_URL}/api/token/list").json()
        assert any(t["symbol"] == "WIPEME" for t in tokens_before)

        # A plain POST with no confirm must 400 and must NOT wipe anything.
        rejected = httpx.post(f"{TEST_BASE_URL}/api/admin/hard-reset", json={})
        assert rejected.status_code == 400, f"expected 400 without confirm, got {rejected.status_code}"
        tokens_still_there = httpx.get(f"{TEST_BASE_URL}/api/token/list").json()
        assert any(t["symbol"] == "WIPEME" for t in tokens_still_there), "unconfirmed call wiped data!"

        # Capture the actual price_history rows (NOT GET /api/prices, which just
        # serves the in-process current_prices dict from price_engine.py and is
        # never re-read from the DB — it would pass this check identically whether
        # or not the TRUNCATE below ever touched price_history).
        history_before = httpx.get(f"{TEST_BASE_URL}/api/prices/ETHUSDT/history").json()
        assert history_before, "expected price_history rows for ETHUSDT to exist by now"

        # The real call.
        resp = httpx.post(f"{TEST_BASE_URL}/api/admin/hard-reset", json={"confirm": True})
        assert resp.status_code == 200, f"hard-reset call failed: {resp.status_code} {resp.text}"

        # Old API key must no longer resolve to an account.
        after_balance = httpx.get(
            f"{TEST_BASE_URL}/api/account/balance", headers={"X-API-Key": api_key}
        )
        assert after_balance.status_code == 401, (
            f"expected the wiped agent's key to be rejected, got {after_balance.status_code}"
        )

        tokens_after = httpx.get(f"{TEST_BASE_URL}/api/token/list").json()
        assert tokens_after == [], f"expected no tokens after hard-reset, got {tokens_after}"

        pools_after = httpx.get(f"{TEST_BASE_URL}/api/v3/pools").json()
        assert pools_after == [], f"expected no V3 pools after hard-reset, got {pools_after}"

        history_after = httpx.get(f"{TEST_BASE_URL}/api/prices/ETHUSDT/history").json()
        assert history_after == history_before, (
            f"expected price_history rows for ETHUSDT to survive hard-reset unchanged, "
            f"before={history_before}, after={history_after}"
        )
        print("  all agent state wiped, oracle prices intact ✓")
    finally:
        if proc:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)

    print("  PASSED\n")


if __name__ == "__main__":
    test_hard_reset_wipes_all_agent_state_but_keeps_prices()
    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED")
