#!/bin/bash
# Test script for visualization

echo "=========================================="
echo "Visualization Test Script"
echo "=========================================="
echo ""

# Check if experiment directory exists
EXP_DIR=${1:-"experiment_logs/20260313_033128"}

if [ ! -d "$EXP_DIR" ]; then
    echo "Error: Experiment directory not found: $EXP_DIR"
    exit 1
fi

echo "Experiment directory: $EXP_DIR"
echo ""

# Check required files
echo "Checking required files..."
REQUIRED_FILES=("portfolio_performance.csv" "messages.csv" "config.json")

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$EXP_DIR/$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file (missing)"
        echo ""
        echo "Please run: python analyze_results.py $EXP_DIR --export"
        exit 1
    fi
done

echo ""
echo "Checking Python packages..."

# Check for required packages
python3 -c "import matplotlib; import seaborn; import pandas; import numpy" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ All required packages installed"
else
    echo "  ✗ Missing packages"
    echo ""
    echo "Please install:"
    echo "  pip install matplotlib seaborn pandas numpy"
    echo ""
    echo "Or:"
    echo "  pip install -r requirements_visualization.txt"
    exit 1
fi

echo ""
echo "=========================================="
echo "All checks passed!"
echo "=========================================="
echo ""
echo "Run visualizations:"
echo "  python visualize_results.py $EXP_DIR"
echo "  python visualize_behavior.py $EXP_DIR"
echo ""
