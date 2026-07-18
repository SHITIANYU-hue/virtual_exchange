import pytest
from auditor.config import AuditorConfig
from auditor.threat_scorer import ThreatScorer
from auditor.models import AuditVerdictType, ThreatCategory, RuleViolation, LLMAuditResult

def test_threat_scorer():
    config = AuditorConfig(
        block_threshold=0.8,
        flag_threshold=0.4,
        rule_weight=0.3,
        stat_weight=0.3,
        llm_weight=0.4
    )
    scorer = ThreatScorer(config)
    
    # Low concern
    score = scorer.calculate(0.1, 0.1, 0.1)
    assert score < 0.4
    assert scorer.determine_verdict(score) == AuditVerdictType.ALLOWED
    
    # Medium concern
    score = scorer.calculate(0.6, 0.5, 0.5)
    assert score >= 0.4 and score < 0.8
    assert scorer.determine_verdict(score) == AuditVerdictType.FLAGGED
    
    # High concern
    score = scorer.calculate(0.9, 0.9, 1.0)
    assert score >= 0.8
    assert scorer.determine_verdict(score) == AuditVerdictType.BLOCKED
    
    # Cache hit (redistributes weight)
    score = scorer.calculate(0.5, 0.5, 0.0, cache_hit=True)
    # (0.3 + 0.2)*0.5 + (0.3 + 0.2)*0.5 = 0.5
    assert score == 0.5
    
def test_category_determination():
    config = AuditorConfig()
    scorer = ThreatScorer(config)
    
    # LLM category has priority
    llm_res = LLMAuditResult(
        verdict='manipulative',
        threat_category=ThreatCategory.WASH_TRADING,
        confidence=0.9,
        reasoning=''
    )
    cat = scorer.determine_category([], [], llm_res)
    assert cat == ThreatCategory.WASH_TRADING
    
    # Rule category fallback
    rule_v = RuleViolation(rule_id='R002', rule_name='', description='', severity=0.9)
    cat = scorer.determine_category([rule_v], [], None)
    assert cat == ThreatCategory.PUMP_DUMP
