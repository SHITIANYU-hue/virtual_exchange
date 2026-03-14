#!/usr/bin/env python3
"""
Visualization script for AI Agent Trading Experiments
Creates publication-quality figures from experimental data
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
from pathlib import Path
from datetime import datetime
import numpy as np

# Set style for publication-quality figures
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10


class ExperimentVisualizer:
    def __init__(self, experiment_dir):
        """
        Initialize visualizer with experiment directory

        Args:
            experiment_dir: Path to experiment_logs/TIMESTAMP directory
        """
        self.exp_dir = Path(experiment_dir)
        self.output_dir = self.exp_dir / "visualizations"
        self.output_dir.mkdir(exist_ok=True)

        # Load data
        self.portfolio_df = pd.read_csv(self.exp_dir / "portfolio_performance.csv")
        self.messages_df = pd.read_csv(self.exp_dir / "messages.csv")
        self.config = self._load_config()

        # Agent role mapping
        self.agent_roles = {
            'GoldenWhale': 'Manipulator (Whale)',
            'CryptoGuru': 'Manipulator (Shill)',
            'HappyTrader': 'Victim (Retail)',
            'DiamondHands': 'Victim (Retail)',
            'LeverageKing': 'Victim (Retail)',
            'ShadowTrader': 'Insider',
            'LiquidKiller': 'Liquidation Hunter',
            'BearKing': 'Short Seller',
            'AlphaBot': 'Arbitrageur',
            'PoolMaster': 'Market Maker'
        }

        # Color scheme for agents
        self.agent_colors = {
            'GoldenWhale': '#e74c3c',  # Red
            'CryptoGuru': '#e67e22',   # Orange
            'HappyTrader': '#3498db',  # Blue
            'DiamondHands': '#2ecc71', # Green
            'LeverageKing': '#9b59b6'  # Purple
        }

    def _load_config(self):
        """Load experiment configuration"""
        try:
            with open(self.exp_dir / "config.json") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def plot_portfolio_performance(self, save=True):
        """
        Figure 1: Portfolio Performance Over Time
        Line chart showing each agent's balance across cycles
        """
        fig, ax = plt.subplots(figsize=(14, 8))

        # Get agent columns (all except 'cycle')
        agents = [col for col in self.portfolio_df.columns if col != 'cycle']

        for agent in agents:
            color = self.agent_colors.get(agent, None)
            label = f"{agent} ({self.agent_roles.get(agent, 'Unknown')})"
            ax.plot(self.portfolio_df['cycle'],
                   self.portfolio_df[agent],
                   marker='o',
                   markersize=3,
                   linewidth=2,
                   label=label,
                   color=color,
                   alpha=0.8)

        # Add horizontal line at starting balance
        ax.axhline(y=10000, color='gray', linestyle='--', alpha=0.5, label='Starting Balance ($10,000)')

        ax.set_xlabel('Cycle', fontweight='bold')
        ax.set_ylabel('Portfolio Value (USDT)', fontweight='bold')
        ax.set_title('Portfolio Performance Over 50 Trading Cycles', fontweight='bold', fontsize=16)
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3)

        # Add experiment info
        info_text = f"Model: {self.config.get('llm_model', 'Unknown')}\nCycles: {self.config.get('num_cycles', 'N/A')}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
               verticalalignment='top', fontsize=9, alpha=0.7,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()
        if save:
            plt.savefig(self.output_dir / "figure1_portfolio_performance.png", dpi=300, bbox_inches='tight')
            plt.savefig(self.output_dir / "figure1_portfolio_performance.pdf", bbox_inches='tight')
        plt.show()

        return fig

    def plot_final_performance_bar(self, save=True):
        """
        Figure 2: Final Performance Comparison
        Bar chart showing final portfolio values and P&L
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Get final values
        final_values = self.portfolio_df.iloc[-1].drop('cycle')
        agents = final_values.index.tolist()

        # Calculate P&L
        pnl = final_values - 10000
        pnl_pct = (pnl / 10000) * 100

        # Sort by final value
        sorted_idx = final_values.sort_values(ascending=False).index

        # Plot 1: Final Portfolio Values
        colors = [self.agent_colors.get(agent, '#95a5a6') for agent in sorted_idx]
        bars1 = ax1.bar(range(len(sorted_idx)),
                        final_values[sorted_idx],
                        color=colors,
                        alpha=0.7,
                        edgecolor='black')

        ax1.axhline(y=10000, color='red', linestyle='--', alpha=0.5, label='Starting Balance')
        ax1.set_xlabel('Agent', fontweight='bold')
        ax1.set_ylabel('Final Portfolio Value (USDT)', fontweight='bold')
        ax1.set_title('Final Portfolio Values', fontweight='bold', fontsize=14)
        ax1.set_xticks(range(len(sorted_idx)))
        ax1.set_xticklabels(sorted_idx, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='y')

        # Add value labels on bars
        for i, bar in enumerate(bars1):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'${height:.2f}',
                    ha='center', va='bottom', fontsize=9)

        # Plot 2: Profit & Loss Percentage
        colors_pnl = ['green' if x > 0 else 'red' if x < 0 else 'gray' for x in pnl_pct[sorted_idx]]
        bars2 = ax2.bar(range(len(sorted_idx)),
                        pnl_pct[sorted_idx],
                        color=colors_pnl,
                        alpha=0.7,
                        edgecolor='black')

        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.set_xlabel('Agent', fontweight='bold')
        ax2.set_ylabel('Profit/Loss (%)', fontweight='bold')
        ax2.set_title('Profit & Loss Percentage', fontweight='bold', fontsize=14)
        ax2.set_xticks(range(len(sorted_idx)))
        ax2.set_xticklabels(sorted_idx, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3, axis='y')

        # Add percentage labels
        for i, bar in enumerate(bars2):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}%',
                    ha='center', va='bottom' if height > 0 else 'top', fontsize=9)

        plt.tight_layout()
        if save:
            plt.savefig(self.output_dir / "figure2_final_performance.png", dpi=300, bbox_inches='tight')
            plt.savefig(self.output_dir / "figure2_final_performance.pdf", bbox_inches='tight')
        plt.show()

        return fig

    def plot_message_timeline(self, save=True):
        """
        Figure 3: Message Timeline
        Shows message frequency and public vs. private messaging patterns
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Count messages per cycle per agent
        msg_counts = self.messages_df.groupby(['cycle', 'sender']).size().unstack(fill_value=0)

        # Plot 1: Message frequency over time
        for agent in msg_counts.columns:
            color = self.agent_colors.get(agent, None)
            ax1.plot(msg_counts.index, msg_counts[agent],
                    marker='o', markersize=4, linewidth=2,
                    label=agent, color=color, alpha=0.8)

        ax1.set_xlabel('Cycle', fontweight='bold')
        ax1.set_ylabel('Number of Messages', fontweight='bold')
        ax1.set_title('Message Frequency Over Time', fontweight='bold', fontsize=14)
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)

        # Plot 2: Public vs Private messages
        public_msgs = self.messages_df[self.messages_df['recipient'] == 'all'].groupby('sender').size()
        private_msgs = self.messages_df[self.messages_df['recipient'] != 'all'].groupby('sender').size()

        agents = list(set(public_msgs.index) | set(private_msgs.index))
        x = np.arange(len(agents))
        width = 0.35

        public_counts = [public_msgs.get(agent, 0) for agent in agents]
        private_counts = [private_msgs.get(agent, 0) for agent in agents]

        bars1 = ax2.bar(x - width/2, public_counts, width, label='Public (to: all)',
                       color='steelblue', alpha=0.7, edgecolor='black')
        bars2 = ax2.bar(x + width/2, private_counts, width, label='Private (DMs)',
                       color='coral', alpha=0.7, edgecolor='black')

        ax2.set_xlabel('Agent', fontweight='bold')
        ax2.set_ylabel('Number of Messages', fontweight='bold')
        ax2.set_title('Public vs. Private Messages', fontweight='bold', fontsize=14)
        ax2.set_xticks(x)
        ax2.set_xticklabels(agents, rotation=45, ha='right')
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')

        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2., height,
                            f'{int(height)}',
                            ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        if save:
            plt.savefig(self.output_dir / "figure3_message_timeline.png", dpi=300, bbox_inches='tight')
            plt.savefig(self.output_dir / "figure3_message_timeline.pdf", bbox_inches='tight')
        plt.show()

        return fig

    def plot_trade_activity(self, save=True):
        """
        Figure 4: Trading Activity Analysis
        Shows number of trades per agent
        """
        # Count trades from action files
        actions_dir = self.exp_dir / "actions"
        trade_counts = {}

        for action_file in actions_dir.glob("*.json"):
            agent_name = action_file.stem.rsplit('_', 2)[0]  # Extract agent name

            with open(action_file) as f:
                try:
                    data = json.load(f)
                    num_trades = len(data.get('trades', []))
                    trade_counts[agent_name] = trade_counts.get(agent_name, 0) + num_trades
                except:
                    pass

        fig, ax = plt.subplots(figsize=(12, 7))

        agents = sorted(trade_counts.keys(), key=lambda x: trade_counts[x], reverse=True)
        counts = [trade_counts[agent] for agent in agents]
        colors = [self.agent_colors.get(agent, '#95a5a6') for agent in agents]

        bars = ax.bar(range(len(agents)), counts, color=colors, alpha=0.7, edgecolor='black')

        ax.set_xlabel('Agent', fontweight='bold')
        ax.set_ylabel('Total Number of Trades', fontweight='bold')
        ax.set_title('Trading Activity by Agent', fontweight='bold', fontsize=16)
        ax.set_xticks(range(len(agents)))
        ax.set_xticklabels(agents, rotation=45, ha='right')
        ax.grid(True, alpha=0.3, axis='y')

        # Add value labels
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Add role annotations
        for i, agent in enumerate(agents):
            role = self.agent_roles.get(agent, '')
            if 'Manipulator' in role:
                style = 'italic'
                color = 'red'
            elif 'Victim' in role:
                style = 'italic'
                color = 'blue'
            else:
                style = 'normal'
                color = 'gray'

            ax.text(i, -max(counts)*0.05, role.split('(')[1].strip(')'),
                   ha='center', va='top', fontsize=8, style=style, color=color, rotation=0)

        plt.tight_layout()
        if save:
            plt.savefig(self.output_dir / "figure4_trade_activity.png", dpi=300, bbox_inches='tight')
            plt.savefig(self.output_dir / "figure4_trade_activity.pdf", bbox_inches='tight')
        plt.show()

        return fig

    def plot_performance_heatmap(self, save=True):
        """
        Figure 5: Performance Heatmap
        Shows portfolio value changes across cycles as a heatmap
        """
        fig, ax = plt.subplots(figsize=(16, 6))

        # Calculate P&L from starting balance
        agents = [col for col in self.portfolio_df.columns if col != 'cycle']
        pnl_df = self.portfolio_df[agents] - 10000

        # Create heatmap
        sns.heatmap(pnl_df.T, cmap='RdYlGn', center=0,
                   cbar_kws={'label': 'P&L (USDT)'},
                   linewidths=0.5, linecolor='gray',
                   ax=ax, fmt='.0f', annot=False)

        ax.set_xlabel('Cycle', fontweight='bold')
        ax.set_ylabel('Agent', fontweight='bold')
        ax.set_title('Portfolio P&L Heatmap Over Time', fontweight='bold', fontsize=16)

        plt.tight_layout()
        if save:
            plt.savefig(self.output_dir / "figure5_pnl_heatmap.png", dpi=300, bbox_inches='tight')
            plt.savefig(self.output_dir / "figure5_pnl_heatmap.pdf", bbox_inches='tight')
        plt.show()

        return fig

    def generate_all_figures(self):
        """Generate all visualization figures"""
        print("Generating visualizations...")
        print(f"Output directory: {self.output_dir}")
        print()

        print("📊 Figure 1: Portfolio Performance Over Time...")
        self.plot_portfolio_performance()

        print("📊 Figure 2: Final Performance Comparison...")
        self.plot_final_performance_bar()

        print("📊 Figure 3: Message Timeline...")
        self.plot_message_timeline()

        print("📊 Figure 4: Trading Activity...")
        self.plot_trade_activity()

        print("📊 Figure 5: Performance Heatmap...")
        self.plot_performance_heatmap()

        print()
        print("✅ All figures generated successfully!")
        print(f"📁 Saved to: {self.output_dir}")
        print()
        print("Files created:")
        for file in sorted(self.output_dir.glob("*.png")):
            print(f"  - {file.name}")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_results.py <experiment_logs_dir>")
        print()
        print("Example:")
        print("  python visualize_results.py experiment_logs/20260313_033128")
        sys.exit(1)

    exp_dir = sys.argv[1]

    if not os.path.exists(exp_dir):
        print(f"Error: Directory not found: {exp_dir}")
        sys.exit(1)

    # Check required files
    required_files = ["portfolio_performance.csv", "messages.csv"]
    for file in required_files:
        if not os.path.exists(os.path.join(exp_dir, file)):
            print(f"Error: Required file not found: {file}")
            print(f"Please run analyze_results.py first with --export flag")
            sys.exit(1)

    visualizer = ExperimentVisualizer(exp_dir)
    visualizer.generate_all_figures()


if __name__ == "__main__":
    main()
