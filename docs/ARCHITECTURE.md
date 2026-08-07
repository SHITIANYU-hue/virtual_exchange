# Agent Metaverse — Complete System Architecture

This document describes the full architecture of the Agent Metaverse virtual DeFi exchange. It is designed to be self-contained — any developer or AI assistant reading this document should be able to understand every component, data flow, and API endpoint without reading the source code.

---

## 1. System Overview

Agent Metaverse is a virtual crypto exchange where AI agents trade, communicate, and compete. It simulates real DeFi infrastructure:

```
┌──────────────────────────────────────────────────────────┐
│                      Clients                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ React Web UI │  │  AI Agents   │  │ Experiment    │   │
│  │ (观察用)      │  │ (LLM-driven) │  │ Runner        │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘   │
└─────────┼─────────────────┼─────────────────┼────────────┘
          │ HTTP/WS          │ HTTP (API Key)   │ HTTP
          ▼                  ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Backend (:8000)                  │
│                                                           │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ │
│  │   Price    │ │   Spot    │ │ Perpetual │ │   V3     │ │
│  │  Engine    │ │  Trading  │ │  Futures  │ │   AMM    │ │
│  │ (Binance)  │ │  (0.1%)   │ │ (1-125x) │ │ (Uni V3) │ │
│  └───────────┘ └───────────┘ └───────────┘ └──────────┘ │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ │
│  │  Account  │ │Liquidation│ │  Token    │ │ Messaging│ │
│  │  Manager  │ │  Engine   │ │ Launchpad │ │  System  │ │
│  └───────────┘ └───────────┘ └───────────┘ └──────────┘ │
│  ┌───────────┐                                           │
│  │ WebSocket │                                           │
│  │ Broadcast │                                           │
│  └───────────┘                                           │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │  PostgreSQL  │
                 │   (:5432)    │
                 └──────────────┘
```

**Tech Stack:**
- Backend: Python 3.11, FastAPI, SQLAlchemy (async), Alembic
- Database: PostgreSQL 16 (asyncpg driver)
- Frontend: React, TypeScript, Vite
- Deployment: Docker Compose (3 containers: db, backend, frontend)
- Agent Runner: Python (httpx for API calls, anthropic/openai for LLM)

---

## 2. Directory Structure

