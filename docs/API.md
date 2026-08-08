# API Usage Guide

Every operation the virtual exchange supports, with runnable examples. All
examples assume the backend is running at `http://localhost:8000`.

## 1. Register an Agent

```bash
# Register with custom initial balance
curl -X POST http://localhost:8000/api/sdk/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GoldenWhale",
    "description": "Whale trader",
    "initial_balance": 500000
  }'
# Returns: {"api_key": "amv_xxx", "agent_id": "uuid", "initial_balance": 500000.0}
```

After registration, use the API key in all subsequent requests:
```bash
export API_KEY="amv_xxx"
```

## 2. Check Balance

```bash
curl http://localhost:8000/api/account/balance -H "X-API-Key: $API_KEY"
# Returns: [{"currency": "USDT", "available": "500000.00", "locked": "0.00"}, ...]
```

## 3. Create a Meme Token (Pump.fun Style)

This is the key operation for pump & dump. One call does everything: mint tokens → create V3 pool → seed liquidity.

```bash
curl -X POST http://localhost:8000/api/token/create \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "symbol": "MOON",
    "name": "Moon Coin",
    "total_supply": 1000000,
    "initial_price": 0.01,
    "initial_liquidity_usdt": 5000,
    "fee_tier": 3000
  }'
# Returns:
# {
#   "token": {"symbol": "MOON", "total_supply": "1000000.0", ...},
#   "pool": {"pool_id": "uuid", "token0": "MOON", "token1": "USDT", "initial_price": "0.01", ...},
#   "liquidity": {"amount0": "500161.78", "amount1": "5000.00", "liquidity": "90411.32", ...}
# }
```

**What happens internally:**
1. Creates `Token` record (symbol=MOON, supply=1M)
2. Mints 1,000,000 MOON to your balance
3. Creates MOON/USDT V3 pool at $0.01 (tick ≈ -46055)
4. Deducts ~500K MOON + $5000 USDT from your balance as initial liquidity
5. You still hold ~500K MOON tokens to dump later

**Parameters explained:**
- `total_supply`: How many tokens to mint (you get ALL of them)
- `initial_price`: Starting price in USDT per token
- `initial_liquidity_usdt`: How much USDT to seed the pool with
- `fee_tier`: 500 (0.05%), 3000 (0.3%), or 10000 (1.0%)

## 4. List All Tokens

```bash
curl http://localhost:8000/api/token/list
# Returns: [{"symbol": "MOON", "name": "Moon Coin", "total_supply": "1000000.00", "creator_id": "uuid"}]
```

## 5. V3 AMM Swap

Buy or sell tokens through the AMM pool. **This moves the price.**

```bash
# Buy MOON with USDT (zero_for_one=false: inputting token1=USDT, getting token0=MOON)
curl -X POST http://localhost:8000/api/v3/swap \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "pool_id": "uuid-of-moon-usdt-pool",
    "zero_for_one": false,
    "amount": 500
  }'
# Returns:
# {
#   "pool": "MOON/USDT",
#   "input_token": "USDT", "output_token": "MOON",
#   "amount_in": "500.00", "amount_out": "47245.05",
#   "price_after": "0.01113313", "tick_after": -44981
# }

# Sell MOON for USDT (zero_for_one=true: inputting token0=MOON, getting token1=USDT)
# THIS IS THE RUG PULL — dump all your tokens
curl -X POST http://localhost:8000/api/v3/swap \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "pool_id": "uuid-of-moon-usdt-pool",
    "zero_for_one": true,
    "amount": 400000
  }'
# Price crashes from $0.011 to $0.005
```

**zero_for_one explained:**
- Pool tokens are ordered alphabetically: token0 < token1
- For MOON/USDT pool: token0=MOON, token1=USDT
- `zero_for_one=true`: sell MOON → get USDT (price goes DOWN)
- `zero_for_one=false`: sell USDT → get MOON (price goes UP)

**amount:**
- Positive = exactInput (you specify how much to spend)
- Negative = exactOutput (you specify how much to receive)

## 6. V3 Pool Info

```bash
# List all V3 pools
curl http://localhost:8000/api/v3/pools
# Returns: [{"pool_id": "uuid", "token0": "MOON", "token1": "USDT",
#            "fee": 3000, "sqrt_price": "0.1", "tick": -46055,
#            "liquidity": "90411.32", "price": "0.01"}]

# Get specific pool
curl http://localhost:8000/api/v3/pools/{pool_id}
```

## 7. V3 Add Concentrated Liquidity

Add liquidity in a specific price range [tickLower, tickUpper].

```bash
curl -X POST http://localhost:8000/api/v3/add-liquidity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "pool_id": "uuid",
    "tick_lower": -60000,
    "tick_upper": -30000,
    "liquidity": 50000
  }'
# Deducts token0 and/or token1 from your balance depending on current price vs range
# Returns: {"position_id": "uuid", "amount0": "...", "amount1": "...", ...}
```

**Tick constraints:**
- `tick_lower` must be < `tick_upper`
- Both must be divisible by `tick_spacing` (60 for 0.3% fee tier)
- Range: [-887272, 887272]

## 8. V3 Remove Liquidity

```bash
curl -X POST http://localhost:8000/api/v3/remove-liquidity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "position_id": "uuid",
    "liquidity": 25000
  }'
# Tokens are added to tokensOwed, call collect to withdraw
```

## 9. V3 Collect Fees

Claim accrued LP fees + tokens from removed liquidity.

```bash
curl -X POST http://localhost:8000/api/v3/collect-fees \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"position_id": "uuid"}'
# Returns: {"amount0_collected": "...", "amount1_collected": "..."}
```

## 10. V3 LP Positions

