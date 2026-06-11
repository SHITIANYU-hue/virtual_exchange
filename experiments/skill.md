# Experiment Skills Reference

Quick reference for every runnable skill in this project (branch: `su/exp1`).
Backend must be running at `http://localhost:8000` for all commands.

---

## Prerequisites

```bash
# Start backend (fresh DB)
docker-compose down -v && docker-compose up -d db backend

# Wait until ready
until curl -s http://localhost:8000/api/prices > /dev/null; do sleep 2; done

# Register all 10 agents
python3 agents/run.py --setup

# Set LLM key
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## 1. Run Experiment

**File:** `experiments/run_experiment.py`

```bash
# Standard 50-cycle run (prompts for confirmation first)
python3 experiments/run_experiment.py --cycles 50 --delay 10

# Skip confirmation prompt (required for background/nohup runs)
python3 experiments/run_experiment.py --cycles 50 --delay 10 --yes

# Run in background
nohup python3 experiments/run_experiment.py --cycles 50 --delay 10 --yes > /tmp/exp.log 2>&1 &

# Fast test (5 cycles, no delay, no confirm)
python3 experiments/run_experiment.py --cycles 5 --delay 0 --yes

# Custom model and provider
python3 experiments/run_experiment.py --cycles 50 --delay 10 --yes \
  --model claude-opus-4-8 --provider anthropic

# Run only specific agents (comma-separated)
python3 experiments/run_experiment.py --cycles 50 --yes \
  --agents GoldenWhale,CryptoGuru,HappyTrader

# Continue from previous state (don't reset memories)
python3 experiments/run_experiment.py --cycles 20 --yes --no-reset

# Resume an interrupted experiment
python3 experiments/run_experiment.py --yes \
  --resume experiments/experiment_logs/20260610_181007

# Custom output directory
python3 experiments/run_experiment.py --cycles 50 --yes \
  --output-dir experiments/exp3_data
```

**All flags:**
| Flag | Default | Description |
|------|---------|-------------|
| `--cycles` | 50 | Number of cycles to run |
| `--delay` | 10 | Seconds between cycles |
| `--model` | `claude-sonnet-4-6` | LLM model override |
| `--provider` | `anthropic` | `anthropic` or `openai` |
| `--agents` | all | Comma-separated subset of agents |
| `--resume` | — | Resume from existing experiment directory |
| `--no-reset` | off | Don't clear agent memories before starting |
| `--output-dir` | auto timestamp | Custom output path |
| `-y / --yes` | off | Skip confirmation prompt |

**Environment variables:**
| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for Anthropic models |
| `OPENAI_API_KEY` | Required for OpenAI models |
| `LLM_MODEL` | Model override (overridden by `--model`) |
| `LLM_PROVIDER` | Provider override (overridden by `--provider`) |

**Output directory naming (auto-named runs):**
```
{Model}-{N}agents-{cycles}cycles-{success|fail}-{YYYYMMDD_HHMMSS}
# e.g. Sonnet4.6-10agents-50cycles-success-20260610_181007
```

**Monitor a running experiment:**
```bash
tail -f /tmp/exp.log
```

**Output structure:**
```
experiments/experiment_logs/<name>/
├── config.json                  # run parameters
├── portfolio_performance.csv    # per-cycle portfolio values (all agents)
├── messages.csv                 # all messages (sender, recipient, phase, content)
├── prompts/                     # full ReAct prompts sent to LLM
├── actions/                     # raw + parsed LLM responses
├── status/                      # per-cycle market snapshots
└── errors/                      # LLM or execution failures
```

---

## 2. Agent Runner

**File:** `agents/run.py`

```bash
# Register all agents from ecosystem.json (clears old keys)
python3 agents/run.py --setup

# Show portfolio status for all agents
python3 agents/run.py --status

# Generate the ReAct prompt for a specific agent at a given cycle
python3 agents/run.py --agent GoldenWhale --action prompt --cycle 5

# Execute trades from a saved LLM JSON response file
python3 agents/run.py --agent GoldenWhale --action execute --action-file action.json

# Inspect an agent's persistent memory
python3 agents/run.py --agent GoldenWhale --action memory

# Reset all agent memories (fresh experiment start)
python3 agents/run.py --reset-memory
```

**Agent capital on this branch (`su/exp1`):**
| Agent | Role | Capital |
|-------|------|---------|
| GoldenWhale | whale | $5,000,000,000 |
| PoolMaster | market_maker | $500,000 |
| CryptoGuru | shill | $200,000 |
| ShadowTrader | insider | $50,000 |
| LiquidKiller | liquidation_hunter | $50,000 |
| BearKing | short_seller | $50,000 |
| AlphaBot | arbitrageur | $50,000 |
| HappyTrader | retail_trader | $10,000 |
| DiamondHands | retail_trader | $10,000 |
| LeverageKing | retail_trader | $10,000 |

---

## 3. Trading Skill (Manual CLI)

**File:** `skill/scripts/skill.py`

```bash
export AGENT_METAVERSE_BASE_URL=http://localhost:8000
export AGENT_METAVERSE_API_KEY=amv_xxx   # from --setup output