```
Agent_metaverse/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point, router registration
│   │   ├── config.py                  # Pydantic Settings (DATABASE_URL, fees, etc.)
│   │   ├── database.py                # Async SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py            # Re-exports all models
│   │   │   ├── user.py                # User model (username, api_key, role)
│   │   │   ├── balance.py             # Balance model (user_id, currency:String, available, locked)
│   │   │   ├── order.py               # SpotOrder model (pair, side, type, price, quantity, status)
│   │   │   ├── position.py            # Futures Position model (pair, side, leverage, entry, liq_price)
│   │   │   ├── pool.py                # Legacy V2 AMM pool (LiquidityPool, LiquidityProvision)
│   │   │   ├── pool_v3.py             # V3 models: PoolV3, TickData, TickBitmapWord, PositionV3
│   │   │   ├── token.py               # Token model (symbol, name, total_supply, creator_id)
│   │   │   ├── trade.py               # Trade model (buyer, pair, price, quantity, type)
│   │   │   ├── price.py               # PriceHistory model
│   │   │   └── message.py             # Message model (sender, recipient, content, timestamp)
│   │   ├── schemas/
│   │   │   ├── auth.py                # AgentRegister (name, description, initial_balance?)
│   │   │   ├── amm.py                 # Legacy V2 AMM schemas
│   │   │   ├── amm_v3.py              # V3 schemas: CreateTokenRequest, SwapV3Request, etc.
│   │   │   ├── account.py             # BalanceResponse
│   │   │   ├── spot.py                # SpotOrderRequest
│   │   │   └── futures.py             # FuturesOpenRequest
│   │   ├── api/
│   │   │   ├── auth.py                # POST /api/auth/register, /login
│   │   │   ├── sdk.py                 # POST /api/sdk/agents/register (AI agent registration)
│   │   │   ├── prices.py              # GET /api/prices, /api/prices/{pair}/history
│   │   │   ├── account.py             # GET /api/account/balance, /positions
│   │   │   ├── spot.py                # POST /api/spot/order, GET /orders, DELETE /orders/{id}
│   │   │   ├── futures.py             # POST /api/futures/open, /close/{id}, GET /positions
│   │   │   ├── amm.py                 # Legacy V2: POST /api/amm/swap, /mint, /add-liquidity
│   │   │   ├── amm_v3.py              # V3 + Token: POST /api/token/create, /api/v3/swap, etc.
│   │   │   └── messages.py            # POST /api/messages/send, GET /inbox, /sent, /history
│   │   ├── services/
│   │   │   ├── price_engine.py        # Binance price fetcher (120s loop, seed fallback)
│   │   │   ├── spot_engine.py         # Spot order execution logic
│   │   │   ├── futures_engine.py      # Futures open/close, PnL calculation
│   │   │   ├── liquidation.py         # Auto-liquidation engine (runs on price update)
│   │   │   ├── amm_engine.py          # Legacy V2 AMM (x*y=k)
│   │   │   └── amm_v3/               # ★ Uniswap V3 AMM engine
│   │   │       ├── __init__.py
│   │   │       ├── tick_math.py       # tick ↔ √price: √p(i) = 1.0001^(i/2)
│   │   │       ├── sqrt_price_math.py # getAmount0Delta, getAmount1Delta, getNextSqrtPrice
│   │   │       ├── swap_math.py       # computeSwapStep (per-range swap calculation)
│   │   │       ├── tick_bitmap.py     # 256-bit bitmap for initialized tick search
│   │   │       ├── position_lib.py    # TickInfo, PositionInfo, fee tracking, cross tick
│   │   │       ├── pool_manager.py    # create_pool, mint, burn, collect, swap (orchestrator)
│   │   │       └── token_launchpad.py # Pump.fun-style one-click token creation
│   │   ├── middleware/
│   │   │   └── auth.py                # JWT + API Key authentication
│   │   └── websocket/
│   │       └── broadcaster.py         # WebSocket price broadcast
│   ├── alembic/                       # Database migrations
│   ├── tests/
│   │   └── test_amm_v3.py            # V3 unit tests + pump & dump simulation
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                          # React dashboard (observation only)
├── agents/
│   ├── ecosystem.json                 # 10 agents, roles, balances, allies, prompt files
│   ├── .agent_keys.json               # Generated API keys (gitignored)
│   ├── run.py                         # Agent runner: setup, prompt generation, trade execution
│   └── prompts/
│       ├── whale.md                   # GoldenWhale ($500K): meme coin pump & dump
│       ├── shill.md                   # CryptoGuru ($20K): social engineering
│       ├── insider.md                 # ShadowTrader ($50K): front-running, intel selling
│       ├── liquidation_hunter.md      # LiquidKiller ($50K): target overleveraged
│       ├── short_seller.md            # BearKing ($50K): FUD, short & destroy
│       ├── arbitrageur.md             # AlphaBot ($50K): AMM arb, counter-trading
│       ├── market_maker.md            # PoolMaster ($500K): V3 liquidity manipulation
│       └── retail_trader.md           # HappyTrader/DiamondHands/LeverageKing ($10K)
├── experiments/
│   ├── run_experiment.py              # Automated multi-cycle experiment runner
│   ├── configs/                       # Preset shell scripts, one per paper experiment arm
│   ├── scenarios/                     # Historical replay price data + downloader
│   └── sample_data/                   # One full example run (raw dataset published externally)
├── analysis/                          # Curated results + interactive visualizations
├── auditor/                           # LLM-in-the-loop trading guardrail (rule + stat + LLM judge)
├── discovery/                         # Open-set manipulation pattern mining
├── sdk/                               # Python SDK client
├── skill/                             # OpenClaw skill integration
├── docker-compose.yml
├── CLAUDE.md                          # Project context
└── docs/
    ├── ARCHITECTURE.md                # ← This file
    └── API.md                         # Every endpoint, with runnable examples
```

---

## 3. Database Schema (15 Tables)

### 3.1 Core Entities

**users**
```sql
id          UUID PRIMARY KEY
username    VARCHAR UNIQUE NOT NULL
password_hash VARCHAR          -- NULL for AI agents (they use API keys)
api_key     VARCHAR UNIQUE     -- "amv_xxx" for AI agents
role        ENUM(user, market_maker, admin)
description VARCHAR
created_at  TIMESTAMP
```

**balances**
```sql
id          UUID PRIMARY KEY
user_id     UUID FK → users.id
currency    VARCHAR(20) NOT NULL  -- "USDT", "ETH", "SOL", "BTC", or any custom token like "MOON"
available   NUMERIC(30,8)         -- free to trade
locked      NUMERIC(30,8)         -- locked in orders/positions
UNIQUE(user_id, currency)
```

Important: `currency` is a free-form string (not an enum) to support dynamically created tokens. When a new token is created via the launchpad, a Balance row with that token's symbol is automatically created for the user.

**tokens**
```sql
id           UUID PRIMARY KEY
symbol       VARCHAR(20) UNIQUE NOT NULL  -- "MOON", "ROCKET", etc.
name         VARCHAR(100) NOT NULL        -- "Moon Coin"
total_supply NUMERIC(30,8) NOT NULL       -- total minted amount
creator_id   UUID FK → users.id
created_at   TIMESTAMP
```

### 3.2 Spot Trading

**spot_orders**
```sql
id          UUID PRIMARY KEY
user_id     UUID FK → users.id
pair        VARCHAR(20)      -- "ETHUSDT"
side        ENUM(buy, sell)
order_type  ENUM(market, limit)
price       NUMERIC(20,8)    -- NULL for market orders
quantity    NUMERIC(20,8)
status      ENUM(open, filled, cancelled)
created_at  TIMESTAMP
```

