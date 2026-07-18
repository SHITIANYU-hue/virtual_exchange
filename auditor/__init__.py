"""Agent Auditor — Financial market surveillance system.

Inspired by AgentSentinel (arXiv 2509.07764), adapted for
adversarial multi-agent financial exchange monitoring.
"""

from auditor.config import AuditorConfig
from auditor.models import AuditVerdict, AuditVerdictType, ThreatCategory
from auditor.trade_gate import TradeGate

__all__ = [
    'AuditorConfig',
    'AuditVerdict',
    'AuditVerdictType', 
    'ThreatCategory',
    'TradeGate',
]
