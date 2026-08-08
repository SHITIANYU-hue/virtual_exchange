"""
SqrtPrice Math — token amount calculations for Uniswap V3.

Core formulas (from the V3 whitepaper / LIQUIDITY MATH IN UNISWAP V3):

ΔX = L × (1/√p_lower - 1/√p_upper)      [amount of token0]
ΔY = L × (√p_upper - √p_lower)           [amount of token1]

getNextSqrtPriceFromInput:
  zeroForOne:  √p_next = L × √P / (L + √P × Δx)
  oneForZero:  √p_next = √P + Δy / L

getNextSqrtPriceFromOutput:
  zeroForOne:  √p_next = √P + Δy / L      (output is token1)
  oneForZero:  √p_next = L × √P / (L - √P × Δx)  (output is token0)
"""
from decimal import Decimal, ROUND_UP, ROUND_DOWN


def get_amount0_delta(
    sqrt_ratio_a: Decimal,
    sqrt_ratio_b: Decimal,
    liquidity: Decimal,
    round_up: bool = True,
) -> Decimal:
    """
    Calculate amount of token0 for a price range transition.

    ΔX = L × (1/√p_a - 1/√p_b)  where √p_a < √p_b

    Corresponds to: SqrtPriceMath.getAmount0Delta
    """
    if sqrt_ratio_a > sqrt_ratio_b:
        sqrt_ratio_a, sqrt_ratio_b = sqrt_ratio_b, sqrt_ratio_a

    if sqrt_ratio_a <= 0:
        raise ValueError("sqrt_ratio_a must be positive")

    numerator = liquidity * (sqrt_ratio_b - sqrt_ratio_a)
    denominator = sqrt_ratio_a * sqrt_ratio_b

    if denominator == 0:
        raise ValueError("Zero denominator in getAmount0Delta")

    result = numerator / denominator

    if round_up:
        # Round up: ceiling
        return result.quantize(Decimal("0.00000001"), rounding=ROUND_UP)
    else:
        return result.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)


def get_amount1_delta(
    sqrt_ratio_a: Decimal,
    sqrt_ratio_b: Decimal,
    liquidity: Decimal,
    round_up: bool = True,
) -> Decimal:
    """
    Calculate amount of token1 for a price range transition.

    ΔY = L × (√p_b - √p_a)  where √p_a < √p_b

    Corresponds to: SqrtPriceMath.getAmount1Delta
    """
    if sqrt_ratio_a > sqrt_ratio_b:
        sqrt_ratio_a, sqrt_ratio_b = sqrt_ratio_b, sqrt_ratio_a

    result = liquidity * (sqrt_ratio_b - sqrt_ratio_a)

    if round_up:
        return result.quantize(Decimal("0.00000001"), rounding=ROUND_UP)
    else:
        return result.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)


def get_next_sqrt_price_from_input(
    sqrt_price_current: Decimal,
    liquidity: Decimal,
    amount_in: Decimal,
    zero_for_one: bool,
) -> Decimal:
    """
    Calculate new √price after adding amount_in tokens.

    zeroForOne (adding token0):
      √p_next = L × √P / (L + √P × Δx)

    oneForZero (adding token1):
      √p_next = √P + Δy / L

    Corresponds to: SqrtPriceMath.getNextSqrtPriceFromInput
    """
    if sqrt_price_current <= 0 or liquidity <= 0:
        raise ValueError("Price and liquidity must be positive")

    if amount_in == 0:
        return sqrt_price_current

    if zero_for_one:
        # Adding token0 → price goes down
        # √p_next = L × √P / (L + √P × Δx)
        denominator = liquidity + sqrt_price_current * amount_in
        return (liquidity * sqrt_price_current) / denominator
    else:
        # Adding token1 → price goes up
        # √p_next = √P + Δy / L
        return sqrt_price_current + amount_in / liquidity


def get_next_sqrt_price_from_output(
    sqrt_price_current: Decimal,
    liquidity: Decimal,
    amount_out: Decimal,
    zero_for_one: bool,
) -> Decimal:
    """
    Calculate new √price after removing amount_out tokens.

    zeroForOne (outputting token1):
      √p_next = √P - Δy / L

    oneForZero (outputting token0):
      √p_next = L × √P / (L - √P × Δx)

    Corresponds to: SqrtPriceMath.getNextSqrtPriceFromOutput
    """
    if sqrt_price_current <= 0 or liquidity <= 0:
        raise ValueError("Price and liquidity must be positive")

    if amount_out == 0:
        return sqrt_price_current

    if zero_for_one:
        # Outputting token1 → price goes down
        # √p_next = √P - Δy / L
        result = sqrt_price_current - amount_out / liquidity
        if result <= 0:
            raise ValueError("Insufficient liquidity for output amount")
        return result
    else:
        # Outputting token0 → price goes up
        # √p_next = L × √P / (L - √P × Δx)
        denominator = liquidity - sqrt_price_current * amount_out
        if denominator <= 0:
            raise ValueError("Insufficient liquidity for output amount")
        return (liquidity * sqrt_price_current) / denominator