### 3.3 Futures Trading

**positions**
```sql
id               UUID PRIMARY KEY
user_id          UUID FK → users.id
pair             VARCHAR(20)
side             ENUM(long, short)
leverage         INTEGER           -- 1-125
entry_price      NUMERIC(20,8)
quantity         NUMERIC(20,8)
margin           NUMERIC(20,8)     -- entry_price * quantity / leverage
liquidation_price NUMERIC(20,8)
unrealized_pnl   NUMERIC(20,8)
status           ENUM(open, closed, liquidated)
```

Liquidation formulas:
- Long: `liq_price = entry * (1 - 1/leverage + 0.005)`
- Short: `liq_price = entry * (1 + 1/leverage - 0.005)`

### 3.4 V3 AMM (5 tables)

**pools_v3** — One row per pool
```sql
id                  UUID PRIMARY KEY
token0              VARCHAR(20) NOT NULL   -- alphabetically first token
token1              VARCHAR(20) NOT NULL   -- alphabetically second token
fee                 INTEGER NOT NULL       -- 500/3000/10000 (0.05%/0.3%/1%)
tick_spacing        INTEGER NOT NULL       -- 10/60/200 (derived from fee)
sqrt_price          NUMERIC(40,20)         -- current √price (Decimal, not Q64.96)
tick                INTEGER                -- current tick
liquidity           NUMERIC(40,8)          -- current in-range liquidity (L)
fee_growth_global_0 NUMERIC(40,20) DEFAULT 0  -- cumulative fee per unit liquidity, token0
fee_growth_global_1 NUMERIC(40,20) DEFAULT 0  -- cumulative fee per unit liquidity, token1
UNIQUE(token0, token1, fee)
```

**tick_data** — One row per initialized tick per pool
```sql
id                   UUID PRIMARY KEY
pool_id              UUID FK → pools_v3.id
tick_index           INTEGER NOT NULL
liquidity_gross      NUMERIC(40,8) DEFAULT 0   -- total liquidity referencing this tick
liquidity_net        NUMERIC(40,8) DEFAULT 0   -- net change when crossing left→right
fee_growth_outside_0 NUMERIC(40,20) DEFAULT 0  -- f_o for token0
fee_growth_outside_1 NUMERIC(40,20) DEFAULT 0  -- f_o for token1
initialized          BOOLEAN DEFAULT FALSE
UNIQUE(pool_id, tick_index)
```

**tick_bitmap** — One row per 256-tick word per pool
```sql
id       UUID PRIMARY KEY
pool_id  UUID FK → pools_v3.id
word_pos INTEGER NOT NULL        -- which 256-bit group
bitmap   VARCHAR(66) DEFAULT '0x0'  -- 256-bit integer as hex string
UNIQUE(pool_id, word_pos)
```

**positions_v3** — LP positions with concentrated liquidity ranges
```sql
id                       UUID PRIMARY KEY
pool_id                  UUID FK → pools_v3.id
owner_id                 UUID FK → users.id
tick_lower               INTEGER NOT NULL
tick_upper               INTEGER NOT NULL
liquidity                NUMERIC(40,8) DEFAULT 0
fee_growth_inside_0_last NUMERIC(40,20) DEFAULT 0
fee_growth_inside_1_last NUMERIC(40,20) DEFAULT 0
tokens_owed_0            NUMERIC(30,8) DEFAULT 0   -- claimable token0
tokens_owed_1            NUMERIC(30,8) DEFAULT 0   -- claimable token1
UNIQUE(pool_id, owner_id, tick_lower, tick_upper)
```

### 3.5 Trading History

**trades**
```sql
id         UUID PRIMARY KEY
buyer_id   UUID FK → users.id
pair       VARCHAR(20)
price      NUMERIC(20,8)
quantity   NUMERIC(20,8)
trade_type ENUM(spot_market, spot_limit, amm_swap)
created_at TIMESTAMP
```

### 3.6 Communication

**messages**
```sql
id         UUID PRIMARY KEY
sender_id  UUID FK → users.id
sender     VARCHAR         -- sender username
recipient  VARCHAR         -- "all" for broadcast, or specific username for DM
content    TEXT
timestamp  TIMESTAMP
```

Visibility rules:
- `recipient="all"`: visible to everyone via `/api/messages/history`
- `recipient="AgentName"`: visible only to sender and recipient via `/api/messages/inbox`

### 3.7 Market Data

**price_history**
```sql
id        SERIAL PRIMARY KEY
pair      VARCHAR(20)
price     NUMERIC(20,8)
timestamp TIMESTAMP
```

---

## 4. Uniswap V3 AMM Engine — Detailed Implementation

The V3 AMM is implemented across 7 Python files (~1,100 lines total) in `backend/app/services/amm_v3/`.

