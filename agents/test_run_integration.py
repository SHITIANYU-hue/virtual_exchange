"""
Integration test for agents/run.py's portfolio valuation, exercising the real
HTTP + backend + database stack (unlike test_run.py, which uses synthetic
in-memory state dicts).

Spins up a throwaway backend instance against a scratch database, registers a
real test agent, mints a real LP position with known parameters, and confirms
_calculate_portfolio_value (fetched via a real get_agent_state() HTTP call)
no longer treats deployed liquidity as vanished capital.

Run directly: python3 agents/test_run_integration.py
Requires: postgres reachable at localhost:5432 as postgres/postgres.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = str(Path(__file__).parent.parent / "backend")
TEST_DB = "agent_metaverse_test_integration"
TEST_DB_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{TEST_DB}"
TEST_PORT = 8391
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


def test_portfolio_value_does_not_vanish_when_adding_lp_liquidity():
    print("=== Integration test: LP position value survives in portfolio total ===")
    proc = None
    try:
        _reset_schema()
        proc = _start_server()

        os.environ["AGENT_METAVERSE_BASE_URL"] = TEST_BASE_URL
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import agents.run as agent_run
        agent_run.BASE_URL = TEST_BASE_URL  # module-level constant read at import time

        reg = httpx.post(
            f"{TEST_BASE_URL}/api/sdk/agents/register",
            json={"name": "IntegrationTestLP", "initial_balance": 200000},
        ).json()
        api_key = reg["api_key"]

        create = httpx.post(
            f"{TEST_BASE_URL}/api/token/create",
            headers={"X-API-Key": api_key},
            json={
                "symbol": "TESTCOIN", "name": "Test Coin", "total_supply": 1000000,
                "initial_price": 1.0, "initial_liquidity_usdt": 1000,
            },
        ).json()
        pool_id = create["pool"]["pool_id"]
        current_tick = create["pool"]["tick"]
        assert current_tick >= -600, f"test assumption broken: pool tick {current_tick} not >= -600"

        before_state = agent_run.get_agent_state(api_key)
        before_total = agent_run._calculate_portfolio_value(before_state)

        mint = httpx.post(
            f"{TEST_BASE_URL}/api/v3/add-liquidity",
            headers={"X-API-Key": api_key},
            json={"pool_id": pool_id, "tick_lower": -1200, "tick_upper": -600, "liquidity": 100000},
        ).json()
        deposited_usdt = float(mint["amount1"])
        assert deposited_usdt > 0, f"expected a real USDT deposit, got {mint}"

        after_state = agent_run.get_agent_state(api_key)
        after_total = agent_run._calculate_portfolio_value(after_state)

        # The position's value right after minting should equal what was just
        # deposited (nothing has moved the price in between) -- so adding
        # liquidity should barely move the total at all.
        assert abs(after_total - before_total) < 1.0, (
            f"expected total to stay ~flat across minting (before={before_total}, after={after_total}), "
            f"deposited {deposited_usdt} USDT that should now show up as position value instead of balance"
        )
        print(f"  before={before_total:.4f}, after={after_total:.4f}: deployed liquidity did not vanish ✓")

        # Prove the old bug WOULD have fired: zeroing v3_positions (simulating
        # the pre-fix code, which never read this key at all) must show the
        # deposited USDT as a real loss.
        old_behavior_state = dict(after_state)
        old_behavior_state["v3_positions"] = []
        old_behavior_total = agent_run._calculate_portfolio_value(old_behavior_state)
        assert before_total - old_behavior_total > deposited_usdt - 1.0, (
            f"expected the old (pre-fix) calculation to show ~-{deposited_usdt} vs before, "
            f"got before={before_total}, old_behavior={old_behavior_total}"
        )
        print(f"  old behavior would have shown a ${before_total - old_behavior_total:.2f} phantom loss ✓")
    finally:
        if proc:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)

    print("  PASSED\n")


if __name__ == "__main__":
    test_portfolio_value_does_not_vanish_when_adding_lp_liquidity()
    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED")
    print("=" * 60)
