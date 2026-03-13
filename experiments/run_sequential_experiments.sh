#!/bin/bash
# Sequential experiment runner: 10 cycles (test) → 50 cycles (main)

set -e

# Set your API key before running:
# export ANTHROPIC_API_KEY="your-key-here"
API_KEY="${ANTHROPIC_API_KEY:-}"
PYTHON="venv_experiment/bin/python3"

if [ -z "$API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable not set"
    echo "Please set it with: export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

echo "========================================"
echo "Sequential Experiment Runner"
echo "========================================"
echo ""

# Wait for current 10-cycle experiment to complete
echo "Waiting for 10-cycle experiment to complete..."
LOG_DIR_10=$(ls -t experiment_logs/ | head -1)
echo "Monitoring: experiment_logs/$LOG_DIR_10"

while true; do
    # Count status files (completed cycles)
    COMPLETED=$(ls experiment_logs/$LOG_DIR_10/status/ 2>/dev/null | wc -l | xargs)

    # Check if process is still running
    RUNNING=$(ps aux | grep "run_experiment.py --cycles 10" | grep -v grep | wc -l | xargs)

    echo -ne "\rCycles completed: $COMPLETED/10 | Process running: $RUNNING"

    if [ "$COMPLETED" -eq 10 ] || [ "$RUNNING" -eq 0 ]; then
        echo ""
        echo "10-cycle experiment complete!"
        break
    fi

    sleep 10
done

echo ""
echo "========================================"
echo "Starting 50-cycle experiment..."
echo "========================================"
echo ""
echo "Settings:"
echo "  - Model: Claude Sonnet 4.5"
echo "  - Cycles: 50"
echo "  - Agents: GoldenWhale, CryptoGuru, HappyTrader, DiamondHands, LeverageKing"
echo "  - Estimated time: ~2 hours"
echo "  - Estimated cost: ~$7.50"
echo ""
echo "Starting in 5 seconds..."
sleep 5

# Run 50-cycle experiment
ANTHROPIC_API_KEY="$API_KEY" $PYTHON run_experiment.py --cycles 50 --yes

echo ""
echo "========================================"
echo "50-cycle experiment complete!"
echo "========================================"

# Show latest log directory
LOG_DIR_50=$(ls -t experiment_logs/ | head -1)
echo ""
echo "Results saved to: experiment_logs/$LOG_DIR_50"
echo ""
echo "Next steps:"
echo "  1. Analyze results:"
echo "     $PYTHON analyze_results.py experiment_logs/$LOG_DIR_50"
echo ""
echo "  2. Export to CSV:"
echo "     $PYTHON analyze_results.py experiment_logs/$LOG_DIR_50 --export"
echo ""