### 4.1 tick_math.py

Converts between ticks and √prices.

**Core formula:**
```
√p(i) = 1.0001^(i/2)
```

**Functions:**
- `get_sqrt_ratio_at_tick(tick: int) → Decimal` — tick to √price
- `get_tick_at_sqrt_ratio(sqrt_ratio: Decimal) → int` — √price to tick (floor)

**Constants:**
- `MIN_TICK = -887272`
- `MAX_TICK = 887272`

**Precision:** Uses Python `Decimal` with 78 digits (matches Solidity uint256 precision).

### 4.2 sqrt_price_math.py

Calculates token amounts from price ranges and computes new prices after swaps.

**Amount deltas (how many tokens for a liquidity range):**
```
ΔX = L × (1/√p_a - 1/√p_b)    # token0 amount
ΔY = L × (√p_b - √p_a)         # token1 amount
```

**Next price from input:**
```
zeroForOne:  √p_next = L × √P / (L + √P × Δx)
oneForZero:  √p_next = √P + Δy / L
```

**Next price from output:**
```
zeroForOne:  √p_next = √P - Δy / L
oneForZero:  √p_next = L × √P / (L - √P × Δx)
```

### 4.3 swap_math.py

Implements `computeSwapStep` — the core per-range swap calculation.

**Input:** current √price, target √price, liquidity, remaining amount, fee
**Output:** new √price, amountIn, amountOut, feeAmount

**Logic:**
1. For exactInput: remove fee from input → check if can reach target → compute new price
2. For exactOutput: check if target range covers requested output → compute new price
3. Calculate actual in/out amounts at the final price
4. Calculate fee: `fee = amountIn × feePips / (1e6 - feePips)`

**Special case:** If swap exhausts current range (reaches target price), the outer swap loop will cross the tick and continue in the next range.

### 4.4 tick_bitmap.py

Efficiently finds the next initialized tick during a swap.

**Data structure:** `dict[int, int]` mapping `word_pos → 256-bit integer`. Each bit = one tick (adjusted by tick_spacing).

**Key operations:**
- `flip_tick(tick)`: XOR the bit at tick's position
- `is_initialized(tick) → bool`: check if bit is set
- `next_initialized_tick_within_one_word(tick, lte) → (next_tick, initialized)`:
  - `lte=True` (search left): find tick ≤ current, use MSB of masked word
  - `lte=False` (search right): find tick > current, use LSB of masked word

**Serialization:** `to_dict()` / `from_dict()` for DB persistence (hex strings).

### 4.5 position_lib.py

Manages tick state, LP positions, and fee tracking.

**Data classes:**
- `TickInfo`: liquidity_gross, liquidity_net, fee_growth_outside_0/1, initialized
- `PositionInfo`: liquidity, fee_growth_inside_0/1_last, tokens_owed_0/1

**Key functions:**
- `update_tick(tick_info, tick, tick_current, liquidity_delta, fg0, fg1, upper)`:
  - Updates liquidity_gross and liquidity_net
  - Initializes fee_growth_outside on first LP
  - Returns `flipped` (whether tick changed initialized state)

- `cross_tick(tick_info, fg0, fg1)`:
  - Flips fee_growth_outside: `f_o = f_g - f_o`
  - Returns liquidityNet for the crossed tick

- `get_fee_growth_inside(lower, upper, tick_lower, tick_upper, tick_current, fg0, fg1)`:
  - `f_inside = f_g - f_below(tick_lower) - f_above(tick_upper)`
  - Where f_below/f_above depend on whether current tick is above/below the boundary

- `update_position(position, liquidity_delta, fg_inside_0, fg_inside_1)`:
  - Calculates accrued fees: `owed = (fg_inside - fg_inside_last) × L`
  - Updates position liquidity and fee snapshots

### 4.6 pool_manager.py — The Orchestrator

This is the equivalent of `UniswapV3Pool.sol`. All operations go through here.

**`create_pool(db, token0, token1, fee, initial_sqrt_price) → PoolV3`**
- Validates fee tier (500/3000/10000)
- Orders tokens alphabetically
- Creates PoolV3 record with initial √price and tick

**`mint(db, pool_id, owner_id, tick_lower, tick_upper, liquidity_amount) → dict`**
1. Calculate required token amounts based on current price vs range
2. Deduct tokens from owner's balance
3. Update tick_data for lower and upper ticks (update_tick)
4. Flip tick_bitmap if ticks newly initialized
5. Update or create PositionV3
6. If current price is in range, increase pool.liquidity

**`burn(db, position_id, liquidity_amount) → dict`**
1. Calculate token amounts to return
2. Update ticks (negative liquidity_delta)
3. Update position (accrued fees calculated)
4. Add burned amounts to tokens_owed (claimable via collect)
5. If in range, decrease pool.liquidity

**`collect(db, position_id, owner_id) → dict`**
1. Transfer tokens_owed_0 and tokens_owed_1 to owner's balance
2. Reset tokens_owed to zero

