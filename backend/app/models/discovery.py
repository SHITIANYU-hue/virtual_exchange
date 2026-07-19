"""Database models for the Discovery Auditor Agent Loop.

An open-set discovery agent mines emergent manipulation patterns from the
accumulated record every K cycles and persists them here — complementing the
per-action recognizer (`audit_events`).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class DiscoveredPattern(Base):
    __tablename__ = 'discovered_patterns'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(String(100), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    mechanism = Column(Text, nullable=True)
    involved_agents = Column(JSON, nullable=True)   # ["GoldenWhale", "CryptoGuru"]
    evidence = Column(JSON, nullable=True)          # [{cycle, agent, action, quote}]
    is_novel = Column(Boolean, default=True)
    known_category = Column(String(50), nullable=True)
    occurrence_count = Column(Integer, default=1)
    first_seen_cycle = Column(Integer, nullable=True)
    proposed_rule = Column(JSON, nullable=True)
    status = Column(String(20), default='proposed')  # proposed / confirmed / merged / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiscoveryRun(Base):
    __tablename__ = 'discovery_runs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(String(100), nullable=True, index=True)
    cycle = Column(Integer, nullable=False)
    window_start_cycle = Column(Integer, nullable=False)
    patterns_found = Column(Integer, default=0)
    novel_count = Column(Integer, default=0)
    llm_reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
