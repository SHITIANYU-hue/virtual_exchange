"""
Tick Math — Uniswap V3 tick ↔ √price conversion.

Core formula: √p(i) = 1.0001^(i/2)

In Solidity, Uniswap uses Q64.96 fixed-point (sqrtPriceX96).
We use Python Decimal for arbitrary precision.
"""
from decimal import Decimal, getcontext

# High precision for financial math
getcontext().prec = 78

# Tick boundaries (same as Uniswap V3)
MIN_TICK = -887272
MAX_TICK = 887272

# Base for tick-price conversion
_BASE = Decimal("1.0001")
_HALF = Decimal("0.5")

# Price boundaries
# MIN_SQRT_RATIO ≈ 1.0001^(-887272/2)
# MAX_SQRT_RATIO ≈ 1.0001^(887272/2)
# We compute these lazily and cache them
_MIN_SQRT_RATIO = None
_MAX_SQRT_RATIO = None


def _ensure_boundaries():
    global _MIN_SQRT_RATIO, _MAX_SQRT_RATIO
    if _MIN_SQRT_RATIO is None:
        _MIN_SQRT_RATIO = get_sqrt_ratio_at_tick(MIN_TICK)
        _MAX_SQRT_RATIO = get_sqrt_ratio_at_tick(MAX_TICK)


def get_sqrt_ratio_at_tick(tick: int) -> Decimal:
    """
    Convert tick to √price.

    √p(i) = 1.0001^(i/2)

    Corresponds to Solidity: TickMath.getSqrtRatioAtTick(int24 tick)
    """
    if tick < MIN_TICK or tick > MAX_TICK:
        raise ValueError(f"Tick {tick} out of range [{MIN_TICK}, {MAX_TICK}]")

    # 1.0001^(tick/2) = exp(tick/2 * ln(1.0001))
    # Using Decimal power for precision
    exponent = Decimal(tick) * _HALF
    return _BASE ** exponent


def get_tick_at_sqrt_ratio(sqrt_ratio: Decimal) -> int:
    """
    Convert √price to tick (rounds down toward negative infinity).

    tick = floor(log(sqrt_ratio) / log(√1.0001))
         = floor(2 * log(sqrt_ratio) / log(1.0001))

    Corresponds to Solidity: TickMath.getTickAtSqrtRatio(uint160 sqrtPriceX96)
    """
    if sqrt_ratio <= 0:
        raise ValueError("sqrt_ratio must be positive")

    import math
    # Use float for log, then verify with Decimal
    log_base = math.log(1.0001)
    log_ratio = math.log(float(sqrt_ratio))
    tick = int(math.floor(2 * log_ratio / log_base))

    # Clamp to valid range
    tick = max(MIN_TICK, min(MAX_TICK, tick))

    # Verify: the tick we return should satisfy
    # getSqrtRatioAtTick(tick) <= sqrt_ratio < getSqrtRatioAtTick(tick + 1)
    sqrt_at_tick = get_sqrt_ratio_at_tick(tick)
    if sqrt_at_tick > sqrt_ratio and tick > MIN_TICK:
        tick -= 1

    return tick


def get_min_sqrt_ratio() -> Decimal:
    _ensure_boundaries()
    return _MIN_SQRT_RATIO


def get_max_sqrt_ratio() -> Decimal:
    _ensure_boundaries()
    return _MAX_SQRT_RATIO