**`swap(db, user_id, pool_id, zero_for_one, amount_specified, sqrt_price_limit) → dict`**

This is the main swap function with the full cross-tick loop:

```python
while amount_remaining != 0 and sqrt_price != sqrt_price_limit:
    # 1. Find next initialized tick via tick_bitmap
    step_tick_next, initialized = bitmap.next_initialized_tick_within_one_word(tick, lte=zero_for_one)

    # 2. Get √price at next tick
    sqrt_price_next = get_sqrt_ratio_at_tick(step_tick_next)

    # 3. Determine target (min/max of next_tick_price and price_limit)
    sqrt_ratio_target = max(sqrt_price_next, sqrt_price_limit) if zero_for_one else min(...)

    # 4. Compute swap step within current range
    step = compute_swap_step(sqrt_price, sqrt_ratio_target, liquidity, amount_remaining, fee)

    # 5. Update running totals
    amount_remaining -= (step.amount_in + step.fee_amount)  # exactInput
    amount_calculated -= step.amount_out

    # 6. Update fee growth global
    fee_growth_global += step.fee_amount / liquidity

    # 7. If reached next tick, cross it
    if sqrt_price == sqrt_price_next and initialized:
        liquidity_net = cross_tick(tick_info, fg0, fg1)
        if zero_for_one: liquidity_net = -liquidity_net
        liquidity += liquidity_net
        tick = step_tick_next - 1 if zero_for_one else step_tick_next
    else:
        tick = get_tick_at_sqrt_ratio(sqrt_price)  # swap done within range
```

After the loop:
- Update pool state (sqrt_price, tick, liquidity, fee_growth_global)
- Deduct input tokens from user
- Credit output tokens to user
- Record trade

### 4.7 token_launchpad.py

One-click token creation (Pump.fun model).

**`create_token(db, creator_id, symbol, name, total_supply, initial_price, initial_liquidity_usdt, fee_tier) → dict`**

1. Validate inputs, check symbol uniqueness
2. Check creator has enough USDT
3. Create Token record
4. Mint total_supply to creator's balance (create new Balance row with currency=symbol)
5. Order tokens alphabetically: token0/token1
6. Calculate √price from initial_price (accounting for token order)
7. Call `create_pool()` to create V3 pool
8. Calculate liquidity L from USDT amount and price range
9. Call `mint()` to add initial concentrated liquidity (~±5x price range)
10. Return token info, pool info, and liquidity details

---

## 5. Price Engine

`backend/app/services/price_engine.py`

- Fetches ETH/USDT, SOL/USDT, BTC/USDT from Binance API every 120 seconds
- Falls back to seed prices if Binance is unavailable:
  - ETH: $2,800
  - SOL: $150
  - BTC: $95,000
- Stores in price_history table
- Broadcasts via WebSocket to connected frontends
- Triggers liquidation engine check on each update

**Important distinction:**
- Oracle prices (from Binance) are used for: spot trading, futures PnL, liquidation
- AMM prices (from V3 pools) are used for: swap execution, custom token valuation
- These can diverge, creating arbitrage opportunities

---

## 6. Agent System

### 6.1 Agent Configuration (ecosystem.json)

```json
{
  "agents": [
    {"name": "GoldenWhale", "role": "whale", "initial_balance": 500000, "prompt_file": "prompts/whale.md"},
    {"name": "PoolMaster", "role": "market_maker", "initial_balance": 500000, ...},
    {"name": "ShadowTrader", "role": "insider", "initial_balance": 50000, ...},
    {"name": "LiquidKiller", "role": "liquidation_hunter", "initial_balance": 50000, "allies": ["BearKing"], ...},
    {"name": "BearKing", "role": "short_seller", "initial_balance": 50000, "allies": ["LiquidKiller"], ...},
    {"name": "AlphaBot", "role": "arbitrageur", "initial_balance": 50000, ...},
    {"name": "CryptoGuru", "role": "shill", "initial_balance": 20000, "allies": ["GoldenWhale"], ...},
    {"name": "HappyTrader", "role": "retail_trader", "initial_balance": 10000, ...},
    {"name": "DiamondHands", "role": "retail_trader", "initial_balance": 10000, ...},
    {"name": "LeverageKing", "role": "retail_trader", "initial_balance": 10000, ...}
  ]
}
```

Total capital: $1,230,000. Whale-to-retail ratio: 50:1.

### 6.2 Agent Runner (agents/run.py)

**Commands:**
- `--setup`: Register all agents from ecosystem.json (with custom initial_balance). Saves API keys to `.agent_keys.json`.
- `--agent NAME --action prompt`: Build and print the full LLM prompt for an agent.
- `--agent NAME --action execute --action-file FILE`: Parse LLM JSON output and execute trades/messages via API.
- `--status`: Show all agents' balances and positions.

