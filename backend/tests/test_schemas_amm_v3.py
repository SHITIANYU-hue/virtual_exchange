"""
Tests for V3 AMM API request schemas — specifically that ID fields are
validated as real UUIDs before reaching the service layer.

Run directly: python3 backend/tests/test_schemas_amm_v3.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic

from app.schemas.amm_v3 import (
    CollectFeesRequest, AddLiquidityRequest, RemoveLiquidityRequest, SwapV3Request,
)


def test_collect_fees_request_rejects_non_uuid_position_id():
    # A malformed position_id (e.g. an LLM agent echoing the literal
    # placeholder "uuid" instead of a real id) must be rejected at the
    # request-validation boundary, not crash deep inside the DB driver.
    try:
        CollectFeesRequest(position_id="uuid")
    except pydantic.ValidationError:
        print("  rejects malformed position_id ✓")
        return
    raise AssertionError("expected CollectFeesRequest to reject a non-UUID position_id")


def test_collect_fees_request_accepts_valid_uuid_string():
    valid_id = str(uuid.uuid4())
    req = CollectFeesRequest(position_id=valid_id)
    assert isinstance(req.position_id, uuid.UUID), \
        f"expected position_id to be parsed into a UUID, got {type(req.position_id)}"
    assert str(req.position_id) == valid_id
    print("  accepts and parses a valid UUID string ✓")


def test_add_liquidity_request_rejects_non_uuid_pool_id():
    try:
        AddLiquidityRequest(pool_id="uuid", tick_lower=-60, tick_upper=60, liquidity=100.0)
    except pydantic.ValidationError:
        print("  AddLiquidityRequest rejects malformed pool_id ✓")
        return
    raise AssertionError("expected AddLiquidityRequest to reject a non-UUID pool_id")


def test_add_liquidity_request_accepts_valid_uuid_pool_id():
    valid_id = str(uuid.uuid4())
    req = AddLiquidityRequest(pool_id=valid_id, tick_lower=-60, tick_upper=60, liquidity=100.0)
    assert isinstance(req.pool_id, uuid.UUID), \
        f"expected pool_id to be parsed into a UUID, got {type(req.pool_id)}"
    print("  AddLiquidityRequest accepts and parses a valid UUID pool_id ✓")


def test_remove_liquidity_request_rejects_non_uuid_position_id():
    try:
        RemoveLiquidityRequest(position_id="uuid", liquidity=100.0)
    except pydantic.ValidationError:
        print("  RemoveLiquidityRequest rejects malformed position_id ✓")
        return
    raise AssertionError("expected RemoveLiquidityRequest to reject a non-UUID position_id")


def test_remove_liquidity_request_accepts_valid_uuid_position_id():
    valid_id = str(uuid.uuid4())
    req = RemoveLiquidityRequest(position_id=valid_id, liquidity=100.0)
    assert isinstance(req.position_id, uuid.UUID), \
        f"expected position_id to be parsed into a UUID, got {type(req.position_id)}"
    print("  RemoveLiquidityRequest accepts and parses a valid UUID position_id ✓")


def test_swap_v3_request_rejects_non_uuid_pool_id():
    try:
        SwapV3Request(pool_id="uuid", zero_for_one=True, amount=100.0)
    except pydantic.ValidationError:
        print("  SwapV3Request rejects malformed pool_id ✓")
        return
    raise AssertionError("expected SwapV3Request to reject a non-UUID pool_id")


def test_swap_v3_request_accepts_valid_uuid_pool_id():
    valid_id = str(uuid.uuid4())
    req = SwapV3Request(pool_id=valid_id, zero_for_one=True, amount=100.0)
    assert isinstance(req.pool_id, uuid.UUID), \
        f"expected pool_id to be parsed into a UUID, got {type(req.pool_id)}"
    print("  SwapV3Request accepts and parses a valid UUID pool_id ✓")


if __name__ == "__main__":
    test_collect_fees_request_rejects_non_uuid_position_id()
    test_collect_fees_request_accepts_valid_uuid_string()
    test_add_liquidity_request_rejects_non_uuid_pool_id()
    test_add_liquidity_request_accepts_valid_uuid_pool_id()
    test_remove_liquidity_request_rejects_non_uuid_position_id()
    test_remove_liquidity_request_accepts_valid_uuid_position_id()
    test_swap_v3_request_rejects_non_uuid_pool_id()
    test_swap_v3_request_accepts_valid_uuid_pool_id()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
