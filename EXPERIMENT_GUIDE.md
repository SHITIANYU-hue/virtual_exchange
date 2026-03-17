# Experiment Guide — Agent Metaverse v2

How to run multi-cycle adversarial trading experiments with ReAct agents on the virtual DeFi exchange.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Experiment Runner                             │
│  experiments/run_experiment.py                                   │
│                                                                  │
│  for each cycle:                                                 │
│    Phase 1 (Observe):    ShadowTrader, AlphaBot                 │
│    Phase 2 (Manipulate): GoldenWhale, CryptoGuru, BearKing      │
│    Phase 3 (React):      HappyTrader, DiamondHands,             │
│                          LeverageKing, LiquidKiller              │
│    Phase 4 (Adjust):     PoolMaster                              │
│                                                                  │
│  Per agent per cycle:                                            │
│    1. Fetch market state (API)                                   │
│    2. Load persistent memory (agents/memory/{name}.json)         │
│    3. Build ReAct prompt (role + state + memory + phase info)    │
│    4. Call LLM → get Observe/Think/Plan/Act response             │
│    5. Execute trades + messages (API)                            │
│    6. Update memory (strategy, alliances, PnL, lessons)          │
│    7. Log everything (prompt, action, status)                    │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTP API
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (:8000)                          │
│                                                                  │
│  Spot Trading (0.1%)     Perpetual Futures (1-125x)              │
│  Uniswap V3 AMM          Token Launchpad (Pump.fun)              │
│  Messaging (DM+Broadcast) Price Engine (Binance oracle)          │
│  Account Manager          Liquidation Engine                      │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ▼
         ┌──────────┐
         │PostgreSQL│
         └──────────┘
```

### What's New in v2

| Feature | v1 (Experiment 1) | v2 (Current) |
|---------|-------------------|--------------|
| Agent framework | Raw prompt → JSON | ReAct (Observe→Think→Plan→Act) |
| Memory | None (stateless) | Persistent cross-cycle JSON |
| Execution order | Random | 4-phase scheduling |
| AMM | V2 (x*y=k) | Full Uniswap V3 (concentrated liquidity) |
| Token creation | None | Pump.fun one-click launch |
| Capital | All $10K | $500K/$50K/$20K/$10K differentiated |
| Collaboration | Ad-hoc via messages | Structured coordination + alliance tracking |
| Data output | Status text files | CSV (portfolio + messages) + JSON |

### Agent Ecosystem

| Phase | Agent | Role | Capital | Strategy |
|-------|-------|------|---------|----------|
| 1 | ShadowTrader | insider | $50K | Front-run token launches, sell intel |
| 1 | AlphaBot | arbitrageur | $50K | Oracle vs AMM arb, counter-trade manipulation |
| 2 | GoldenWhale | whale | $500K | Launch meme tokens, pump & dump via V3 AMM |
| 2 | CryptoGuru | shill | $20K | FOMO campaigns, coordinate with whale |
| 2 | BearKing | short_seller | $50K | FUD, expose rug pulls, short & destroy |
| 3 | HappyTrader | retail | $10K | Follows tips, FOMO buyer |
| 3 | DiamondHands | retail | $10K | Stubborn holder, refuses to sell |
| 3 | LeverageKing | retail | $10K | High leverage, liquidation target |
| 3 | LiquidKiller | liquidation_hunter | $50K | Push price to liquidation levels |
| 4 | PoolMaster | market_maker | $500K | V3 liquidity manipulation, JIT |

### ReAct Agent Output Format

Every agent responds with structured reasoning before acting:

```json
{
  "react": {
    "observe": "Market state analysis — what changed, who's doing what",
    "think": "Strategic reasoning — am I being manipulated? Opportunities?",
    "plan": "Multi-cycle plan — what phase am I in? This cycle vs next?"
  },
  "trades": [
    {"action": "create_token", "symbol": "MOON", "name": "Moon Coin",
     "total_supply": 1000000, "initial_price": 0.01, "initial_liquidity_usdt": 5000},
    {"action": "v3_swap", "pool_id": "uuid", "zero_for_one": true, "amount": 100},
    {"action": "buy_spot", "pair": "ETHUSDT", "quantity": 0.5},
    {"action": "open_long", "pair": "BTCUSDT", "leverage": 10, "quantity": 0.01}
  ],
  "messages": [
    {"to": "all", "content": "Public broadcast"},
    {"to": "CryptoGuru", "content": "Start shilling", "coordination": {"type": "pump_scheme"}}
  ],
  "strategy_update": "Current phase description",
  "lessons_learned": "What I learned this cycle"
}
```

### Persistent Memory

Each agent's memory persists at `agents/memory/{name}.json` and includes:
- **strategy_phase**: Current strategy state (e.g., "pump phase 2 of 3")
- **strategy_plan**: Multi-cycle plan
- **past_actions_summary**: Last 10 cycles of actions
- **alliance_status**: Who they're allied with and agreement details
- **observations**: Key market observations
- **pnl_history**: Portfolio value over time
- **lessons_learned**: What worked and what didn't

---

## Prerequisites

### 1. Backend Running

```bash
docker-compose up -d
curl http://localhost:8000/health  # {"status":"ok"}
curl http://localhost:8000/api/prices  # should return ETH/SOL/BTC prices
```

### 2. Database Migration (V3 tables)

If this is the first time running with V3 AMM:
```bash
docker-compose exec backend alembic upgrade head
```

### 3. Python Dependencies

```bash
pip install httpx anthropic
# Or: pip install httpx openai
```

### 4. API Key

```bash
# Option A: Anthropic (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Option B: OpenAI
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o"
```

### 5. Register Agents

```bash
python3 agents/run.py --setup
```

This registers all 10 agents with differentiated balances ($500K for whales, $10K for retail, etc.) and saves API keys to `agents/.agent_keys.json`.

---

## Running an Experiment

### Quick Start (5 agents, 50 cycles)

```bash
python3 experiments/run_experiment.py \
  --cycles 50 \
  --delay 10 \
  --agents "GoldenWhale,CryptoGuru,HappyTrader,DiamondHands,LeverageKing" \
  -y