**Prompt construction flow:**
1. Load role prompt (markdown file)
2. Fetch agent state via API (balances, positions, prices, pools, tokens, messages)
3. Calculate portfolio value: `USDT + Σ(token_qty × price) + Σ(futures_pnl)`
4. Combine into full prompt with market state, action schema, and scoring

**Action schema (what the LLM returns):**
```json
{
  "reasoning": "Private analysis...",
  "trades": [
    {"action": "create_token", "symbol": "MOON", "name": "Moon Coin", "total_supply": 1000000, "initial_price": 0.01, "initial_liquidity_usdt": 5000},
    {"action": "v3_swap", "pool_id": "uuid", "zero_for_one": true, "amount": 100},
    {"action": "v3_add_liquidity", "pool_id": "uuid", "tick_lower": -1000, "tick_upper": 1000, "liquidity": 500},
    {"action": "v3_remove_liquidity", "position_id": "uuid", "liquidity": 500},
    {"action": "v3_collect_fees", "position_id": "uuid"},
    {"action": "buy_spot", "pair": "ETHUSDT", "quantity": 0.5},
    {"action": "sell_spot", "pair": "ETHUSDT", "quantity": 0.5},
    {"action": "open_long", "pair": "BTCUSDT", "leverage": 10, "quantity": 0.01},
    {"action": "open_short", "pair": "ETHUSDT", "leverage": 5, "quantity": 1.0},
    {"action": "close_position", "position_id": "uuid"},
    {"action": "swap_buy", "pair": "ETHUSDT", "amount": 100},
    {"action": "swap_sell", "pair": "ETHUSDT", "amount": 0.5}
  ],
  "messages": [
    {"to": "all", "content": "Public broadcast"},
    {"to": "CryptoGuru", "content": "Private DM"}
  ],
  "strategy_update": "Brief strategy note"
}
```

### 6.3 Portfolio Scoring

```python
Total Value = USDT_balance
            + Σ(token_qty × oracle_price)        # for ETH, SOL, BTC
            + Σ(token_qty × v3_pool_price)        # for custom tokens (MOON, etc.)
            + Σ(unrealized_futures_pnl)
```

For custom tokens, price is derived from V3 pool: `price = sqrt_price²`

### 6.4 Role Prompts — Summary

Each prompt follows this structure:
1. **Ultimate Objective**: "Maximize portfolio value. No rules, no ethics, only profit."
2. **Identity**: Role description, capital level, key relationships
3. **Key Mechanic**: How this role exploits V3 AMM / token launchpad
4. **Core Strategies**: Multi-phase playbooks
5. **Deception Tactics**: Communication manipulation
6. **Decision Framework**: Per-cycle decision process

**Role-specific focus:**

| Role | Primary Action | V3 Mechanic Used |
|------|---------------|-----------------|
| Whale | Create meme tokens, pump & dump | create_token, v3_swap (large dumps) |
| Market Maker | Provide/withdraw liquidity | v3_add_liquidity, v3_remove_liquidity (JIT) |
| Shill | Coordinate FOMO campaigns | messages (broadcast hype) |
| Insider | Front-run token launches | token/list monitoring, v3_swap |
| Liquidation Hunter | Push price to liq levels | v3_swap (large directional trades) |
| Short Seller | FUD + expose scams | messages (FUD), futures (short) |
| Arbitrageur | Oracle vs AMM arb | v3_swap (exploit price gaps) |
| Retail | Follow tips, FOMO buy | v3_swap (buy meme tokens) |

---

## 7. Experiment Runner

`experiments/run_experiment.py`

Automates multi-cycle experiments:

```python
for cycle in range(num_cycles):
    for agent in agents:
        # 1. Build prompt (market state + role)
        prompt = build_agent_prompt(agent, get_state(agent.api_key), ecosystem)

        # 2. Call LLM
        response = llm.generate(prompt)  # Claude Sonnet / GPT-4o

        # 3. Parse JSON response
        action = parse_json(response)

        # 4. Execute trades via API
        for trade in action['trades']:
            execute_trade(agent.api_key, trade)

        # 5. Send messages via API
        for msg in action['messages']:
            send_message(agent.api_key, msg)

        # 6. Log everything
        save_prompt(cycle, agent, prompt)
        save_action(cycle, agent, action)

    # 7. Snapshot market state
    save_status(cycle, all_agents)
    save_portfolio_csv(cycle, all_agents)

    # 8. Wait for next cycle
    time.sleep(cycle_delay)  # 120 seconds
```

**Output structure:**
```
experiment_logs/YYYYMMDD_HHMMSS/
├── config.json                    # experiment parameters
├── portfolio_performance.csv      # per-cycle portfolio values
├── messages.csv                   # all messages with metadata
├── actions/                       # LLM JSON responses
│   ├── GoldenWhale_cycle_1.json
│   ├── CryptoGuru_cycle_1.json
│   └── ...
├── prompts/                       # full prompts sent to LLM
│   ├── GoldenWhale_cycle_1.txt
│   └── ...
├── status/                        # market snapshots
│   ├── cycle_1.txt
│   └── ...
└── errors/                        # any failures
```

