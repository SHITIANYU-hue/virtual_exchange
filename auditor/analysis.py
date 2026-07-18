"""Post-experiment audit analysis for the Agent Auditor system."""
import json
import csv
from collections import Counter, defaultdict


class AuditAnalyzer:
    """Generates comprehensive audit reports from experiment audit logs."""
    
    def __init__(self, audit_log: list[dict]):
        self.audit_log = audit_log
    
    def generate_report(self) -> dict:
        """Generate comprehensive audit analysis report."""
        if not self.audit_log:
            return {'summary': 'No audit data available'}
        
        return {
            'summary': self._summary_stats(),
            'manipulation_detection': self._manipulation_analysis(),
            'agent_risk_profiles': self._agent_risk_profiles(),
            'behavior_evolution': self._behavior_evolution(),
            'coordination_analysis': self._coordination_analysis(),
            'cache_efficiency': self._cache_analysis(),
        }
    
    def _summary_stats(self) -> dict:
        total = len(self.audit_log)
        flagged = sum(1 for e in self.audit_log if e.get('verdict') == 'flagged')
        blocked = sum(1 for e in self.audit_log if e.get('verdict') == 'blocked')
        scores = [e.get('threat_score', 0) for e in self.audit_log]
        return {
            'total_actions_audited': total,
            'flagged_count': flagged,
            'blocked_count': blocked,
            'flag_rate': flagged / total if total > 0 else 0,
            'block_rate': blocked / total if total > 0 else 0,
            'avg_threat_score': sum(scores) / len(scores) if scores else 0,
            'max_threat_score': max(scores) if scores else 0,
        }
    
    def _manipulation_analysis(self) -> dict:
        categories = Counter(
            e.get('threat_category', 'none') 
            for e in self.audit_log 
            if e.get('threat_category') and e.get('threat_category') != 'none'
        )
        return {
            'detected_categories': dict(categories),
            'total_manipulative_actions': sum(categories.values()),
            'most_common_manipulation': categories.most_common(1)[0] if categories else None,
        }
    
    def _agent_risk_profiles(self) -> dict:
        agents = defaultdict(list)
        for e in self.audit_log:
            agents[e.get('agent_name', 'unknown')].append(e)
        
        profiles = {}
        for name, events in agents.items():
            scores = [e.get('threat_score', 0) for e in events]
            flagged = sum(1 for e in events if e.get('verdict') in ('flagged', 'blocked'))
            profiles[name] = {
                'total_actions': len(events),
                'flagged_actions': flagged,
                'risk_rate': flagged / len(events) if events else 0,
                'avg_threat_score': sum(scores) / len(scores) if scores else 0,
                'max_threat_score': max(scores) if scores else 0,
                'categories': dict(Counter(
                    e.get('threat_category', 'none') for e in events if e.get('threat_category') != 'none'
                )),
            }
        
        return profiles
    
    def _behavior_evolution(self) -> dict:
        agents = defaultdict(list)
        for e in self.audit_log:
            agents[e.get('agent_name', 'unknown')].append({
                'cycle': e.get('cycle', 0) if 'cycle' not in e else e.get('cycle_number', 0),
                'threat_score': e.get('threat_score', 0),
                'verdict': e.get('verdict'),
            })
        
        evolution = {}
        for name, events in agents.items():
            sorted_events = sorted(events, key=lambda x: x.get('cycle', 0))
            evolution[name] = sorted_events
        
        return evolution
    
    def _coordination_analysis(self) -> dict:
        coord = [e for e in self.audit_log if e.get('threat_category') == 'coordinated_manipulation']
        return {
            'coordinated_actions_detected': len(coord),
            'involved_agents': list(set(e.get('agent_name') for e in coord)),
        }
    
    def _cache_analysis(self) -> dict:
        cache_hits = sum(1 for e in self.audit_log if e.get('cache_hit'))
        total = len(self.audit_log)
        return {
            'total_audits': total,
            'cache_hits': cache_hits,
            'cache_hit_rate': cache_hits / total if total > 0 else 0,
        }
    
    def save_report(self, filepath: str):
        report = self.generate_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f'[AgentAuditor] Audit report saved to {filepath}')
    
    def save_csv(self, filepath: str):
        if not self.audit_log:
            return
        fieldnames = ['timestamp', 'agent_id', 'agent_name', 'action_type', 'verdict', 
                      'threat_score', 'threat_category', 'rule_score', 
                      'stat_score', 'llm_score', 'cache_hit', 'llm_reasoning']
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for event in self.audit_log:
                # Add placeholders for nested lists/dicts to avoid errors during csv write
                flat_event = event.copy()
                flat_event.pop('rule_violations', None)
                flat_event.pop('anomalies', None)
                flat_event.pop('context_snapshot', None)
                flat_event.pop('action_details', None)
                writer.writerow(flat_event)
        print(f'[AgentAuditor] Audit CSV saved to {filepath}')
