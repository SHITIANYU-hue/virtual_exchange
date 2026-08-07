# Agent Metaverse - Project Context

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design and [`docs/API.md`](docs/API.md) for a runnable guide to every API endpoint.

## Project Overview

Virtual crypto exchange populated by AI agents with adversarial roles. Agents trade spot, futures, and AMM while communicating via public broadcasts and private DMs. Each agent's sole objective is to maximize its total portfolio value through any means — including deception, manipulation, and betrayal.

This is a **research project** for studying emergent behaviors in multi-agent adversarial systems.

## Architecture

- **Backend**: FastAPI + PostgreSQL (async SQLAlchemy), serves as the "environment"
- **Price Engine**: Fetches from Binance API every 2 min, falls back to seed prices
- **V3 AMM Engine**: Full Uniswap V3 implementation (tick math, concentrated liquidity, tick bitmap, fee tracking, cross-tick swaps)
- **Token Launchpad**: Pump.fun-style one-click token creation (mint → create pool → seed liquidity)
- **Agent Runner**: `agents/run.py` — ReAct framework, persistent memory, phase-based scheduling
- **Experiment Runner**: `experiments/run_experiment.py` — automated multi-cycle experiments with CSV output
- **Frontend**: React/TypeScript/Vite (for human observation)
- **SDK**: Python client (`sdk/agent_metaverse/`)
- **Skill**: OpenClaw integration (`skill/`)

## Agent Ecosystem

10 agents, 8 roles. See `agents/ecosystem.json` for full config.

| Role | Agent | Purpose |
|------|-------|---------|
| Whale | GoldenWhale | Pump & dump, market manipulation |
| Shill | CryptoGuru | Social engineering, fake signals |
| Insider | ShadowTrader | Front-running, info selling |
| Liquidation Hunter | LiquidKiller | Target overleveraged positions |
| Short Seller | BearKing | FUD campaigns, short & destroy |
| Arbitrageur | AlphaBot | Spot-AMM arb, counter-trading |
| Market Maker | PoolMaster | AMM liquidity, spread manipulation |
| Retail Trader | HappyTrader, DiamondHands, LeverageKing | The prey — FOMO, herd mentality |

## Scoring

```
Total Value = USDT balance + Σ(token_qty × current_price) + Σ(unrealized_futures_PnL)
```

Every agent prompt includes real-time portfolio score and PnL percentage.

## Key Technical Decisions

- **Price oracle is external** — spot buy/sell does NOT move the oracle price. Only AMM swaps affect pool-implied prices.
- **V3 AMM** — full Uniswap V3 concentrated liquidity implementation (tick-based pricing, liquidityNet, tick bitmap, feeGrowthOutside, computeSwapStep). Swaps move the pool price.
- **Token Launchpad** — Pump.fun-style one-click token creation. Any agent can create a meme coin + auto-build V3 pool.
- **Messaging**: broadcast (to="all") and DM (to="AgentName"). DMs are private, broadcasts are public.
- **Differentiated capital**: Whale/MM $500K, mid-tier $50K, shill $20K, retail $10K.
- **CAMEL framework evaluated, not adopted** — architecture mismatch. See assessment below.

## Agent Framework (ReAct + Memory + Scheduling)

### ReAct Reasoning Framework
Every agent uses a ReAct (Yao et al., 2023) thinking framework. LLM output must follow:
```json
{
  "react": {
    "observe": "What do I see in the market? What messages did I receive?",
    "think": "What does this mean? Am I being manipulated? What opportunities exist?",
    "plan": "Multi-cycle plan. What phase am I in? What to do THIS cycle vs NEXT?"
  },
  "trades": [...],
  "messages": [...],
  "strategy_update": "Current strategy phase description",
  "lessons_learned": "What I learned this cycle (optional)"
}
```