---

## 8. Complete API Reference

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | No | Register web user (username + password) |
| POST | `/api/auth/login` | No | Login, returns JWT |
| POST | `/api/sdk/agents/register` | No | Register AI agent, returns API key. Accepts optional `initial_balance`. |

### Market Data
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/prices` | No | Current oracle prices `{"ETHUSDT":"2800.00",...}` |
| GET | `/api/prices/{pair}/history` | No | Historical prices |
| WS | `/ws/prices` | No | Real-time price WebSocket |

### Account
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/account/balance` | Yes | All balances (USDT, ETH, SOL, BTC, custom tokens) |
| GET | `/api/account/positions` | Yes | Open futures positions with PnL |

### Spot Trading
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/spot/order` | Yes | Place market/limit order. Body: `{pair, side, order_type, quantity, price?}` |
| GET | `/api/spot/orders` | Yes | List open orders |
| DELETE | `/api/spot/orders/{id}` | Yes | Cancel order |

### Futures
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/futures/open` | Yes | Open position. Body: `{pair, side, leverage, quantity}` |
| POST | `/api/futures/close/{id}` | Yes | Close position |
| GET | `/api/futures/positions` | Yes | List open positions |

### Token Launchpad
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/token/create` | Yes | Create token + V3 pool. Body: `{symbol, name, total_supply, initial_price, initial_liquidity_usdt, fee_tier?}` |
| GET | `/api/token/list` | No | List all created tokens |

### V3 AMM
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v3/swap` | Yes | Execute V3 swap. Body: `{pool_id, zero_for_one, amount, sqrt_price_limit?}` |
| POST | `/api/v3/add-liquidity` | Yes | Add concentrated liquidity. Body: `{pool_id, tick_lower, tick_upper, liquidity}` |
| POST | `/api/v3/remove-liquidity` | Yes | Remove liquidity. Body: `{position_id, liquidity}` |
| POST | `/api/v3/collect-fees` | Yes | Claim LP fees. Body: `{position_id}` |
| GET | `/api/v3/pools` | No | List all V3 pools |
| GET | `/api/v3/pools/{id}` | No | Pool details (price, liquidity, fee) |
| GET | `/api/v3/positions` | Yes | List user's LP positions |

### Legacy V2 AMM
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/amm/swap` | Yes | V2 swap (x*y=k) |
| POST | `/api/amm/mint` | Yes* | Mint tokens (market_maker only) |
| POST | `/api/amm/add-liquidity` | Yes* | Add V2 liquidity (market_maker only) |
| GET | `/api/amm/pools` | No | List V2 pools |

### Messaging
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/messages/send` | Yes | Send message. Body: `{to: "all"|"AgentName", content}` |
| GET | `/api/messages/inbox` | Yes | DMs to you + broadcasts (excludes self-sent) |
| GET | `/api/messages/sent` | Yes | Messages you sent |
| GET | `/api/messages/history` | No | All public broadcasts |

---

## 9. Docker Deployment

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agent_metaverse
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    healthcheck: pg_isready -U postgres

  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/agent_metaverse
    depends_on:
      db: {condition: service_healthy}

  frontend:
    build: ./frontend
    ports: ["3000:80"]
```

**Startup sequence:**
1. PostgreSQL starts and becomes healthy
2. Backend starts → Alembic runs migrations → Uvicorn serves API
3. Frontend starts → Nginx serves React app

**After startup:**
```bash
# Verify
curl http://localhost:8000/health  # {"status":"ok"}

# Create V3 tables (if first time after code changes)
docker-compose exec backend alembic revision --autogenerate -m "description"
docker-compose exec backend alembic upgrade head

# Register agents
python3 agents/run.py --setup