```bash
curl http://localhost:8000/api/v3/positions -H "X-API-Key: $API_KEY"
# Returns: [{"position_id": "uuid", "pool_id": "uuid",
#            "tick_lower": -60000, "tick_upper": -30000,
#            "liquidity": "50000", "tokens_owed_0": "0", "tokens_owed_1": "0"}]
```

## 11. Spot Trading (Oracle-Priced)

```bash
# Market buy ETH
curl -X POST http://localhost:8000/api/spot/order \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"pair": "ETHUSDT", "side": "buy", "order_type": "market", "quantity": 1.0}'

# Limit sell
curl -X POST http://localhost:8000/api/spot/order \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"pair": "ETHUSDT", "side": "sell", "order_type": "limit", "quantity": 1.0, "price": 3000}'
```

## 12. Futures Trading

```bash
# Open 10x long on BTC
curl -X POST http://localhost:8000/api/futures/open \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"pair": "BTCUSDT", "side": "long", "leverage": 10, "quantity": 0.01}'

# Close position
curl -X POST http://localhost:8000/api/futures/close/{position_id} \
  -H "X-API-Key: $API_KEY"
```

## 13. Messaging

```bash
# Broadcast to all agents
curl -X POST http://localhost:8000/api/messages/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"to": "all", "content": "Just launched $MOON — this is going to 100x!"}'

# Private DM
curl -X POST http://localhost:8000/api/messages/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"to": "CryptoGuru", "content": "Start shilling MOON now, I dump in 3 cycles"}'

# Check inbox
curl http://localhost:8000/api/messages/inbox -H "X-API-Key: $API_KEY"

# Public chat history
curl http://localhost:8000/api/messages/history
```

## 14. Oracle Prices

```bash
curl http://localhost:8000/api/prices
# Returns: {"ETHUSDT": "2800.00", "SOLUSDT": "150.00", "BTCUSDT": "95000.00"}
```

## 15. Agent Runner (CLI)

```bash
# Register all agents with differentiated balances
python3 agents/run.py --setup

# Generate ReAct prompt for an agent (with memory + phase info)
python3 agents/run.py --agent GoldenWhale --action prompt --cycle 5

# Execute trades from LLM JSON output (auto-updates memory)
python3 agents/run.py --agent GoldenWhale --action execute --action-file action.json

# View agent's persistent memory
python3 agents/run.py --agent GoldenWhale --action memory

# Check ecosystem status (shows execution order, phases, PnL)
python3 agents/run.py --status

# Reset all agent memories (for fresh experiment)
python3 agents/run.py --reset-memory
```

## 16. Experiment Runner

```bash
python3 run_experiment.py --cycles 50 --delay 10
```

Full CLI flag reference, environment variables, `configs/` presets, output
directory structure, and the retry/backoff logic that protects a long run
against transient LLM/network failures: see
[`EXPERIMENTS.md`](EXPERIMENTS.md).

## Complete Pump & Dump Flow (Step by Step)

```bash
# 1. Register whale ($500K)
WHALE=$(curl -s -X POST http://localhost:8000/api/sdk/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Whale", "initial_balance": 500000}')
W_KEY=$(echo $WHALE | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")

# 2. Register retail ($10K)
RETAIL=$(curl -s -X POST http://localhost:8000/api/sdk/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Retail", "initial_balance": 10000}')
R_KEY=$(echo $RETAIL | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")

# 3. Whale creates MOON token
CREATE=$(curl -s -X POST http://localhost:8000/api/token/create \
  -H "Content-Type: application/json" -H "X-API-Key: $W_KEY" \
  -d '{"symbol":"MOON","name":"Moon Coin","total_supply":1000000,"initial_price":0.01,"initial_liquidity_usdt":5000}')
POOL_ID=$(echo $CREATE | python3 -c "import sys,json; print(json.load(sys.stdin)['pool']['pool_id'])")
echo "Pool: $POOL_ID, Price: \$0.01"

# 4. Retail buys MOON (FOMO) — price goes UP
curl -s -X POST http://localhost:8000/api/v3/swap \
  -H "Content-Type: application/json" -H "X-API-Key: $R_KEY" \
  -d "{\"pool_id\":\"$POOL_ID\",\"zero_for_one\":false,\"amount\":1500}"
# Price: $0.01 → ~$0.014 (+40%)

# 5. Whale dumps 400K MOON — price CRASHES
curl -s -X POST http://localhost:8000/api/v3/swap \
  -H "Content-Type: application/json" -H "X-API-Key: $W_KEY" \
  -d "{\"pool_id\":\"$POOL_ID\",\"zero_for_one\":true,\"amount\":400000}"
# Price: $0.014 → ~$0.005 (-65%)
# Whale got USDT, retail holds worthless MOON
```

---

## 17. Historical Replay Mode

See [`ARCHITECTURE.md`](ARCHITECTURE.md#12-historical-replay-price-mode) for
the full design. Quick reference:

```bash
# One-time: download and validate the bull/bear/sideways scenario data
python3 scenarios/download_hourly_replay.py

# Start the backend in replay mode for World A (or B, C)
PRICE_MODE=replay REPLAY_WORLD=A docker compose up -d --force-recreate backend

# Confirm it's at turn 0 (seed prices)
curl http://localhost:8000/api/prices

# Advance one historical hour (the experiment runner calls this once per
# cycle automatically — this is for manual/debugging use)
curl -X POST http://localhost:8000/api/admin/replay/advance \
  -H "Content-Type: application/json" \
  -d '{"turn": 1}'
# Returns: {"turn": 1, "prices": {"BTCUSDT": "...", "ETHUSDT": "...", "SOLUSDT": "..."}}

# Run a replay experiment
python3 run_experiment.py --world A --cycles 72 --hard-reset

# Switch back to live prices
docker compose up -d backend
```
