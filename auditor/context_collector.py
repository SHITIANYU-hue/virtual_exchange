"""Context aggregation for Agent Auditor."""
from typing import Optional


class ContextCollector:
    """Aggregates context for auditing actions."""
    
    def __init__(self, api_base_url: str = 'http://localhost:8000'):
        self.api_base_url = api_base_url
    
    def collect(self, agent_id: str, agent_name: str, action: dict, 
                cycle: int, agent_info: dict = None,
                market_state: dict = None, memory: dict = None) -> dict:
        """Collect full context for audit.
        
        Returns dict with keys:
        - agent_id, agent_name, cycle
        - action: the trade action being audited
        - portfolio: agent's current balances
        - positions: agent's current positions
        - memory: agent's persistent memory (alliances, strategy, past actions)
        - market_state: current prices, pool states
        - react_reasoning: agent's ReAct output (observe/think/plan)
        - recent_trades: last N trades by this agent (from trade_history)
        - recent_messages: last N messages sent/received
        """
        # Build context from provided data + supplement from trade_history
        context = {
            'agent_id': agent_id,
            'agent_name': agent_name,
            'cycle': cycle,
            'action': action,
            'portfolio': agent_info.get('balances', {}) if agent_info else {},
            'positions': agent_info.get('positions', []) if agent_info else [],
            'memory': memory or {},
            'market_state': market_state or {},
            'react_reasoning': agent_info.get('last_react', {}) if agent_info else {},
            'recent_trades': [],  # populated from trade_history
            'recent_messages': [],  # populated from message_history
        }
        return context
    
    def add_trade_history(self, context: dict, trade_history: list):
        """Add recent trade history for this agent."""
        context['recent_trades'] = trade_history[-20:]  # Last 20 trades
    
    def add_message_history(self, context: dict, message_history: list):
        """Add recent messages sent/received by this agent."""
        context['recent_messages'] = message_history[-20:]
