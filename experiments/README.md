# Experiments Directory

Scripts, data, and analysis tools for adversarial multi-agent trading experiments.

## Architecture

Experiments use the ReAct (Observe→Think→Plan→Act) agent framework with persistent memory, phase-based execution scheduling, and Uniswap V3 AMM + Pump.fun token launchpad.

See [../EXPERIMENT_GUIDE.md](../EXPERIMENT_GUIDE.md) for the full setup and architecture documentation.

## Directory Structure

```
experiments/
├── run_experiment.py               # Main experiment runner (ReAct + memory + scheduling)
├── analyze_results.py              # Post-experiment analysis
├── visualize_results.py            # Portfolio performance figures
├── visualize_behavior.py           # Behavioral analysis figures
├── setup_experiment.sh             # One-command setup
├── run_sequential_experiments.sh   # Run multiple experiments back-to-back
├── requirements_experiment.txt     # Python dependencies
├── requirements_visualization.txt  # Visualization dependencies
├── VISUALIZATION_GUIDE.md          # Figure generation guide
├── test_*.py                       # Model testing scripts
└── experiment_logs/                # Timestamped experiment data
    └── YYYYMMDD_HHMMSS/
        ├── config.json             # Experiment config (agents, model, phases)
        ├── portfolio_performance.csv  # Per-cycle portfolio values
        ├── messages.csv            # All messages with phase + coordination info
        ├── prompts/                # Full ReAct prompts sent to LLM
        ├── actions/                # Raw + parsed LLM responses
        ├── status/                 # Per-cycle market snapshots (JSON)
        ├── errors/                 # Error logs
        └── visualizations/         # Generated figures (PNG & PDF)
```

## Quick Start

```bash
# 1. Ensure backend is running
docker-compose up -d
curl http://localhost:8000/health

# 2. Register agents (with differentiated balances)
python3 agents/run.py --setup

# 3. Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Run experiment
python3 experiments/run_experiment.py --cycles 50 --delay 10 -y

# 5. Analyze
python3 experiments/analyze_results.py experiments/experiment_logs/YYYYMMDD_HHMMSS
python3 experiments/visualize_results.py experiments/experiment_logs/YYYYMMDD_HHMMSS
```

## Agent Ecosystem (10 agents, 4 phases)

| Phase | Agent | Role | Capital |
|-------|-------|------|---------|
| 1 Observe | ShadowTrader | insider | $50K |
| 1 Observe | AlphaBot | arbitrageur | $50K |
| 2 Manipulate | GoldenWhale | whale | $500K |
| 2 Manipulate | CryptoGuru | shill | $20K |
| 2 Manipulate | BearKing | short_seller | $50K |
| 3 React | HappyTrader | retail | $10K |
| 3 React | DiamondHands | retail | $10K |
| 3 React | LeverageKing | retail | $10K |
| 3 React | LiquidKiller | liquidation_hunter | $50K |
| 4 Adjust | PoolMaster | market_maker | $500K |

Total ecosystem capital: $1,230,000 USDT. Whale-to-retail ratio: 50:1.

## Completed Experiments

### Experiment 1: 20260313_033128 (Baseline)
- **Setup**: 5 agents, 50 cycles, Claude Sonnet 4.5, all $10K, no V3, no memory
- **Duration**: 10.31 hours
- **Result**: All agents lost money. Moral regression within 10 cycles.
- **Key findings**: Coalition formation, multi-layer deception, inaction equilibrium
- **Issues**: Zero price volatility, no memory, equal capital

### Experiment 2: (Planned)
- **Setup**: 10 agents, 100 cycles, differentiated capital, V3 AMM, ReAct + memory
- **Expected**: Successful pump & dump via meme tokens, coalition vs manipulation dynamics

## Key CLI Commands

```bash
# Run experiment
python3 experiments/run_experiment.py --cycles 50 --delay 10

# Run with specific agents
python3 experiments/run_experiment.py --cycles 50 --agents "GoldenWhale,CryptoGuru,HappyTrader"

# Resume interrupted experiment
python3 experiments/run_experiment.py --resume experiments/experiment_logs/YYYYMMDD_HHMMSS

# Don't reset memories (continue from previous state)
python3 experiments/run_experiment.py --cycles 20 --no-reset

# Use OpenAI
python3 experiments/run_experiment.py --provider openai --model gpt-4o

# Check agent status and memory
python3 agents/run.py --status
python3 agents/run.py --agent GoldenWhale --action memory

# Reset memories for fresh start
python3 agents/run.py --reset-memory
```

## Cost Estimates

| Cycles | Agents | LLM Calls | Time (~10s delay) | Cost (Sonnet) |
|--------|--------|-----------|-------------------|---------------|
| 10 | 5 | 50 | ~8min | ~$0.75 |
| 50 | 10 | 500 | ~80min | ~$7.50 |
| 100 | 10 | 1000 | ~2.5h | ~$15.00 |