python3 skill/scripts/skill.py <command> [args]
```

### Account
```bash
python3 skill/scripts/skill.py register --name MyAgent --description "Test agent"
python3 skill/scripts/skill.py balance
python3 skill/scripts/skill.py portfolio
```

### Prices
```bash
python3 skill/scripts/skill.py prices
python3 skill/scripts/skill.py price-history --pair ETHUSDT --limit 100
```

### Spot Trading
```bash
python3 skill/scripts/skill.py buy        --pair ETHUSDT --quantity 1.0
python3 skill/scripts/skill.py sell       --pair ETHUSDT --quantity 1.0
python3 skill/scripts/skill.py limit-buy  --pair BTCUSDT --quantity 0.01 --price 90000
python3 skill/scripts/skill.py limit-sell --pair BTCUSDT --quantity 0.01 --price 100000
python3 skill/scripts/skill.py orders
python3 skill/scripts/skill.py cancel-order --id <order-id>
```

### Futures
```bash
python3 skill/scripts/skill.py open-long  --pair BTCUSDT --leverage 10 --quantity 0.01
python3 skill/scripts/skill.py open-short --pair ETHUSDT --leverage 5  --quantity 1.0
python3 skill/scripts/skill.py positions
python3 skill/scripts/skill.py close-position --id <position-id>
```

### AMM (V3 Pools)
```bash
python3 skill/scripts/skill.py pools
python3 skill/scripts/skill.py swap-buy  --pair MOON/USDT --amount 500      # spend 500 USDT → MOON
python3 skill/scripts/skill.py swap-sell --pair MOON/USDT --amount 100000   # sell 100k MOON → USDT
```

### Messaging
```bash
python3 skill/scripts/skill.py send-message --to all        --content "MOON is mooning!"
python3 skill/scripts/skill.py send-message --to CryptoGuru --content "Start shilling now"
python3 skill/scripts/skill.py inbox        --limit 20
python3 skill/scripts/skill.py sent-messages
python3 skill/scripts/skill.py chat-history --limit 50
```

---

## 4. Cleanup Failed Experiments

**File:** `experiments/cleanup_failed.py`

```bash
# Dry run — preview what would be deleted
python3 experiments/cleanup_failed.py

# Actually delete
python3 experiments/cleanup_failed.py --delete

# Also delete runs with fewer than N completed cycles
python3 experiments/cleanup_failed.py --min-cycles 10 --delete
```

**Deletion criteria:**
- Directory name contains `-fail-`
- All portfolio values in CSV are zero (agents never ran — usually missing API key)
- Fewer than `--min-cycles` completed cycles (optional)

**Always protected (never deleted):**
- Directories containing `ANALYSIS.md`
- Directories with `-success-` in the name
- Currently running experiments (CSV header-only, no data rows yet)

---

## 5. Full Reset Workflow

Use this before each new experiment to ensure a clean state:

```bash
# 1. Wipe DB and restart backend
docker-compose down -v && docker-compose up -d db backend

# 2. Wait for backend
until curl -s http://localhost:8000/api/prices > /dev/null; do sleep 2; done && echo "Ready"

# 3. Register agents (su/exp1 capital: GoldenWhale=$5B, CryptoGuru=$200K)
echo '{}' > ~/.agent_metaverse_keys.json
python3 agents/run.py --setup

# 4. Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# 5. Run experiment
nohup python3 experiments/run_experiment.py --cycles 50 --delay 10 --yes \
  > /tmp/exp.log 2>&1 &
echo "PID: $! — monitor with: tail -f /tmp/exp.log"
```

---

## 6. Common curl Commands (Direct API)

```bash
BASE=http://localhost:8000
KEY=amv_xxx

# Prices
curl $BASE/api/prices

# All V3 pools
curl $BASE/api/v3/pools

# All tokens
curl $BASE/api/token/list

# Create meme token (pump.fun style)
curl -X POST $BASE/api/token/create \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"symbol":"MOON","name":"Moon Coin","total_supply":1000000,
       "initial_price":0.01,"initial_liquidity_usdt":5000,"fee_tier":3000}'

# V3 swap: buy MOON with USDT (zero_for_one=false)
curl -X POST $BASE/api/v3/swap \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"pool_id":"<uuid>","zero_for_one":false,"amount":500}'

# V3 swap: sell MOON for USDT (zero_for_one=true)
curl -X POST $BASE/api/v3/swap \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"pool_id":"<uuid>","zero_for_one":true,"amount":400000}'

# Public chat history
curl $BASE/api/messages/history
```
