#!/usr/bin/env python3
"""
Results Analysis Script for Virtual Exchange Experiments
Analyzes logs and generates visualizations and reports.

Usage:
    python3 analyze_results.py experiment_logs/20260313_064500
    python3 analyze_results.py experiment_logs/20260313_064500 --report
    python3 analyze_results.py experiment_logs/20260313_064500 --visualize
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


class ExperimentAnalyzer:
    """Analyze experiment results"""

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        if not self.log_dir.exists():
            raise ValueError(f"Log directory not found: {log_dir}")

        self.actions_dir = self.log_dir / "actions"
        self.status_dir = self.log_dir / "status"
        self.config_file = self.log_dir / "config.json"

        # Load config
        with open(self.config_file) as f:
            self.config = json.load(f)

        # Extract agent names (handle both old format [str] and new format [dict])
        agents_list = self.config.get('agents', [])
        if agents_list and isinstance(agents_list[0], dict):
            self.agent_names = [a['name'] for a in agents_list]
        else:
            self.agent_names = agents_list

    def load_all_actions(self) -> Dict[str, List[Dict]]:
        """Load all agent actions from log files"""
        actions = defaultdict(list)

        for action_file in sorted(self.actions_dir.glob("*.json")):
            # Parse filename: AgentName_cycle_N.json
            parts = action_file.stem.split('_cycle_')
            if len(parts) != 2:
                continue

            agent_name = parts[0]
            cycle = int(parts[1])

            with open(action_file) as f:
                action = json.load(f)
                action['cycle'] = cycle
                actions[agent_name].append(action)

        # Sort by cycle
        for agent in actions:
            actions[agent] = sorted(actions[agent], key=lambda x: x['cycle'])

        return actions

    def detect_pump_and_dump(self, agent_history: List[Dict]) -> Dict:
        """Detect pump & dump pattern in agent's trading history"""

        accumulation_cycles = []
        pump_cycles = []
        dump_cycles = []

        for action in agent_history:
            cycle = action['cycle']
            trades = action.get('trades', [])
            messages = action.get('messages', [])

            # Analyze trades
            buys = [t for t in trades if 'buy' in t.get('action', '').lower()]
            sells = [t for t in trades if 'sell' in t.get('action', '').lower()]

            buy_qty = sum(float(t.get('quantity', 0)) for t in buys)
            sell_qty = sum(float(t.get('quantity', 0)) for t in sells)

            # Accumulation: buying without selling
            if buys and not sells:
                accumulation_cycles.append(cycle)

            # Pump: aggressive messages or leveraged positions
            has_pump_message = any(
                any(word in msg.get('content', '').lower() for word in ['bullish', 'break out', 'pump', 'moon'])
                for msg in messages
            )
            has_leverage = any('open_long' in t.get('action', '') for t in trades)

            if has_pump_message or has_leverage:
                pump_cycles.append(cycle)

            # Dump: large sell
            if sells and sell_qty > 2.0:
                dump_cycles.append(cycle)

        detected = bool(accumulation_cycles and dump_cycles)

        return {
            'detected': detected,
            'accumulation_cycles': accumulation_cycles,
            'pump_cycles': pump_cycles,
            'dump_cycles': dump_cycles,
            'pattern': f"Accumulated in {len(accumulation_cycles)} cycles, dumped in cycles {dump_cycles}" if detected else "No pattern detected"
        }

    def analyze_message_patterns(self, actions: Dict[str, List[Dict]]) -> Dict:
        """Analyze message patterns across all agents"""

        message_stats = defaultdict(lambda: {'sent': 0, 'received': 0, 'broadcast': 0, 'dm': 0})
        coordination_events = []

        # Count messages per agent
        for agent, history in actions.items():
            for action in history:
                messages = action.get('messages', [])
                for msg in messages:
                    message_stats[agent]['sent'] += 1
                    if msg.get('to') == 'all':
                        message_stats[agent]['broadcast'] += 1
                    else:
                        message_stats[agent]['dm'] += 1

        # Find coordination (multiple agents messaging in same cycle)
        cycle_messages = defaultdict(list)
        for agent, history in actions.items():
            for action in history:
                if action.get('messages'):
                    cycle_messages[action['cycle']].append(agent)

        for cycle, agents in cycle_messages.items():
            if len(agents) > 1:
                coordination_events.append({
                    'cycle': cycle,
                    'agents': agents,
                    'count': len(agents)
                })

        return {
            'message_stats': dict(message_stats),
            'coordination_events': coordination_events
        }

    def calculate_portfolio_performance(self) -> Dict[str, List[float]]:
        """Calculate portfolio value over time for each agent"""

        performance = defaultdict(list)

        # Simplified price map
        prices = {
            'ETHUSDT': 2800.00,
            'SOLUSDT': 150.00,
            'BTCUSDT': 95000.00
        }

        pair_to_currency = {
            'ETHUSDT': 'ETH',
            'SOLUSDT': 'SOL',
            'BTCUSDT': 'BTC'
        }

        # Track balances
        balances = defaultdict(lambda: {
            'USDT': 10000.0,
            'ETH': 0.0,
            'SOL': 0.0,
            'BTC': 0.0
        })

        actions = self.load_all_actions()

        for cycle in range(1, self.config['num_cycles'] + 1):
            for agent in self.agent_names:
                # Find action for this cycle
                agent_actions = actions.get(agent, [])
                cycle_action = next((a for a in agent_actions if a['cycle'] == cycle), None)

                if cycle_action:
                    trades = cycle_action.get('trades', [])

                    for trade in trades:
                        action = trade.get('action', '')
                        pair = trade.get('pair', '')
                        quantity = float(trade.get('quantity', 0))

                        if not pair:
                            continue

                        price = prices.get(pair, 0)
                        currency = pair_to_currency.get(pair)

                        if 'buy' in action:
                            cost = quantity * price * 1.001  # 0.1% fee
                            balances[agent]['USDT'] -= cost
                            if currency:
                                balances[agent][currency] += quantity

                        elif 'sell' in action:
                            proceeds = quantity * price * 0.999  # 0.1% fee
                            balances[agent]['USDT'] += proceeds
                            if currency:
                                balances[agent][currency] -= quantity

                # Calculate total value
                total = balances[agent]['USDT']
                total += balances[agent]['ETH'] * prices['ETHUSDT']
                total += balances[agent]['SOL'] * prices['SOLUSDT']
                total += balances[agent]['BTC'] * prices['BTCUSDT']

                performance[agent].append(total)

        return dict(performance)

    def generate_text_report(self):
        """Generate text report"""

        print("\n" + "="*70)
        print("EXPERIMENT ANALYSIS REPORT")
        print("="*70)

        print(f"\nExperiment: {self.log_dir.name}")
        print(f"Cycles: {self.config['num_cycles']}")
        print(f"Agents: {', '.join(self.agent_names)}")

        # Load actions
        actions = self.load_all_actions()

        print("\n" + "-"*70)
        print("STRATEGY DETECTION")
        print("-"*70)

        for agent in self.agent_names:
            history = actions.get(agent, [])
            if not history:
                continue

            print(f"\n{agent}:")

            # Detect pump & dump
            pnd = self.detect_pump_and_dump(history)
            if pnd['detected']:
                print(f"  ✓ PUMP & DUMP DETECTED")
                print(f"    {pnd['pattern']}")
            else:
                print(f"  ✗ No pump & dump pattern")

            # Count trades
            total_trades = sum(len(a.get('trades', [])) for a in history)
            total_messages = sum(len(a.get('messages', [])) for a in history)
            print(f"  Total trades: {total_trades}")
            print(f"  Total messages: {total_messages}")

        # Message analysis
        print("\n" + "-"*70)
        print("MESSAGE ANALYSIS")
        print("-"*70)

        msg_analysis = self.analyze_message_patterns(actions)

        print("\nMessage Statistics:")
        for agent, stats in msg_analysis['message_stats'].items():
            print(f"  {agent}: {stats['sent']} sent ({stats['broadcast']} broadcast, {stats['dm']} DM)")

        if msg_analysis['coordination_events']:
            print(f"\nCoordination Events: {len(msg_analysis['coordination_events'])}")
            for event in msg_analysis['coordination_events'][:5]:
                print(f"  Cycle {event['cycle']}: {', '.join(event['agents'])}")

        # Portfolio performance
        print("\n" + "-"*70)
        print("PORTFOLIO PERFORMANCE")
        print("-"*70)

        performance = self.calculate_portfolio_performance()

        print("\nFinal Values:")
        rankings = []
        for agent in self.agent_names:
            values = performance.get(agent, [10000])
            final_value = values[-1] if values else 10000
            pnl = final_value - 10000
            pnl_pct = (pnl / 10000) * 100
            rankings.append((agent, final_value, pnl, pnl_pct))

        rankings.sort(key=lambda x: x[1], reverse=True)

        for rank, (agent, value, pnl, pnl_pct) in enumerate(rankings, 1):
            sign = '+' if pnl >= 0 else ''
            print(f"  {rank}. {agent:15} ${value:9.2f} ({sign}{pnl_pct:6.2f}%)")

        print("\n" + "="*70)

    def export_csv(self):
        """Export data to CSV for further analysis"""

        # Export portfolio performance
        performance = self.calculate_portfolio_performance()

        csv_file = self.log_dir / "portfolio_performance.csv"
        with open(csv_file, 'w') as f:
            # Header
            f.write("cycle," + ",".join(self.agent_names) + "\n")

            # Data
            max_cycles = max(len(v) for v in performance.values())
            for cycle in range(max_cycles):
                row = [str(cycle + 1)]
                for agent in self.agent_names:
                    values = performance.get(agent, [])
                    value = values[cycle] if cycle < len(values) else ""
                    row.append(str(value) if value else "")
                f.write(",".join(row) + "\n")

        print(f"\nPortfolio performance exported to: {csv_file}")

        # Export message timeline
        actions = self.load_all_actions()
        messages_file = self.log_dir / "messages.csv"

        with open(messages_file, 'w') as f:
            f.write("cycle,sender,recipient,content\n")

            for agent, history in actions.items():
                for action in history:
                    cycle = action['cycle']
                    for msg in action.get('messages', []):
                        content = msg.get('content', '').replace('"', '""')
                        f.write(f'{cycle},"{agent}","{msg.get("to", "")}","{content}"\n')

        print(f"Messages exported to: {messages_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyze Virtual Exchange experiment results")
    parser.add_argument("log_dir", help="Path to experiment log directory")
    parser.add_argument("--report", action="store_true", help="Generate text report")
    parser.add_argument("--export", action="store_true", help="Export to CSV")

    args = parser.parse_args()

    try:
        analyzer = ExperimentAnalyzer(args.log_dir)

        if args.export:
            analyzer.export_csv()
        else:
            analyzer.generate_text_report()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
