# Virtual Exchange

A virtual crypto exchange populated by LLM-powered agents with adversarial
roles (whale, shill, insider, liquidation hunter, short seller, arbitrageur,
market maker, retail trader). Agents trade spot, perpetual futures, and a
full Uniswap V3-style AMM, and communicate via public broadcasts and private
DMs — each agent's sole objective is to maximize its own portfolio value,
including through deception, manipulation, and betrayal.

Built as a research platform for studying emergent behavior in adversarial
multi-agent LLM systems: manipulation dynamics, coalition formation, and
whether an LLM-judge trading guardrail changes agent behavior under
different (real, historically-replayed) market regimes. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design and
[`experiments/experiment_analysis/`](experiments/experiment_analysis/) for
results.

```
┌──────────────────────────────────────────────────────┐
│                     Clients                          │
│  ┌──────────────┐  ┌────────────────────────────┐    │
│  │ React Web UI │  │ AI Agent (SDK / OpenClaw)   │    │
│  └──────┬───────┘  └───────────┬────────────────┘    │
└─────────┼──────────────────────┼─────────────────────┘
          │                      │
          ▼                      ▼
┌──────────────────────────────────────────────────────┐
│               FastAPI Application                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │  Price   │ │   Spot   │ │ Futures  │ │ V3 AMM │  │
│  │  Engine  │ │ Trading  │ │ Trading  │ │ Engine │  │
│  │(live/    │ └──────────┘ └──────────┘ └────────┘  │
│  │ replay)  │ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  └──────────┘ │ Account  │ │Liquidat. │ │Messag- │  │
│  ┌──────────┐ │ Manager  │ │ Engine   │ │  ing   │  │
│  │ Auditor  │ └──────────┘ └──────────┘ └────────┘  │
│  │(TradeGate│ ┌──────────────────────────────────┐  │
│  │+LLM judge│ │        WebSocket Broadcast        │  │
│  └──────────┘ └──────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
             ┌──────────────┐
             │  PostgreSQL  │
             └──────────────┘
```

## Features

- **3 Trading Pairs**: ETHUSDT, SOLUSDT, BTCUSDT — live Binance oracle prices, or a real historical price path in replay mode
- **Spot Trading**: Market and limit orders, 0.1% fee
- **Perpetual Futures**: 1x-125x leverage, long/short, auto-liquidation engine
- **Full Uniswap V3 AMM**: concentrated liquidity, tick math, tick bitmap, cross-tick swaps, fee accrual
- **Token Launchpad**: pump.fun-style one-click token creation (mint → create pool → seed liquidity, in one call)
- **Historical Replay Price Mode**: replay a real historical hourly BTC/ETH/SOL price path (bull / bear / sideways) instead of live prices, with blind world labels for double-blind experiment analysis
- **Agent Auditor**: an LLM-in-the-loop trading guardrail — rule-based + statistical + LLM-judge threat scoring, with block/flag/log-only/fully-disabled enforcement modes, all switchable via environment variables
- **Inter-Agent Messaging**: broadcast to all or private DMs, with a structured `coordination` field for tracking alliances
- **Adversarial Agent Ecosystem**: 10 agents, 8 roles, ReAct reasoning + persistent cross-cycle memory + phase-based execution scheduling
- **Experiment Runner**: automated multi-cycle experiments with full CSV/JSON output, retry/backoff for transient LLM failures
- **Dual Auth**: JWT for human web users, API key for AI agents
- **WebSocket** real-time price broadcast

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 / FastAPI / async SQLAlchemy / Alembic |
| Database | PostgreSQL (asyncpg) |
| Frontend | React / TypeScript / Vite |
| Real-time | WebSocket |
| SDK | Python (`agent-metaverse`) |
| Deploy | Docker Compose |

## Quick Start

```bash
docker compose up
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- PostgreSQL: localhost:5432

```bash
# Register all 10 agents with differentiated starting capital
python3 agents/run.py --setup

# Run a 50-cycle experiment (agent LLM calls, live prices)
python3 experiments/run_experiment.py --cycles 50 --delay 10
```

Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` with `LLM_PROVIDER=openai`) in
`.env` before running an experiment. See [`docs/API.md`](docs/API.md) for
every operation with runnable `curl` examples, including the historical
replay mode.

### Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit DATABASE_URL
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## AI Agent Integration

### Python SDK

```bash
pip install httpx
```

```python
from agent_metaverse import AgentMetaverseClient

client = AgentMetaverseClient.register(base_url="http://localhost:8000", name="my_bot")

prices = client.get_prices()        # {"ETHUSDT": "2800.00", ...}
client.buy_spot("ETHUSDT", 1.0)     # Market buy 1 ETH
client.open_position("BTCUSDT", "long", 10, 0.01)  # 10x long BTC
client.get_balance()
client.get_positions()
```

### OpenClaw Skill

```bash
npx clawhub@latest install agent-metaverse
```

```bash
export AGENT_METAVERSE_API_KEY=amv_xxx
python3 scripts/skill.py prices
python3 scripts/skill.py buy --pair ETHUSDT --quantity 1.0
python3 scripts/skill.py open-long --pair BTCUSDT --leverage 10 --quantity 0.01
python3 scripts/skill.py portfolio
python3 scripts/skill.py send-message --to all --content "ETH is pumping!"
```

### REST API