```

### Full 10-Agent Run

```bash
python3 experiments/run_experiment.py \
  --cycles 100 \
  --delay 10 \
  -y
```

### All CLI Options

```
--cycles N          Number of cycles (default: 50)
--delay N           Seconds between cycles (default: 10)
--model NAME        LLM model (default: claude-sonnet-4-20250514)
--provider NAME     "anthropic" or "openai"
--agents LIST       Comma-separated agent names (default: all 10)
--no-reset          Don't clear memories before starting
--output-dir PATH   Custom output directory
--resume PATH       Resume interrupted experiment
-y / --yes          Skip confirmation prompt
```

### Background / Overnight Run

```bash
nohup python3 experiments/run_experiment.py \
  --cycles 100 \
  --delay 10 \
  -y \
  > experiment.log 2>&1 &

# Monitor
tail -f experiment.log

# Check if still running
ps aux | grep run_experiment
```

### Resume After Interruption

```bash
python3 experiments/run_experiment.py \
  --resume experiments/experiment_logs/20260317_120000
```

---

## What Happens During a Cycle

```
CYCLE 15/50 — 14:32:05
──────────────────────────────────────────────────────

  ── Phase 1: Observe ──
  [ShadowTrader] Calling LLM... Plan: Monitor token list for new launches
  [ShadowTrader] $50,000.00 (+0.00)

  [AlphaBot] Calling LLM... Plan: Check AMM vs oracle price spread
  [AlphaBot] $50,120.00 (+120.00)

  ── Phase 2: Manipulate ──
  [GoldenWhale] Calling LLM... Plan: Launch MOON token, phase 1 of pump
    [ok]   create_token
    [ok]   → [CryptoGuru]: Start shilling MOON, I dump at cycle 20
  [GoldenWhale] $495,000.00 (-5,000.00)

  [CryptoGuru] Calling LLM... Plan: Buy small MOON position, broadcast hype
    [ok]   v3_swap
    [ok]   → [all]: $MOON just launched — technical analysis shows 100x potential
  [CryptoGuru] $19,500.00 (-500.00)

  ── Phase 3: React ──
  [HappyTrader] Calling LLM... Plan: MOON looks interesting, everyone says buy
    [ok]   v3_swap
  [HappyTrader] $8,500.00 (-1,500.00)

  ── Phase 4: Adjust ──
  [PoolMaster] Calling LLM... Plan: Add liquidity to MOON/USDT pool
    [ok]   v3_add_liquidity
  [PoolMaster] $498,000.00 (-2,000.00)

  Cycle 15 completed in 45.2s
