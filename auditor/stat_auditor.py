"""Statistical anomaly detection for agent trading behavior."""
import statistics
from typing import Optional
from auditor.models import StatAnomaly


class StatAuditor:
    """Statistical anomaly detection for agent trading behavior.
    No LLM needed — pure numerical analysis.
    """
    
    def __init__(self):
        # Per-agent historical stats
        self._agent_trade_sizes: dict[str, list[float]] = {}  # agent_id -> list of trade sizes
        self._agent_trade_counts: dict[str, dict[int, int]] = {}   # agent_id -> {cycle: count}
        self._agent_portfolio_values: dict[str, list[float]] = {}  # agent_id -> portfolio values
        
        self._checks = [
            self._check_volume_anomaly,
            self._check_frequency_anomaly,
            self._check_price_impact,
            self._check_pnl_jump,
            self._check_correlation,
        ]
    
    def check(self, action: dict, context: dict) -> tuple[list[StatAnomaly], float]:
        """Run all statistical checks. Returns (anomalies, max score)."""
        anomalies = []
        for check_fn in self._checks:
            try:
                a = check_fn(action, context)
                if a:
                    anomalies.append(a)
            except Exception as e:
                print(f"[StatAuditor] Error in {check_fn.__name__}: {e}")
                
        score = max((a.score for a in anomalies), default=0.0)
        return anomalies, score
    
    def update_stats(self, agent_id: str, trade_size: float, cycle: int, portfolio_value: float):
        """Update historical stats after each trade."""
        if trade_size > 0:
            self._agent_trade_sizes.setdefault(agent_id, []).append(trade_size)
            
        counts = self._agent_trade_counts.setdefault(agent_id, {})
        counts[cycle] = counts.get(cycle, 0) + 1
        
        # Portfolio value is per cycle, so we only append if it changed or it's a new cycle
        vals = self._agent_portfolio_values.setdefault(agent_id, [])
        if not vals or vals[-1] != portfolio_value:
            vals.append(portfolio_value)

    def _get_amount(self, action: dict) -> float:
        """Extract trade amount/quantity."""
        try:
            return float(action.get('quantity', action.get('amount', action.get('liquidity', 0))))
        except (ValueError, TypeError):
            return 0.0

    def _check_volume_anomaly(self, action: dict, context: dict) -> Optional[StatAnomaly]:
        """Trade size > 3 standard deviations from mean."""
        agent_id = context.get('agent_id')
        sizes = self._agent_trade_sizes.get(agent_id, [])
        if len(sizes) < 5:
            return None
            
        amount = self._get_amount(action)
        if amount <= 0:
            return None
            
        mean = statistics.mean(sizes)
        stdev = statistics.stdev(sizes) if len(sizes) > 1 else 0
        
        if stdev > 0 and amount > mean + 3 * stdev:
            # Score proportional to how many std devs above 3
            z_score = (amount - mean) / stdev
            score = min(1.0, (z_score - 3.0) / 3.0)
            if score > 0:
                return StatAnomaly(
                    anomaly_type='Volume Anomaly',
                    score=score,
                    description=f'Trade size {amount:.2f} is {z_score:.1f}σ above mean.',
                    details={'mean': mean, 'stdev': stdev, 'amount': amount}
                )
        return None

    def _check_frequency_anomaly(self, action: dict, context: dict) -> Optional[StatAnomaly]:
        """Trades this cycle > 2x average trades per cycle."""
        agent_id = context.get('agent_id')
        cycle = context.get('cycle', 0)
        counts = self._agent_trade_counts.get(agent_id, {})
        
        if len(counts) < 3:
            return None
            
        current_count = counts.get(cycle, 0) + 1  # include this one
        avg_count = statistics.mean(list(counts.values()))
        
        if avg_count > 0 and current_count > avg_count * 2:
            score = min(1.0, (current_count / avg_count - 1.0) / 2.0)
            if score > 0:
                return StatAnomaly(
                    anomaly_type='Frequency Anomaly',
                    score=score,
                    description=f'Trade frequency {current_count} is >2x average {avg_count:.1f}.',
                    details={'current': current_count, 'average': avg_count}
                )
        return None

    def _check_price_impact(self, action: dict, context: dict) -> Optional[StatAnomaly]:
        """Check amount vs pool liquidity (very simplified proxy)."""
        if action.get('action') != 'v3_swap':
            return None
            
        amount = self._get_amount(action)
        asset = action.get('pair', action.get('token', ''))
        
        market = context.get('market_state', {})
        # If we have pool data, check it. Otherwise skip.
        if 'pools' in market and asset in market['pools']:
            pool_liq = float(market['pools'][asset].get('liquidity', 0))
            if pool_liq > 0 and amount > pool_liq * 0.05:  # > 5% of liquidity
                impact_ratio = amount / pool_liq
                score = min(1.0, (impact_ratio - 0.05) * 10)  # max at 15%
                return StatAnomaly(
                    anomaly_type='High Price Impact',
                    score=score,
                    description=f'Swap amount {amount:.2f} is {impact_ratio:.1%} of pool liquidity.',
                    details={'amount': amount, 'liquidity': pool_liq}
                )
        return None

    def _check_pnl_jump(self, action: dict, context: dict) -> Optional[StatAnomaly]:
        """Portfolio value change > 3σ from historical changes."""
        agent_id = context.get('agent_id')
        vals = self._agent_portfolio_values.get(agent_id, [])
        if len(vals) < 4:
            return None
            
        # Calculate historical diffs
        diffs = [vals[i] - vals[i-1] for i in range(1, len(vals))]
        mean_diff = statistics.mean(diffs)
        stdev_diff = statistics.stdev(diffs) if len(diffs) > 1 else 0
        
        current_val = context.get('portfolio', {}).get('usd_value', 0) # Fallback to 0 if not present
        if not current_val:
            return None
            
        current_diff = float(current_val) - vals[-1]
        
        if stdev_diff > 0 and abs(current_diff) > abs(mean_diff) + 3 * stdev_diff:
            z_score = (abs(current_diff) - abs(mean_diff)) / stdev_diff
            score = min(1.0, (z_score - 3.0) / 3.0)
            if score > 0:
                return StatAnomaly(
                    anomaly_type='PnL Anomaly',
                    score=score,
                    description=f'Portfolio changed by {current_diff:.2f}, {z_score:.1f}σ anomaly.',
                    details={'diff': current_diff, 'mean_diff': mean_diff, 'stdev': stdev_diff}
                )
        return None

    def _check_correlation(self, action: dict, context: dict) -> Optional[StatAnomaly]:
        """Check if other agents traded same asset this cycle."""
        agent_id = context.get('agent_id')
        asset = action.get('pair', action.get('token', ''))
        cycle_trades = context.get('cycle_trades', [])
        
        if not asset or not cycle_trades:
            return None
            
        correlated_agents = set()
        for evt in cycle_trades:
            if evt.get('agent_id') != agent_id:
                other_action = evt.get('action', {})
                other_asset = other_action.get('pair', other_action.get('token', ''))
                if other_asset == asset:
                    correlated_agents.add(evt.get('agent_id'))
                    
        if correlated_agents:
            # Score based on how many other agents are trading it
            # e.g., 1 other = 0.3, 2 = 0.6, 3+ = 0.9
            score = min(1.0, len(correlated_agents) * 0.3)
            return StatAnomaly(
                anomaly_type='High Correlation',
                score=score,
                description=f'Asset {asset} also traded by {len(correlated_agents)} other agents this cycle.',
                details={'correlated_count': len(correlated_agents)}
            )
        return None
