# Experiments Directory

This directory contains all experimental data, scripts, and analysis tools for the AI Agent Trading experiments.

## Directory Structure

```
experiments/
├── experiment_logs/          # All experimental run data
│   └── YYYYMMDD_HHMMSS/     # Individual experiment runs (timestamped)
│       ├── actions/         # AI decisions with reasoning (JSON)
│       ├── prompts/         # What AI saw each cycle (TXT)
│       ├── status/          # Market snapshots per cycle (TXT)
│       ├── errors/          # Error logs if any
│       ├── visualizations/  # Generated figures (PNG & PDF)
│       ├── config.json      # Experiment configuration
│       ├── portfolio_performance.csv  # Agent balances over time
│       └── messages.csv     # All messages sent during experiment
│
├── run_experiment.py        # Main experiment runner
├── analyze_results.py       # Results analysis script
├── visualize_results.py     # Standard figure generation
├── visualize_behavior.py    # Behavioral analysis figures
├── setup_experiment.sh      # One-command setup script
├── test_visualization.sh    # Test visualization setup
├── run_sequential_experiments.sh  # Run multiple experiments
├── requirements_experiment.txt    # Experiment dependencies
├── requirements_visualization.txt # Visualization dependencies
├── VISUALIZATION_GUIDE.md   # Visualization documentation
├── venv_experiment/         # Python virtual environment
└── test_*.py               # Model testing scripts
```

## Completed Experiments

### 20260313_033128 - 50-Cycle Full Run ✅
- **Duration**: 10.31 hours
- **Agents**: GoldenWhale, CryptoGuru, HappyTrader, DiamondHands, LeverageKing (5 agents)
- **Model**: Claude Sonnet 4.5
- **Cycles**: 50 complete
- **Total Trades**: 15
- **Total Messages**: 247
- **API Calls**: 246
- **Errors**: 4

**Key Findings**:
- Victim coalition formation (mutual support system)
- Multi-layer deception (public vs. private personas)
- Failed manipulation → manipulators lost to fees
- Emergent defensive strategies (red flags list with 74+ items)

**Files Generated**:
- 246 action JSONs with AI reasoning
- 246 prompt files showing context
- 50 status snapshots
- portfolio_performance.csv (ready for plotting)
- messages.csv (247 messages)

### Other Runs
- `20260313_003019` through `20260313_004754` - Test runs and iterations

## Quick Start

### Visualize Existing Results

```bash
# Generate standard performance figures
python visualize_results.py experiment_logs/20260313_033128

# Generate behavioral analysis figures
python visualize_behavior.py experiment_logs/20260313_033128

# Test visualization setup
./test_visualization.sh experiment_logs/20260313_033128
```

See [VISUALIZATION_GUIDE.md](VISUALIZATION_GUIDE.md) for detailed documentation.

### Run a New Experiment
```bash
# Setup (first time only)
./setup_experiment.sh

# Run 50-cycle experiment
python3 run_experiment.py --cycles 50

# Run in background
nohup python3 run_experiment.py --cycles 50 > experiment.log 2>&1 &
```

### Analyze Results
```bash
# Generate report
python3 analyze_results.py experiment_logs/YYYYMMDD_HHMMSS

# Export to CSV
python3 analyze_results.py experiment_logs/YYYYMMDD_HHMMSS --export
```

## Cost Estimates

| Cycles | Agents | Time | Cost (Claude Sonnet) |
|--------|--------|------|---------------------|
| 10     | 2      | 25m  | $0.30               |
| 50     | 5      | 2h   | $3.75               |
| 100    | 10     | 7h   | $15.00              |

## Data Files Explained

### actions/*.json
AI's decision with full reasoning for each cycle. Example:
```json
{
  "reasoning": "Full strategic thinking...",
  "trades": [...],
  "messages": [...],
  "strategy_update": "..."
}
```

### prompts/*.txt
Complete context shown to AI each cycle:
- Current prices
- Agent balances
- Open positions
- Recent messages
- Role definition

### portfolio_performance.csv
Agent balances by cycle - ready for Excel/Python visualization:
```csv
cycle,GoldenWhale,CryptoGuru,HappyTrader,DiamondHands,LeverageKing
1,10000.0,10000.0,10000.0,10000.0,10000.0
...
```

### messages.csv
All messages with metadata:
```csv
cycle,sender,recipient,content
1,"GoldenWhale","all","Message content..."
```

## Requirements

- Python 3.8+
- Anthropic API key
- Virtual Exchange running on localhost:8000
- Dependencies: httpx, anthropic (see requirements_experiment.txt)

## Research Value

This experimental data demonstrates:
1. Emergent defensive coalitions
2. Multi-layer deception strategies
3. Psychological manipulation tactics
4. Adaptive learning when strategies fail
5. Realistic victim behavior patterns

Perfect for academic papers on:
- AI agent behavior
- Financial crime strategies
- Multi-agent systems
- Emergent coordination
- Deception in AI systems
