"""Data models for Agent Auditor."""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


class ThreatCategory(str, Enum):
    NONE = 'none'
    WASH_TRADING = 'wash_trading'
    PUMP_DUMP = 'pump_dump'
    FRONT_RUNNING = 'front_running'
    SPOOFING = 'spoofing'
    COORDINATED_MANIPULATION = 'coordinated_manipulation'
    DECEPTIVE_MESSAGING = 'deceptive_messaging'
    LIQUIDITY_EXPLOITATION = 'liquidity_exploitation'


class AuditVerdictType(str, Enum):
    ALLOWED = 'allowed'
    FLAGGED = 'flagged'
    BLOCKED = 'blocked'


class CacheScope(str, Enum):
    ONCE = 'once'
    TASK = 'task'
    UNIVERSAL = 'universal'


@dataclass
class RuleViolation:
    rule_id: str
    rule_name: str
    description: str
    severity: float  # 0.0-1.0
    evidence: dict = field(default_factory=dict)


@dataclass
class StatAnomaly:
    anomaly_type: str
    score: float  # 0.0-1.0
    description: str
    details: dict = field(default_factory=dict)


@dataclass
class LLMAuditResult:
    verdict: str  # 'safe', 'suspicious', 'manipulative'
    threat_category: ThreatCategory
    confidence: float
    reasoning: str
    verified_patterns: list[dict] = field(default_factory=list)


@dataclass
class AuditResult:
    rule_violations: list[RuleViolation] = field(default_factory=list)
    rule_score: float = 0.0
    stat_anomalies: list[StatAnomaly] = field(default_factory=list)
    stat_score: float = 0.0
    llm_result: Optional[LLMAuditResult] = None
    llm_score: float = 0.0
    cache_hit: bool = False


@dataclass
class AuditVerdict:
    verdict_type: AuditVerdictType
    threat_score: float
    threat_category: ThreatCategory
    audit_result: AuditResult
    agent_id: str
    agent_name: str
    action_type: str
    action_details: dict
    context_snapshot: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_blocked(self) -> bool:
        return self.verdict_type == AuditVerdictType.BLOCKED
    
    @property
    def is_flagged(self) -> bool:
        return self.verdict_type == AuditVerdictType.FLAGGED
    
    @property
    def is_allowed(self) -> bool:
        return self.verdict_type == AuditVerdictType.ALLOWED


@dataclass
class CachedVerdict:
    verdict: AuditVerdictType
    pattern: dict