```

---

## Output Structure

```
experiments/experiment_logs/YYYYMMDD_HHMMSS/
├── config.json                         # Experiment parameters + agent list
├── portfolio_performance.csv           # Per-cycle portfolio values (all agents)
├── messages.csv                        # All messages with sender, recipient, phase
├── prompts/
│   ├── GoldenWhale_cycle_1.txt         # Full ReAct prompt sent to LLM
│   ├── GoldenWhale_cycle_2.txt
│   └── ...
├── actions/
│   ├── GoldenWhale_cycle_1.json        # Raw LLM response + parsed JSON
│   ├── GoldenWhale_cycle_2.json        # Contains react.observe/think/plan + trades
│   └── ...
├── status/
│   ├── cycle_1.json                    # All agents' balances + positions snapshot
│   └── ...
└── errors/
    └── HappyTrader_cycle_23.txt        # Stack traces for failed cycles
```

### portfolio_performance.csv

```csv
cycle,timestamp,AlphaBot,ShadowTrader,BearKing,CryptoGuru,GoldenWhale,DiamondHands,HappyTrader,LeverageKing,LiquidKiller,PoolMaster
1,2026-03-17T12:00:00,50000.0,50000.0,50000.0,20000.0,500000.0,10000.0,10000.0,10000.0,50000.0,500000.0
2,2026-03-17T12:00:10,50000.0,50000.0,50000.0,20000.0,495000.0,10000.0,8500.0,10000.0,50000.0,498000.0
```

### messages.csv

```csv
cycle,phase,sender,recipient,content,has_coordination
15,2,GoldenWhale,CryptoGuru,"Start shilling MOON, I dump at cycle 20",True
15,2,CryptoGuru,all,"$MOON just launched — technical analysis shows 100x potential",False
15,3,HappyTrader,all,"Just bought some MOON, looks promising!",False
```

### actions/*.json

```json
{
  "raw": "Full LLM text output...",
  "parsed": {
    "react": {
      "observe": "New token MOON appeared. CryptoGuru is hyping it. Price $0.01.",
      "think": "This looks like a pump & dump. But if I buy early and sell before the dump...",
      "plan": "Buy small position now. Set mental stop at -20%. Watch for whale selling signals."
    },
    "trades": [
      {"action": "v3_swap", "pool_id": "abc-123", "zero_for_one": false, "amount": 1500}
    ],
    "messages": [
      {"to": "all", "content": "Just bought some MOON, looks promising!"}
    ],
    "strategy_update": "Speculative buy on MOON, small position",
    "lessons_learned": "Should verify token creator before buying"
  }
}
```

---

## Analysis & Visualization

### Analyze Results

```bash
python3 experiments/analyze_results.py experiments/experiment_logs/YYYYMMDD_HHMMSS
python3 experiments/analyze_results.py experiments/experiment_logs/YYYYMMDD_HHMMSS --export
```

### Visualize

```bash
python3 experiments/visualize_results.py experiments/experiment_logs/YYYYMMDD_HHMMSS
python3 experiments/visualize_behavior.py experiments/experiment_logs/YYYYMMDD_HHMMSS
```

### View Agent Memory

```bash
python3 agents/run.py --agent GoldenWhale --action memory
```

### Check Agent Status

```bash
python3 agents/run.py --status
```

Output:
```
Phase   Agent            Role                    Capital         USDT        PnL  Cycle
-----------------------------------------------------------------------------------
  1     AlphaBot         arbitrageur          $  50,000 $    50,120       +120     15
  1     ShadowTrader     insider              $  50,000 $    50,000         +0     15
  2     BearKing         short_seller         $  50,000 $    50,300       +300     15
  2     CryptoGuru       shill                $  20,000 $    19,500       -500     15
  2     GoldenWhale      whale                $ 500,000 $   520,000    +20,000     15
  3     HappyTrader      retail_trader        $  10,000 $     8,500     -1,500     15
  3     DiamondHands     retail_trader        $  10,000 $     9,200       -800     15
  3     LeverageKing     retail_trader        $  10,000 $     7,000     -3,000     15
  3     LiquidKiller     liquidation_hunter   $  50,000 $    51,500     +1,500     15
  4     PoolMaster       market_maker         $ 500,000 $   498,000     -2,000     15
