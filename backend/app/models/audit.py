"""Database models for the Agent Auditor system."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.app.database import Base


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(String(100), nullable=True, index=True)
    cycle_number = Column(Integer, nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    agent_name = Column(String(50), nullable=False)
    
    # Action details
    action_type = Column(String(50), nullable=False, index=True)  # buy_spot, sell_spot, v3_swap, etc.
    action_details = Column(JSON, nullable=True)
    
    # Audit results
    verdict = Column(String(20), nullable=False, index=True)  # allowed, flagged, blocked
    threat_score = Column(Float, nullable=False, default=0.0)
    threat_category = Column(String(50), nullable=True)  # wash_trading, pump_dump, etc.
    
    # Component scores
    rule_score = Column(Float, nullable=False, default=0.0)
    stat_score = Column(Float, nullable=False, default=0.0)
    llm_score = Column(Float, nullable=True)  # null if cache hit or LLM not called
    
    # Details
    triggered_rules = Column(JSON, nullable=True)  # [{rule_id, rule_name, severity}]
    anomalies = Column(JSON, nullable=True)  # [{anomaly_type, score}]
    llm_reasoning = Column(Text, nullable=True)
    
    # Context snapshot
    agent_reasoning = Column(JSON, nullable=True)  # ReAct reasoning
    market_state = Column(JSON, nullable=True)
    
    # Cache
    cache_hit = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AuditSummary(Base):
    __tablename__ = 'audit_summaries'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    agent_name = Column(String(50), nullable=False)
    
    total_actions = Column(Integer, default=0)
    flagged_count = Column(Integer, default=0)
    blocked_count = Column(Integer, default=0)
    avg_threat_score = Column(Float, default=0.0)
    max_threat_score = Column(Float, default=0.0)
    dominant_threat_category = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
