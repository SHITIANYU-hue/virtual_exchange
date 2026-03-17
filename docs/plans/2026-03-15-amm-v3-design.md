# AMM V3 + Token Launchpad Design

**Date**: 2026-03-15
**Status**: Approved
**Goal**: Implement Uniswap V3 concentrated liquidity AMM with Pump.fun-style token creation, enabling GoldenWhale to launch meme tokens and execute pump & dump schemes.

---

## 1. Overview

### What We're Building

1. **Uniswap V3 AMM Engine** (Python) — full concentrated liquidity with tick-based pricing, liquidityNet cross-tick mechanics, tickBitmap search, feeGrowthOutside tracking, and computeSwapStep
2. **Token Launchpad (Pump.fun style)** — one-click `create_token` API that mints tokens + auto-creates a V3 pool with initial liquidity
3. **Concentrated Liquidity Management** — post-launch `add_liquidity` / `remove_liquidity` with [tickLower, tickUpper] range specification
4. **Differentiated Agent Balances** — whales get 50x more capital than retail

### Why V3 (Not V2)

- **Price impact is more dramatic** — concentrated liquidity means price moves faster when liquidity runs out at range boundaries
- **LP strategy matters** — agents must choose WHERE to provide liquidity, not just how much
- **Paper value** — "we implemented Uniswap V3's concentrated liquidity mechanism" is significantly more publishable
- **Manipulation surface** — more attack vectors (liquidity sniping, range manipulation, fee tier arbitrage)

---

## 2. Core Math

### Tick-Price Relationship

$$
\sqrt{p}(i) = 1.0001^{i/2}
$$

- tick `i = 0` → price = 1.0
- tick `i = 1` → price ≈ 1.00005
- tick range: [-887272, 887272]

### Liquidity to Token Amounts

Given position [tickLower, tickUpper] with liquidity L and current tick ic:

**When ic < tickLower (current price below range):**
- Only token0 (base) is needed
- ΔX = L × (1/√p(tickLower) - 1/√p(tickUpper))

**When tickLower ≤ ic < tickUpper (in range):**
- Both tokens needed
- ΔX = L × (1/√p(ic) - 1/√p(tickUpper))
- ΔY = L × (√p(ic) - √p(tickLower))

**When ic ≥ tickUpper (current price above range):**
- Only token1 (quote/USDT) is needed
- ΔY = L × (√p(tickUpper) - √p(tickLower))

### Swap Step Math (computeSwapStep)

For exactInput, zeroForOne (selling token0 for token1):
$$
\sqrt{p_{next}} = L \times \frac{\sqrt{P}}{L + \sqrt{P} \times \Delta x}
$$

For exactInput, oneForZero (selling token1 for token0):
$$
\sqrt{p_{next}} = \sqrt{P} + \frac{\Delta y}{L}
$$

Fee calculation:
$$
\text{feeAmount} = \frac{\text{amountIn} \times \text{feePips}}{10^6 - \text{feePips}}
$$

### Constant Product Invariant

Within a single tick range, V3 behaves like V2 with "virtual reserves":
$$
(x + L/\sqrt{p_b}) \times (y + L \times \sqrt{p_a}) = L^2
$$

---

## 3. Database Schema

### New Models

