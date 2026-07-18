"""Main orchestrator for the Agent Auditor system."""
import json
from datetime import datetime
from typing import Optional

from auditor.config import AuditorConfig
from auditor.models import (
    AuditVerdict, AuditVerdictType, AuditResult, 
    ThreatCategory, LLMAuditResult
)
from auditor.context_collector import ContextCollector
from auditor.rule_auditor import RuleAuditor
from auditor.stat_auditor import StatAuditor
from auditor.llm_auditor import LLMAuditor
from auditor.audit_cache import AuditCache
from auditor.threat_scorer import ThreatScorer


class TradeGate:
    """Pre-execution interceptor for all agent financial actions.
    
    Analogous to AgentSentinel's process suspension mechanism.
    """
    
    def __init__(self, config: AuditorConfig = None):
        self.config = config or AuditorConfig()
        
        # Sub-components
        self.context_collector = ContextCollector()
        self.rule_auditor = RuleAuditor(config=self.config)
        self.stat_auditor = StatAuditor()
        self.llm_auditor = LLMAuditor(
            model=self.config.llm_model,
            timeout=self.config.llm_timeout
        )
        self.cache = AuditCache(max_size=self.config.cache_max_size)
        self.scorer = ThreatScorer(config=self.config)
        
        # In-memory stores
        self.audit_log: list[AuditVerdict] = []
        self._trade_history: dict[str, list[dict]] = {}
        self._message_history: dict[str, list[dict]] = {}
        self._current_cycle_trades: dict[int, list[dict]] = {}
        
    async def audit_action(
        self,
        agent_id: str,
        agent_name: str,
        action: dict,
        cycle: int,
        agent_info: dict = None,
        market_state: dict = None,
        memory: dict = None,
    ) -> AuditVerdict:
        """Main entry point: audit a single trade action."""
        if not self.config.enabled:
            return self._make_verdict(
                AuditVerdictType.ALLOWED, 0.0, ThreatCategory.NONE,
                AuditResult(), agent_id, agent_name, action, {}
            )
            
        # 1. Collect context
        context = self.context_collector.collect(
            agent_id, agent_name, action, cycle,
            agent_info=agent_info, market_state=market_state, memory=memory
        )
        self.context_collector.add_trade_history(context, self._trade_history.get(agent_id, []))
        self.context_collector.add_message_history(context, self._message_history.get(agent_id, []))
        context['cycle_trades'] = self._current_cycle_trades.get(cycle, [])
        
        # 2. Rule check
        rule_violations, rule_score = self.rule_auditor.check(action, context)
        
        # 3. Stat check
        stat_anomalies, stat_score = self.stat_auditor.check(action, context)
        
        audit_result = AuditResult(
            rule_violations=rule_violations,
            rule_score=rule_score,
            stat_anomalies=stat_anomalies,
            stat_score=stat_score,
        )
        
        # Fast path blocking
        if self.config.mode == 'block_and_flag' and rule_score >= self.config.block_threshold:
            verdict = self._make_verdict(
                AuditVerdictType.BLOCKED, rule_score,
                self.scorer.determine_category(rule_violations, stat_anomalies, None),
                audit_result, agent_id, agent_name, action, context
            )
            self._record(verdict, action, agent_id, cycle)
            return verdict
            
        # 4. Cache lookup
        agent_role = (agent_info or {}).get('role', '')
        action_type = action.get('action', '')
        asset = action.get('pair', action.get('token', ''))
        amount = float(action.get('quantity', action.get('amount', action.get('liquidity', 0))))
        size_bucket = 'small' if amount < 10 else ('medium' if amount < 100 else 'large')
        
        cached_verdict = None
        if self.config.cache_enabled:
            cached_verdict = self.cache.lookup(agent_role, action_type, asset, size_bucket)
            
        llm_result = None
        llm_score = 0.0
        cache_hit = cached_verdict is not None
        
        if cache_hit:
            audit_result.cache_hit = True
        else:
            # 5. LLM Audit
            combined_concern = rule_score + stat_score
            if combined_concern > 0.1:  # Only if there is some concern
                llm_result = await self.llm_auditor.audit(action, context, rule_violations, stat_anomalies)
                if llm_result:
                    audit_result.llm_result = llm_result
                    verdict_scores = {'safe': 0.0, 'suspicious': 0.5, 'manipulative': 1.0}
                    llm_score = llm_result.confidence * verdict_scores.get(llm_result.verdict, 0.0)
                    audit_result.llm_score = llm_score
                    
                    if self.config.cache_enabled and llm_result.verified_patterns:
                        self.cache.store(llm_result.verified_patterns)
                        
        # 6. Score
        threat_score = self.scorer.calculate(rule_score, stat_score, llm_score, cache_hit)
        category = self.scorer.determine_category(rule_violations, stat_anomalies, llm_result)
        
        # 7. Verdict
        if self.config.mode == 'log_only':
            verdict_type = AuditVerdictType.ALLOWED
        elif self.config.mode == 'flag_only':
            verdict_type = AuditVerdictType.FLAGGED if threat_score >= self.config.flag_threshold else AuditVerdictType.ALLOWED
        else:  # block_and_flag
            verdict_type = self.scorer.determine_verdict(threat_score)
            
        verdict = self._make_verdict(
            verdict_type, threat_score, category,
            audit_result, agent_id, agent_name, action, context
        )
        
        self._record(verdict, action, agent_id, cycle)
        return verdict
        
    def record_trade(self, agent_id: str, trade: dict, cycle: int):
        self._trade_history.setdefault(agent_id, []).append({**trade, 'cycle': cycle})
        self._current_cycle_trades.setdefault(cycle, []).append({'agent_id': agent_id, 'action': trade})
        
        # Update stat auditor
        amount = float(trade.get('quantity', trade.get('amount', trade.get('liquidity', 0))))
        self.stat_auditor.update_stats(agent_id, amount, cycle, 0.0)  # PnL updated separately if needed
        
    def record_message(self, agent_id: str, message: dict):
        self._message_history.setdefault(agent_id, []).append(message)
        
    def new_experiment(self):
        self.cache.flush_task_cache()
        self.audit_log.clear()
        self._trade_history.clear()
        self._message_history.clear()
        self._current_cycle_trades.clear()
        
    def get_audit_log(self) -> list[dict]:
        return [
            {
                'timestamp': v.timestamp.isoformat(),
                'agent_id': v.agent_id,
                'agent_name': v.agent_name,
                'action_type': v.action_type,
                'verdict': v.verdict_type.value,
                'threat_score': v.threat_score,
                'threat_category': v.threat_category.value,
                'rule_score': v.audit_result.rule_score,
                'stat_score': v.audit_result.stat_score,
                'llm_score': v.audit_result.llm_score,
                'cache_hit': v.audit_result.cache_hit,
                'rule_violations': [{'rule_id': r.rule_id, 'name': r.rule_name, 'severity': r.severity} for r in v.audit_result.rule_violations],
                'anomalies': [{'type': a.anomaly_type, 'score': a.score} for a in v.audit_result.stat_anomalies],
                'llm_reasoning': v.audit_result.llm_result.reasoning if v.audit_result.llm_result else None,
            }
            for v in self.audit_log
        ]
        
    def _make_verdict(self, verdict_type, threat_score, category, 
                      audit_result, agent_id, agent_name, action, context) -> AuditVerdict:
        return AuditVerdict(
            verdict_type=verdict_type,
            threat_score=threat_score,
            threat_category=category,
            audit_result=audit_result,
            agent_id=str(agent_id),
            agent_name=agent_name,
            action_type=action.get('action', 'unknown'),
            action_details=action,
            context_snapshot={
                'cycle': context.get('cycle'),
            } if context else {},
        )
        
    def _record(self, verdict: AuditVerdict, action: dict, agent_id: str, cycle: int):
        self.audit_log.append(verdict)
        
        emoji = {'allowed': '✅', 'flagged': '⚠️', 'blocked': '🚫'}
        icon = emoji.get(verdict.verdict_type.value, '❓')
        if verdict.verdict_type != AuditVerdictType.ALLOWED:
            print(f"  {icon} [AUDIT] {verdict.agent_name} | {verdict.action_type} | "
                  f"{verdict.verdict_type.value.upper()} | Score: {verdict.threat_score:.2f} | "
                  f"{verdict.threat_category.value}")