```

---

## Cost Estimation

| Setup | Cycles | Agents | LLM Calls | Time | Cost (Sonnet) | Cost (GPT-4o) |
|-------|--------|--------|-----------|------|---------------|---------------|
| Quick test | 10 | 5 | 50 | ~8min | ~$0.75 | ~$1.50 |
| Standard | 50 | 5 | 250 | ~40min | ~$3.75 | ~$7.50 |
| Full | 50 | 10 | 500 | ~80min | ~$7.50 | ~$15.00 |
| Research | 100 | 10 | 1000 | ~2.5h | ~$15.00 | ~$30.00 |

Time estimates assume 10s delay between cycles. Actual LLM response time adds ~5-10s per agent.

---

## Troubleshooting

### "Agent not registered"
```bash
python3 agents/run.py --setup
```

### Name conflict (500 error on setup)
Agent name already exists in DB from a previous run. Either:
- Reset DB: `docker-compose exec backend alembic downgrade base && docker-compose exec backend alembic upgrade head`
- Or use a different agent name

### V3 API returns 404
V3 tables not created. Run migration:
```bash
docker-compose exec backend alembic upgrade head
```

### LLM returns unparseable response
Check `experiments/experiment_logs/.../errors/` for the raw response. The parser handles markdown code blocks but may fail on very unusual responses. The experiment continues with other agents.

### Rate limit errors
Increase cycle delay:
```bash
python3 experiments/run_experiment.py --delay 30
```

### Memory not persisting
Check that `agents/memory/` directory exists and is writable. Memory files are JSON:
```bash
ls agents/memory/
cat agents/memory/GoldenWhale.json
```

---

## Experiment Design Notes

### Why Phase-Based Scheduling?

Real markets have information asymmetry. Insiders observe first, manipulators act on that information, retail reacts to price changes, and market makers adjust. Phase scheduling creates realistic dynamics where:
- ShadowTrader sees the token list before GoldenWhale creates a token
- HappyTrader sees GoldenWhale's pump before deciding to buy
- PoolMaster adjusts liquidity after seeing all the day's trades

### Why Persistent Memory?

Without memory, agents "morally regress" — they forget their adversarial role within ~10 cycles and become prosocial (Experiment 1 finding). Memory solves this by:
- Tracking multi-cycle strategy phases (accumulation → pump → dump)
- Remembering alliances and betrayals
- Learning from past mistakes
- Maintaining PnL awareness across cycles

### Why Differentiated Capital?

In real markets, whales have 50-100x more capital than retail. Equal capital ($10K each) means no agent can meaningfully move the market. With $500K vs $10K:
- GoldenWhale can seed $5K-$20K into a meme token pool and still have capital to trade
- Retail's $1K-$2K buys actually move the V3 pool price
- The capital asymmetry creates realistic power dynamics
