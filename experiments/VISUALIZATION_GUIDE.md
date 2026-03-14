# Visualization Guide

Comprehensive visualization tools for analyzing AI agent trading experiment results.

## Quick Start

### 1. Install Dependencies

```bash
cd experiments
pip install matplotlib seaborn pandas numpy
```

Or use the provided requirements file:
```bash
pip install -r requirements_visualization.txt
```

### 2. Generate All Standard Figures

```bash
python visualize_results.py experiment_logs/20260313_033128
```

This creates:
- **Figure 1**: Portfolio Performance Over Time
- **Figure 2**: Final Performance Comparison
- **Figure 3**: Message Timeline
- **Figure 4**: Trading Activity
- **Figure 5**: Performance Heatmap

### 3. Generate Behavioral Analysis Figures

```bash
python visualize_behavior.py experiment_logs/20260313_033128
```

This creates:
- **Behavior 1**: Deception Analysis
- **Behavior 2**: Strategy Evolution
- **Behavior 3**: Coordination Network
- **Behavior 4**: Emotional Analysis
- **Behavior 5**: Reasoning Complexity

---

## Output Files

All figures are saved in two formats:
- **PNG** (300 DPI) - for presentations and documents
- **PDF** (vector) - for publication-quality papers

Location: `experiment_logs/TIMESTAMP/visualizations/`

---

## Visualization Scripts

### `visualize_results.py` - Standard Figures

**Purpose**: Generate standard performance and activity metrics

**Figures Created**:

#### Figure 1: Portfolio Performance Over Time
- Line chart showing each agent's balance across all cycles
- Starting balance reference line
- Color-coded by agent role (manipulators vs victims)
- **Use for**: Showing overall experiment outcomes

#### Figure 2: Final Performance Comparison
- Two subplots: Final values and P&L percentage
- Sorted by performance
- Green/red color coding for profit/loss
- **Use for**: Comparing final results, identifying winners/losers

#### Figure 3: Message Timeline
- Two subplots: Message frequency over time, public vs private split
- Shows communication patterns
- **Use for**: Analyzing information flow and coordination

#### Figure 4: Trading Activity
- Bar chart of total trades per agent
- Role annotations
- **Use for**: Comparing active vs passive strategies

#### Figure 5: Performance Heatmap
- Heatmap showing P&L evolution across cycles
- Red/yellow/green color coding
- **Use for**: Identifying critical turning points

**Example**:
```bash
python visualize_results.py experiment_logs/20260313_033128
```

**Output**:
```
📊 Figure 1: Portfolio Performance Over Time...
📊 Figure 2: Final Performance Comparison...
📊 Figure 3: Message Timeline...
📊 Figure 4: Trading Activity...
📊 Figure 5: Performance Heatmap...

✅ All figures generated successfully!
📁 Saved to: experiment_logs/20260313_033128/visualizations

Files created:
  - figure1_portfolio_performance.pdf
  - figure1_portfolio_performance.png
  - figure2_final_performance.pdf
  - figure2_final_performance.png
  ...
```

---

### `visualize_behavior.py` - Behavioral Analysis

**Purpose**: Analyze emergent behaviors, deception, and strategic evolution

**Figures Created**:

#### Behavior 1: Deception Analysis
- Detects discrepancies between private reasoning and public messages
- Timeline of deception events
- Frequency by agent
- **Research value**: Evidence of emergent deception

**How it works**:
- Scans AI reasoning for manipulation keywords (deceive, trick, victim, dump, etc.)
- Scans public messages for positive keywords (patience, learning, support, etc.)
- Flags cycles where both occur (manipulation intent + positive facade)

#### Behavior 2: Strategy Evolution
- Tracks strategy keywords in AI reasoning over time
- Stacked area charts for 4 key agents
- Categories: Accumulation, Pump, Dump, Patience
- **Research value**: Shows strategic phases and adaptation

#### Behavior 3: Coordination Network
- Heatmap of private messages between agents
- Shows who coordinated with whom
- Quantifies collaboration attempts
- **Research value**: Emergent coordination patterns

#### Behavior 4: Emotional Analysis
- Tracks emotional keywords in messages
- Categories: FOMO/Anxiety, Confidence, Regret, Discipline
- Timeline and agent comparison
- **Research value**: Emotional manipulation tactics

#### Behavior 5: Reasoning Complexity
- Measures AI reasoning length over time
- Longer = more complex strategic thinking
- **Research value**: Cognitive load and decision difficulty

**Example**:
```bash
python visualize_behavior.py experiment_logs/20260313_033128
```

---

## Customization

### Using Individual Plot Functions

You can import and use individual plotting functions:

```python
from visualize_results import ExperimentVisualizer

viz = ExperimentVisualizer("experiment_logs/20260313_033128")

# Generate specific figure
viz.plot_portfolio_performance(save=True)

# Or don't save, just display
viz.plot_final_performance_bar(save=False)
```

### Custom Analysis

```python
from visualize_behavior import BehaviorVisualizer

viz = BehaviorVisualizer("experiment_logs/20260313_033128")

# Access loaded data
print(viz.messages_df.head())
print(viz.reasoning_data['GoldenWhale'][0])

# Create custom plots
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
# Your custom analysis here
plt.savefig("custom_figure.png")
```

