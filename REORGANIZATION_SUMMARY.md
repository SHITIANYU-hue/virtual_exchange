# 📁 Experiments Folder Reorganization Complete

## What Was Done

All experiment-related files have been consolidated into a single `experiments/` directory for better organization.

## New Directory Structure

```
virtual_exchange/
├── experiments/              # ← NEW: All experimental data and scripts
│   ├── experiment_logs/      # All experimental runs (69 MB total)
│   │   └── 20260313_033128/  # Main 50-cycle run (19 MB, 553 files)
│   │       ├── actions/      # 246 AI decision JSONs
│   │       ├── prompts/      # 246 context files
│   │       ├── status/       # 50 market snapshots
│   │       ├── errors/       # Error logs
│   │       ├── config.json
│   │       ├── portfolio_performance.csv
│   │       └── messages.csv
│   ├── run_experiment.py
│   ├── analyze_results.py
│   ├── setup_experiment.sh
│   ├── run_sequential_experiments.sh
│   ├── sequential_experiment.log
│   ├── requirements_experiment.txt
│   ├── venv_experiment/
│   ├── test_model.py
│   ├── test_model2.py
│   ├── test_sonnet45.py
│   └── README.md             # ← NEW: Complete documentation
│
├── agents/                   # Agent system (unchanged)
├── backend/                  # FastAPI backend (unchanged)
├── frontend/                 # React frontend (unchanged)
├── docs/                     # Documentation (unchanged)
├── sdk/                      # SDK (unchanged)
├── skill/                    # Skills (unchanged)
├── EXPERIMENT_GUIDE.md       # Guide (unchanged)
├── README.md                 # Main readme (unchanged)
└── docker-compose.yml        # Docker config (unchanged)
```

## Files Moved to `experiments/`

### Scripts (5 files)
- ✅ `run_experiment.py` - Main experiment runner
- ✅ `analyze_results.py` - Analysis script
- ✅ `setup_experiment.sh` - Setup script
- ✅ `run_sequential_experiments.sh` - Sequential runner
- ✅ `test_model.py`, `test_model2.py`, `test_sonnet45.py` - Test scripts

### Data (1 directory)
- ✅ `experiment_logs/` - All experimental runs
  - 10 total runs (test + production)
  - Main run: 20260313_033128 (50 cycles, 19 MB)

### Configuration (1 file)
- ✅ `requirements_experiment.txt` - Python dependencies

### Virtual Environment (1 directory)
- ✅ `venv_experiment/` - Python virtual environment

### Logs (1 file)
- ✅ `sequential_experiment.log` - Sequential run log (116 KB)

### Documentation (1 new file)
- ✅ `experiments/README.md` - Complete experiments documentation

## Updated Paths

### To Run Experiments
```bash
# OLD
python3 run_experiment.py --cycles 50

# NEW
cd experiments
python3 run_experiment.py --cycles 50
```

### To Analyze Results
```bash
# OLD
python3 analyze_results.py experiment_logs/20260313_033128

# NEW
cd experiments
python3 analyze_results.py experiment_logs/20260313_033128
```

### To Setup
```bash
# OLD
./setup_experiment.sh

# NEW
cd experiments
./setup_experiment.sh
```

## Benefits of This Organization

1. **Clear Separation**: Experiments isolated from main system
2. **Easy Navigation**: All related files in one place
3. **Better Documentation**: Dedicated README in experiments folder
4. **Scalability**: Easy to add more experiments
5. **Clean Main Directory**: Less clutter in virtual_exchange root

## Main Experiment Data Summary

**Run ID**: 20260313_033128
**Size**: 19 MB (553 files)
**Contents**:
- 246 AI decision JSONs with reasoning
- 246 prompt files showing context
- 50 market snapshots
- 247 messages (CSV)
- Portfolio performance timeline (CSV)
- 4 error logs

**Key Results**:
- Duration: 10.31 hours
- Agents: 5 (GoldenWhale, CryptoGuru, HappyTrader, DiamondHands, LeverageKing)
- Total Trades: 15
- Total Messages: 247
- Emergent behaviors: Victim coalition, multi-layer deception, failed manipulation

## Next Steps

1. **Run More Experiments**:
   ```bash
   cd experiments
   python3 run_experiment.py --cycles 100
   ```

2. **Analyze Main Run**:
   ```bash
   cd experiments
   python3 analyze_results.py experiment_logs/20260313_033128 --export
   ```

3. **Visualize Results**:
   - Use `portfolio_performance.csv` in Excel/Python
   - Use `messages.csv` for timeline visualization

4. **Write Paper**:
   - Extract quotes from `actions/*.json`
   - Plot performance from CSVs
   - Cite behavioral patterns

---

**Total Storage**: 69 MB for all experiments
**Organization Date**: March 13, 2026
**Status**: ✅ Complete and Ready for Research