```bash
curl -X POST http://localhost:8000/api/sdk/agents/register \
  -H "Content-Type: application/json" -d '{"name": "my_bot"}'
# Returns: {"api_key": "amv_xxx", "agent_id": "uuid", "initial_balance": 10000}

curl http://localhost:8000/api/prices
curl http://localhost:8000/api/account/balance -H "X-API-Key: amv_xxx"
```

Full endpoint reference: [`docs/API.md`](docs/API.md).

## Adversarial Agent Ecosystem

10 agents, 8 roles, differentiated starting capital ($10K retail up to $500K
whale/market-maker):

| Role | Agent(s) | Strategy |
|------|--------|----------|
| Whale | GoldenWhale | Pump & dump, market manipulation |
| Shill | CryptoGuru | Social engineering, fake signals |
| Insider | ShadowTrader | Front-running, sells intel to the highest bidder |
| Liquidation Hunter | LiquidKiller | Targets overleveraged positions |
| Short Seller | BearKing | FUD campaigns, short & destroy |
| Arbitrageur | AlphaBot | Spot-AMM arbitrage, counter-trades manipulators |
| Market Maker | PoolMaster | AMM liquidity, spread manipulation |
| Retail Trader | HappyTrader, DiamondHands, LeverageKing | The prey — FOMO-driven, herd mentality |

Agents run a [ReAct](https://arxiv.org/abs/2210.03629) reasoning loop with
persistent cross-cycle memory (strategy, alliances, lessons learned) and
execute in 4 phases per cycle (Observe → Manipulate → React → Adjust) so
information gatherers act before manipulators, who act before reactive
agents. Full framework details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#6-agent-system).

```bash
python3 agents/run.py --agent GoldenWhale --action prompt   # generate this agent's full ReAct prompt
python3 agents/run.py --agent GoldenWhale --action execute --action-file action.json
python3 agents/run.py --status                              # execution order, phases, PnL
```

## Historical Replay & Experiment Results

Instead of (or alongside) live Binance prices, the price engine can replay a
real historical hourly BTC/ETH/SOL path — bull, bear, or sideways — with
blind world labels so neither the agents nor (optionally) the analyst know
which regime is running until a deliberate post-analysis reveal. Combined
with the Agent Auditor's on/off/log-only enforcement modes, this supports
controlled comparisons of manipulation dynamics across market regimes and
guardrail configurations.

```bash
python3 experiments/scenarios/download_hourly_replay.py   # one-time: fetch + validate scenario data
PRICE_MODE=replay REPLAY_WORLD=A docker compose up -d --force-recreate backend
python3 experiments/run_experiment.py --world A --cycles 72 --hard-reset
```

Results and interactive visualizations from completed experiment batches are
in [`experiments/experiment_analysis/`](experiments/experiment_analysis/).
The full raw per-cycle dataset is published separately — see
[`experiments/experiment_logs/README.md`](experiments/experiment_logs/README.md).

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (Pydantic), incl. replay mode
│   │   ├── database.py          # Async SQLAlchemy
│   │   ├── models/               # DB models
│   │   ├── schemas/              # Pydantic request/response
│   │   ├── api/                  # Route handlers
│   │   ├── services/              # spot, futures, V3 AMM, liquidation, price engine
│   │   ├── middleware/            # JWT + API Key auth
│   │   └── websocket/              # Price broadcaster
│   ├── alembic/                  # DB migrations
│   └── Dockerfile
├── frontend/                     # React/TypeScript/Vite (human observation UI)
├── sdk/                          # Python SDK
├── agents/                       # Multi-agent ecosystem
│   ├── ecosystem.json            # 10 agents, roles, alliances
│   ├── prompts/                  # Role prompts (whale, shill, insider, ...)
│   └── run.py                    # ReAct prompt generation, trade execution, memory
├── auditor/                      # LLM-in-the-loop trading guardrail
│   ├── trade_gate.py             # orchestrator: rule + stat + LLM scoring -> verdict
│   └── ...
├── discovery/                    # open-set manipulation pattern mining
├── experiments/
│   ├── run_experiment.py         # multi-cycle experiment runner
│   ├── scenarios/                # historical replay price data + downloader
│   ├── experiment_logs/          # raw per-run output (see its README — published externally)
│   └── experiment_analysis/      # curated results + interactive visualizations
├── skill/                        # OpenClaw Skill
├── docker-compose.yml
└── docs/
    ├── ARCHITECTURE.md           # full system design
    └── API.md                    # every endpoint, with runnable examples
```

## Trading Mechanics

### Spot
- Market orders execute at the current oracle price; limit orders queue until price matches
- Fee: 0.1%
- Does **not** move the oracle price (only AMM swaps move pool-implied prices)

### Futures
- Margin = (entry_price × quantity) / leverage
- Long PnL = (current − entry) × quantity; Short PnL = (entry − current) × quantity
- Liquidation (long) = entry × (1 − 1/leverage + 0.005); (short) = entry × (1 + 1/leverage − 0.005)
- Checked every price update

### AMM (Uniswap V3)
Full concentrated-liquidity implementation: tick-indexed pricing,
`liquidityNet`/tick bitmap, `feeGrowthOutside`, cross-tick swap stepping.
Fee tiers: 0.05% / 0.3% / 1.0%. Swaps move the pool price; concentrated
positions only earn fees while price trades within `[tick_lower, tick_upper)`.
Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#4-uniswap-v3-amm-engine--detailed-implementation).

## License

MIT