---

## For Your Research Paper

### Recommended Figure Usage

**Introduction/Background**:
- None (use schematic diagrams)

**Methods**:
- Figure 4: Trading Activity (show agent participation)

**Results**:
- Figure 1: Portfolio Performance (main results)
- Figure 2: Final Performance (summary)
- Behavior 1: Deception Analysis (emergent behavior)
- Behavior 2: Strategy Evolution (adaptation)

**Discussion**:
- Figure 3: Message Timeline (communication patterns)
- Behavior 3: Coordination Network (coordination evidence)
- Behavior 4: Emotional Analysis (manipulation tactics)

**Supplementary Materials**:
- Figure 5: Performance Heatmap
- Behavior 5: Reasoning Complexity

### Figure Captions (Templates)

**Figure 1**:
> Portfolio performance over 50 trading cycles for 5 AI agents. GoldenWhale and CryptoGuru (manipulators, red/orange) attempted pump-and-dump schemes but lost money to trading fees. Retail agents (HappyTrader, DiamondHands, LeverageKing, blue/green/purple) showed varying degrees of discipline, with DiamondHands and LeverageKing maintaining exact starting balance through complete inactivity.

**Behavior 1**:
> Deception events detected by comparing private AI reasoning (containing manipulation keywords) with public messages (containing positive/supportive language). GoldenWhale and CryptoGuru showed frequent deceptive messaging, maintaining a "reformed trader" public persona while privately planning manipulation. Each point represents a cycle where deception was detected.

---

## Troubleshooting

### "No module named 'seaborn'"
```bash
pip install seaborn
```

### "FileNotFoundError: portfolio_performance.csv"
You need to run the analysis script first:
```bash
python analyze_results.py experiment_logs/20260313_033128 --export
```

### Figures too small/large
Edit the scripts and change `figsize` parameters:
```python
fig, ax = plt.subplots(figsize=(12, 8))  # width, height in inches
```

### Want different colors
Edit the `agent_colors` dictionary in `visualize_results.py`:
```python
self.agent_colors = {
    'GoldenWhale': '#your_hex_color',
    'CryptoGuru': '#another_color',
    # ...
}
```

### PDF fonts look weird
Install LaTeX support for matplotlib:
```bash
# macOS
brew install texlive

# Ubuntu/Debian
sudo apt-get install texlive texlive-latex-extra
```

Then in the script:
```python
plt.rcParams['text.usetex'] = True
```

---

## Advanced Usage

### Batch Process Multiple Experiments

```bash
#!/bin/bash
for exp in experiment_logs/*/; do
    echo "Processing $exp..."
    python visualize_results.py "$exp"
    python visualize_behavior.py "$exp"
done
```

### Compare Multiple Experiments

```python
from visualize_results import ExperimentVisualizer

exp1 = ExperimentVisualizer("experiment_logs/20260313_033128")
exp2 = ExperimentVisualizer("experiment_logs/20260314_120000")

# Plot both on same axes
fig, ax = plt.subplots()
for agent in exp1.portfolio_df.columns[1:]:
    ax.plot(exp1.portfolio_df['cycle'], exp1.portfolio_df[agent],
            label=f"Exp1-{agent}", linestyle='-')
    ax.plot(exp2.portfolio_df['cycle'], exp2.portfolio_df[agent],
            label=f"Exp2-{agent}", linestyle='--')
plt.legend()
plt.show()
```

---

## Example Workflow

### Complete Paper Figures

```bash
# 1. Make sure CSV files exist
python analyze_results.py experiment_logs/20260313_033128 --export

# 2. Generate all standard figures
python visualize_results.py experiment_logs/20260313_033128

# 3. Generate behavioral analysis
python visualize_behavior.py experiment_logs/20260313_033128

# 4. Check output
ls experiment_logs/20260313_033128/visualizations/

# 5. Copy to paper directory
cp experiment_logs/20260313_033128/visualizations/*.pdf ~/Documents/paper/figures/
```

---

## File Organization

```
experiments/
├── visualize_results.py           # Standard performance figures
├── visualize_behavior.py          # Behavioral analysis figures
├── requirements_visualization.txt # Python dependencies
├── VISUALIZATION_GUIDE.md         # This file
└── experiment_logs/
    └── 20260313_033128/
        ├── visualizations/        # ← Generated figures go here
        │   ├── figure1_portfolio_performance.png
        │   ├── figure1_portfolio_performance.pdf
        │   ├── behavior1_deception_analysis.png
        │   └── ...
        ├── portfolio_performance.csv
        ├── messages.csv
        └── actions/
```

---

## Citation

If you use these visualization scripts in your research, please cite:

```bibtex
@software{agent_trading_viz,
  title={AI Agent Trading Experiment Visualization Tools},
  author={Su, Yiyun and Claude Sonnet 4.5},
  year={2026},
  url={https://github.com/Ed1sonL1-byte/virtual_exchange}
}
```

---

## Support

For issues or questions:
1. Check this guide
2. Review script comments
3. Open an issue on GitHub
4. Contact: ysu@axon.com

---

**Happy Visualizing!** 📊📈🎨