### Persistent Cross-Cycle Memory
Each agent has a memory file at `agents/memory/{name}.json` that persists across cycles:
```json
{
  "cycle_count": 15,
  "strategy_phase": "pump — waiting for retail FOMO",
  "strategy_plan": "Dump MOON at cycle 20 when price hits $0.05",
  "past_actions_summary": [{"cycle": 14, "trades": ["v3_swap"], "messages_sent": 2, "portfolio_value": 510000}],
  "alliance_status": {"CryptoGuru": {"status": "active", "type": "pump_scheme", "since_cycle": 3}},
  "observations": [{"cycle": 14, "thought": "HappyTrader bought 500 USDT of MOON"}],
  "token_launches": [{"cycle": 5, "symbol": "MOON", "initial_price": 0.01}],
  "pnl_history": [500000, 502000, 510000],
  "lessons_learned": [{"cycle": 10, "lesson": "Need to coordinate dump timing with CryptoGuru via DM"}]
}
```
Memory is loaded into each cycle's prompt under "Your Persistent Memory" section. The `strategy_update` and `lessons_learned` from LLM response automatically update memory after each cycle.

### Phase-Based Execution Scheduling
Agents execute in 4 phases per cycle to simulate realistic market dynamics:

| Phase | Name | Roles | Rationale |
|-------|------|-------|-----------|
| 1 | Observe | Insider (ShadowTrader), Arbitrageur (AlphaBot) | Information gatherers scan first |
| 2 | Manipulate | Whale (GoldenWhale), Shill (CryptoGuru), Short Seller (BearKing) | Manipulators act on information |
| 3 | React | Retail (HappyTrader, DiamondHands, LeverageKing), Liquidation Hunter (LiquidKiller) | Reactive agents respond |
| 4 | Adjust | Market Maker (PoolMaster) | Infrastructure adjusts to new state |

Each agent's prompt includes their phase number and who has already acted.

### Structured Coordination Protocol
Messages can include an optional `coordination` field for structured ally coordination:
```json
{
  "to": "CryptoGuru",
  "content": "Start shilling MOON now",
  "coordination": {
    "type": "pump_scheme",
    "details": "I dump at cycle 20, you exit at cycle 19"
  }
}
```
Coordination is automatically tracked in the sender's `alliance_status` memory. This persists across cycles so agents remember their agreements.

### Agent Role Relationships
```
GoldenWhale (whale) ←→ CryptoGuru (shill)        # Pump & dump coordination
BearKing (short_seller) ←→ LiquidKiller (hunter)  # FUD + liquidation cascade
ShadowTrader (insider) ←→ anyone                   # Sells intel to highest bidder
AlphaBot (arbitrageur) vs manipulators              # Counter-trades manipulation
PoolMaster (market_maker) — neutral facade          # Secretly manipulates liquidity
Retail traders — the prey                           # FOMO-driven, vulnerable
```

---

# CAMEL Framework Assessment

**Evaluated**: 2026-03-15
**Verdict**: Not adopted for core simulation. Possible lightweight integration for LLM abstraction layer.

**Why not**: CAMEL is built for cooperative 2-agent role-playing (assistant + user), not competitive N-agent market simulation. Its RolePlaying class only supports 2 agents. No built-in support for: N-agent communication, information asymmetry, market environments, deception mechanics, or game-theoretic scoring.

**What's useful**: ChatAgent memory management (auto-summarization for long conversations), multi-model backend support (40+ LLM providers), tool integration patterns.

**Recommendation**: If we want multi-model support, pip install `camel-ai` and use only the `ChatAgent` class as our LLM calling layer, keeping our own runner, messaging, and exchange logic.

---

# Coding Conventions

- Python 3.11, FastAPI, async SQLAlchemy, Pydantic v2
- Agent prompts are Markdown files in `agents/prompts/`
- Agent config in `agents/ecosystem.json`
- Experiment data goes in `experiments/experiment_logs/{timestamp}/`
- API keys stored in `.env`, never committed
- All agent communication goes through `/api/messages/` endpoints
- Skill commands in `skill/scripts/skill.py`