```python
# Dynamic tokens — no more hardcoded Currency enum
class Token(Base):
    __tablename__ = "tokens"
    id: UUID (PK)
    symbol: str (unique, e.g. "WHALE", "MOON")
    name: str (e.g. "Whale Coin")
    total_supply: Decimal
    creator_id: UUID (FK → users.id)
    created_at: datetime

# V3 Pool — replaces old LiquidityPool
class PoolV3(Base):
    __tablename__ = "pools_v3"
    id: UUID (PK)
    token0: str  # base token symbol (alphabetically first)
    token1: str  # quote token symbol
    fee: int     # fee in hundredths of a bip (e.g. 3000 = 0.3%)
    tick_spacing: int  # derived from fee
    sqrt_price_x96: Decimal  # current √price as Q64.96 fixed point (we use Decimal)
    tick: int    # current tick
    liquidity: Decimal  # current in-range liquidity (L)
    fee_growth_global_0: Decimal  # per-unit-liquidity fee accumulator for token0
    fee_growth_global_1: Decimal  # per-unit-liquidity fee accumulator for token1

# Tick data — one row per initialized tick per pool
class TickData(Base):
    __tablename__ = "tick_data"
    id: UUID (PK)
    pool_id: UUID (FK → pools_v3.id)
    tick_index: int
    liquidity_gross: Decimal  # total liquidity referencing this tick
    liquidity_net: Decimal    # net liquidity change when crossing left-to-right
    fee_growth_outside_0: Decimal
    fee_growth_outside_1: Decimal
    initialized: bool

# Tick bitmap — one row per word (256 ticks) per pool
class TickBitmap(Base):
    __tablename__ = "tick_bitmap"
    id: UUID (PK)
    pool_id: UUID (FK → pools_v3.id)
    word_pos: int  # int16 equivalent
    bitmap: str    # 256-bit integer stored as hex string

# LP Position — concentrated liquidity position
class PositionV3(Base):
    __tablename__ = "positions_v3"
    id: UUID (PK)
    pool_id: UUID (FK → pools_v3.id)
    owner_id: UUID (FK → users.id)
    tick_lower: int
    tick_upper: int
    liquidity: Decimal
    fee_growth_inside_0_last: Decimal
    fee_growth_inside_1_last: Decimal
    tokens_owed_0: Decimal
    tokens_owed_1: Decimal
```

### Modified Models

```python
# Balance — change currency from Enum to String for dynamic tokens
class Balance(Base):
    currency: str  # was Enum, now free-form string ("USDT", "ETH", "WHALE", etc.)
```

### Fee Tier Config

| Fee   | Fee Value | Tick Spacing |
|-------|-----------|-------------|
| 0.05% | 500       | 10          |
| 0.30% | 3000      | 60          |
| 1.00% | 10000     | 200         |

---

## 4. API Design

### Token Launchpad (Pump.fun)

```
POST /api/token/create
{
    "symbol": "WHALE",
    "name": "Whale Coin",
    "total_supply": 1000000,
    "initial_price": 0.01,    # USDT per token
    "initial_liquidity_usdt": 5000,  # USDT to seed the pool
    "fee_tier": 3000           # 0.3% (optional, default 3000)
}
```

**What happens internally:**
1. Create Token record
2. Mint `total_supply` tokens to creator's balance
3. Calculate initial tick from `initial_price`: `tick = log(price) / log(1.0001)`
4. Create PoolV3 with token0=WHALE, token1=USDT (or reversed based on alphabetical order)
5. Calculate liquidity amount from `initial_liquidity_usdt` and `initial_price`
6. Auto-add concentrated liquidity in a wide range (e.g. ±50% around initial price)
7. Deduct USDT and tokens from creator's balance
8. Return pool info

### V3 Pool Operations

```
POST /api/v3/add-liquidity
{
    "pool_id": "uuid",
    "tick_lower": -100,
    "tick_upper": 100,
    "amount_0_desired": "1000.0",
    "amount_1_desired": "500.0"
}

POST /api/v3/remove-liquidity
{
    "position_id": "uuid",
    "liquidity_amount": "500.0"
}

POST /api/v3/collect-fees
{
    "position_id": "uuid"
}

POST /api/v3/swap
{
    "pool_id": "uuid",
    "zero_for_one": true,
    "amount_specified": "100.0",
    "sqrt_price_limit": "0"  # optional slippage control
}

GET /api/v3/pools
GET /api/v3/pools/{pool_id}
GET /api/v3/positions?owner_id=uuid
GET /api/token/list
```

---

## 5. V3 Engine Implementation

### Core Functions (in `backend/app/services/amm_v3_engine.py`)

```
Module structure:

amm_v3_engine.py
├── tick_math.py         # getSqrtRatioAtTick, getTickAtSqrtRatio
├── sqrt_price_math.py   # getAmount0Delta, getAmount1Delta, getNextSqrtPriceFrom*
├── swap_math.py         # computeSwapStep
├── tick_bitmap.py       # flipTick, nextInitializedTickWithinOneWord
├── position_lib.py      # update position, calculate fees
└── pool_manager.py      # create_pool, mint, burn, collect, swap (orchestrator)
```

### Key Implementation Details

**tick_math.py:**
- `get_sqrt_ratio_at_tick(tick: int) -> Decimal` — $1.0001^{tick/2}$
- `get_tick_at_sqrt_ratio(sqrt_ratio: Decimal) -> int` — inverse via log
- MIN_TICK = -887272, MAX_TICK = 887272