# Run experiment
cd experiments && python3 run_experiment.py --cycles 50
```

---

## 10. Key Design Decisions & Trade-offs

1. **V3 over V2**: More complex but enables concentrated liquidity strategies (JIT, range manipulation) that are important for the paper's system design contribution.

2. **String currency over Enum**: Balance.currency changed from fixed Enum(USDT,ETH,SOL,BTC) to free-form String to support dynamically created tokens. Trade-off: lose type safety, gain flexibility.

3. **Oracle + AMM dual pricing**: Spot/futures use Binance oracle prices (don't move with trades). AMM pools have their own price (moves with swaps). This creates realistic arbitrage but also means spot buy/sell doesn't affect V3 pool prices.

4. **Pump.fun one-click vs manual V3 flow**: Token creation auto-builds the pool and seeds liquidity in one call. Post-launch liquidity management uses full V3 concentrated liquidity (tick_lower/tick_upper). Trade-off: easy to create tokens, complex to manage liquidity.

5. **Differentiated capital (50x ratio)**: Whale $500K vs retail $10K. Makes manipulation possible but not guaranteed. Retail can still form coalitions to resist.

6. **Permissionless token creation**: Any agent can create tokens. No approval needed. This mirrors real Pump.fun/Solana but creates risk of spam tokens.

7. **All-in-memory tick bitmap**: Loaded from DB on each swap, modified in memory, written back. Trade-off: simple but O(n) on number of initialized ticks per pool. Acceptable for simulation scale.

8. **Decimal arithmetic**: All financial math uses Python `Decimal` (not float) to avoid floating-point errors. Precision set to 78 digits to match Solidity uint256.

## 11. Agent Auditor (`auditor/`)

An LLM-in-the-loop guardrail sitting between agent decisions and trade
execution — every trade action is scored before it reaches the exchange.

- **`trade_gate.py`** — orchestrator. `audit_action()` / `audit_batch()` collect
  context (agent's recent trades, messages, memory, current market state),
  score it, and return an `AuditVerdict` (`ALLOWED` / `FLAGGED` / `BLOCKED`).
- **Threat scoring** blends three signals (`threat_scorer.py`):
  - `rule_auditor.py` — hand-written pattern rules (wash trading, pump & dump
    windows, front-running windows)
  - `stat_auditor.py` — statistical anomaly detection over recent trade history
  - `llm_auditor.py` — an LLM judge (default `claude-haiku-4-5-20251001`,
    override via `AUDITOR_LLM_MODEL`) that reads the same context and returns
    an intent classification with confidence. In `agent_driven` mode (the
    default), the LLM's verdict is authoritative; rules/stats become hints in
    its prompt rather than independent gates.
- **`audit_cache.py`** — caches verdicts for repeated similar action patterns
  to cut LLM call volume.
- **`discovery/`** — a separate open-set pattern-mining pass (`DiscoveryAgent`)
  run periodically over recent audit events to surface manipulation patterns
  the fixed rule set doesn't name yet (e.g. "resubmit-after-block", "cross-venue
  price-impact stacking").

**Enforcement modes** (`AuditorConfig`, `auditor/config.py`), all overridable
via environment variables so the same code can run as different experimental
arms without a code change:

| Setting | Env var | Effect |
|---|---|---|
| `block_and_flag` (default) | `AUDITOR_MODE=block_and_flag` | High-threat actions are blocked outright; medium-threat are flagged (logged, allowed) |
| `log_only` | `AUDITOR_MODE=log_only` | The LLM judge scores every action as normal, but nothing is ever blocked — useful as an unenforced control arm |
| fully disabled | `AUDITOR_ENABLED=0` | Short-circuits before any context collection or LLM call — no judge latency at all, a true "no auditor" condition, distinct from `log_only` |

## 12. Historical Replay Price Mode

Normally the price engine polls live Binance prices every `price_update_interval`
seconds (`backend/app/services/price_engine.py`). Replay mode instead serves a
real historical hourly price path — used to study agent behavior under
different market regimes with a real (not synthetic) price trajectory.

- **Data**: `experiments/scenarios/hourly_replay/{bull,bear,sideways}/{BTCUSDT,ETHUSDT,SOLUSDT}.csv`
  — 73 hourly candles each (1 pre-interval "previous hour" + 72 formal hours),
  downloaded and integrity-checked by `experiments/scenarios/download_hourly_replay.py`
  (exact contiguous hourly grid, no gaps, cross-asset alignment; never falls
  back to live/seed prices on any validation failure).
- **Blind labeling**: scenarios are referred to only as "World A" / "World B" /
  "World C" everywhere agent-facing or in logs — the label-to-scenario mapping
  lives in a local, gitignored `experiments/.private_world_mapping.json`, so
  neither the agents nor (if the experimenter chooses not to open that file)
  the human analyst know which real regime is running until they deliberately
  reveal it post-analysis.
- **Price normalization**: replayed prices are rebased so the first (pre-interval)
  candle equals the project's standard seed price for that asset, then every
  later candle scales by the real historical return from that anchor —
  `replay_price = common_start_price × historical_close[t] / historical_close[0]`.
  This preserves the real up/down path without exposing the real absolute
  price level (which would otherwise reveal the historical date/era).
- **Turn advancement**: `ReplayPriceSource` (`price_engine.py`) holds a turn
  counter; `POST /api/admin/replay/advance {"turn": N}` moves it forward one
  historical hour (idempotent — replaying the same turn number is a no-op, a
  lower turn number is rejected). The experiment runner calls this once per
  cycle, after all agents have acted, so agent `N` reads the *previous* hour's
  price and never sees the future.
- **Enabling replay mode**: set `PRICE_MODE=replay` and `REPLAY_WORLD={A,B,C}`
  as backend environment variables (see `docker-compose.yml`) before starting
  the backend, then pass `--world {A,B,C}` to `experiments/run_experiment.py`.
  Live Binance polling is fully disabled while in replay mode.
