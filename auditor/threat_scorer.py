"""Threat score calculation."""
from auditor.config import AuditorConfig
from auditor.models import AuditVerdictType, ThreatCategory, RuleViolation, StatAnomaly, LLMAuditResult
from typing import Optional


class ThreatScorer:
    """Calculates composite ThreatSense score and determines verdict."""
    
    def __init__(self, config: AuditorConfig):
        self.config = config
    
    def calculate(self, rule_score: float, stat_score: float, 
                  llm_score: float, cache_hit: bool = False) -> float:
        """Calculate composite ThreatSense score.
        
        ThreatSense = w_r * S_rule + w_s * S_stat + w_l * S_llm
        
        If cache_hit (LLM skipped), redistribute LLM weight equally to rules and stats.
        """
        if cache_hit:
            w_r = self.config.rule_weight + self.config.llm_weight / 2
            w_s = self.config.stat_weight + self.config.llm_weight / 2
            w_l = 0.0
        else:
            w_r = self.config.rule_weight
            w_s = self.config.stat_weight
            w_l = self.config.llm_weight
        
        score = w_r * rule_score + w_s * stat_score + w_l * llm_score
        return min(max(score, 0.0), 1.0)  # clamp to [0, 1]
    
    def determine_verdict(self, threat_score: float) -> AuditVerdictType:
        if threat_score >= self.config.block_threshold:
            return AuditVerdictType.BLOCKED
        elif threat_score >= self.config.flag_threshold:
            return AuditVerdictType.FLAGGED
        return AuditVerdictType.ALLOWED
    
    def determine_category(self, rule_violations: list[RuleViolation], 
                           stat_anomalies: list[StatAnomaly], 
                           llm_result: Optional[LLMAuditResult]) -> ThreatCategory:
        """Determine the dominant threat category from all evidence."""
        # Priority: LLM result > rule violations > stat anomalies
        if llm_result and llm_result.threat_category != ThreatCategory.NONE:
            return llm_result.threat_category
            
        # Map rule IDs to categories
        rule_to_category = {
            'R001': ThreatCategory.WASH_TRADING,
            'R002': ThreatCategory.PUMP_DUMP,
            'R003': ThreatCategory.FRONT_RUNNING,
            'R004': ThreatCategory.SPOOFING,
            'R007': ThreatCategory.COORDINATED_MANIPULATION,
            'R008': ThreatCategory.PUMP_DUMP,
            'R009': ThreatCategory.LIQUIDITY_EXPLOITATION,
            'R010': ThreatCategory.DECEPTIVE_MESSAGING,
        }
        
        if rule_violations:
            worst = max(rule_violations, key=lambda v: v.severity)
            return rule_to_category.get(worst.rule_id, ThreatCategory.NONE)
            
        return ThreatCategory.NONE