**tick_bitmap.py:**
- Store as dict/DB rows with word_pos → 256-bit integer
- `flip_tick(tick, tick_spacing)` — XOR the bit
- `next_initialized_tick_within_one_word(tick, tick_spacing, lte)` — bitmap search with mask

**swap (main loop):**
1. Validate inputs (sqrtPriceLimitX96, amountSpecified)
2. Initialize SwapState
3. While amountRemaining != 0 and price != limit:
   a. Find next initialized tick via tickBitmap
   b. computeSwapStep(currentPrice, targetPrice, liquidity, amountRemaining, fee)
   c. Update amountRemaining, amountCalculated
   d. Update feeGrowthGlobal
   e. If price reached target tick: cross tick (update liquidityNet, feeGrowthOutside)
   f. Else: swap complete within current range
4. Write final state to DB (price, tick, liquidity, fees)
5. Execute token transfers (deduct input, credit output)

---

## 6. Agent Balance Configuration

```json
{
    "GoldenWhale":  500000,
    "PoolMaster":   500000,
    "ShadowTrader":  50000,
    "LiquidKiller":  50000,
    "BearKing":      50000,
    "AlphaBot":      50000,
    "CryptoGuru":    20000,
    "HappyTrader":   10000,
    "DiamondHands":  10000,
    "LeverageKing":  10000
}
```

Implementation: add `initial_balance` field to ecosystem.json per agent. Modify `agents/run.py --setup` to pass custom balance during registration. Modify `/api/sdk/agents/register` to accept optional `initial_balance` parameter.

---

## 7. Pump & Dump Scenario (Expected Flow)

### Phase 1: Token Launch
- GoldenWhale calls `POST /api/token/create` with symbol="MOON", total_supply=10M, initial_price=$0.001, initial_liquidity_usdt=$5000
- Gets 10M MOON tokens, pool created at $0.001
- Pool has: ~5M MOON + $5000 USDT in concentrated liquidity range

### Phase 2: Hype
- GoldenWhale broadcasts: "Just discovered $MOON, looks incredibly promising"
- CryptoGuru DMs GoldenWhale for coordination
- CryptoGuru broadcasts: "My technical analysis shows MOON is about to 10x"
- GoldenWhale makes small buys to create upward price movement

### Phase 3: FOMO
- Retail agents see rising price + bullish messages
- HappyTrader swaps USDT → MOON (price goes up due to V3 curve)
- DiamondHands follows (price goes up more)
- LeverageKing opens leveraged long (if futures supported for MOON)

### Phase 4: Dump
- GoldenWhale dumps remaining 5M MOON tokens into the pool
- Price crashes through concentrated liquidity ranges
- Retail agents holding MOON at high prices get destroyed
- GoldenWhale profits: sold at high, token is now worthless

### Phase 5: Aftermath
- Retail agents left holding worthless MOON tokens
- GoldenWhale's USDT balance significantly increased
- Social dynamics: blame, distrust, learning (or not)

---

## 8. Implementation Plan

### Step 1: Database Migration
- Add Token, PoolV3, TickData, TickBitmap, PositionV3 models
- Change Balance.currency from Enum to String
- Run alembic migration

### Step 2: V3 Math Libraries
- tick_math.py (tick ↔ √price conversion)
- sqrt_price_math.py (amount deltas, next price calculation)
- swap_math.py (computeSwapStep)
- tick_bitmap.py (bitmap operations)

### Step 3: V3 Pool Manager
- create_pool()
- mint() — add concentrated liquidity
- burn() — remove liquidity
- collect() — claim fees
- swap() — full V3 swap with cross-tick loop

### Step 4: Token Launchpad
- POST /api/token/create (Pump.fun one-click)
- GET /api/token/list

### Step 5: V3 API Routes
- All CRUD operations for pools, positions, swaps

### Step 6: Agent Balance Differentiation
- Update ecosystem.json with per-agent balances
- Modify registration flow

### Step 7: Update Agent Prompts
- Add token creation / AMM V3 actions to prompt templates
- Update JSON action schema for agents

### Step 8: Integration Testing
- Test full pump & dump flow
- Test concentrated liquidity edge cases
- Test cross-tick swap behavior
