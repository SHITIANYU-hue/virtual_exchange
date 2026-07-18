"""API routes for the Agent Auditor system."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional
from datetime import datetime

from backend.app.database import get_db
from backend.app.models.audit import AuditEvent, AuditSummary

router = APIRouter(prefix='/api/audit', tags=['audit'])


@router.get('/events')
async def list_audit_events(
    agent_name: Optional[str] = None,
    verdict: Optional[str] = None,
    threat_category: Optional[str] = None,
    cycle_min: Optional[int] = None,
    cycle_max: Optional[int] = None,
    experiment_id: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List audit events with filtering."""
    query = select(AuditEvent).order_by(desc(AuditEvent.created_at))
    
    if agent_name:
        query = query.where(AuditEvent.agent_name == agent_name)
    if verdict:
        query = query.where(AuditEvent.verdict == verdict)
    if threat_category:
        query = query.where(AuditEvent.threat_category == threat_category)
    if cycle_min is not None:
        query = query.where(AuditEvent.cycle_number >= cycle_min)
    if cycle_max is not None:
        query = query.where(AuditEvent.cycle_number <= cycle_max)
    if experiment_id:
        query = query.where(AuditEvent.experiment_id == experiment_id)
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    events = result.scalars().all()
    
    return {
        'events': [
            {
                'id': str(e.id),
                'experiment_id': e.experiment_id,
                'cycle_number': e.cycle_number,
                'agent_id': str(e.agent_id),
                'agent_name': e.agent_name,
                'action_type': e.action_type,
                'action_details': e.action_details,
                'verdict': e.verdict,
                'threat_score': e.threat_score,
                'threat_category': e.threat_category,
                'rule_score': e.rule_score,
                'stat_score': e.stat_score,
                'llm_score': e.llm_score,
                'triggered_rules': e.triggered_rules,
                'anomalies': e.anomalies,
                'llm_reasoning': e.llm_reasoning,
                'cache_hit': e.cache_hit,
                'created_at': e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        'count': len(events),
    }

@router.get('/events/{event_id}')
async def get_audit_event(event_id: str, db: AsyncSession = Depends(get_db)):
    """Get single audit event with full details."""
    from uuid import UUID
    try:
        event_uuid = UUID(event_id)
    except ValueError:
        raise HTTPException(400, 'Invalid UUID')
        
    result = await db.execute(
        select(AuditEvent).where(AuditEvent.id == event_uuid)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, 'Audit event not found')
        
    return {
        'id': str(event.id),
        'experiment_id': event.experiment_id,
        'cycle_number': event.cycle_number,
        'agent_id': str(event.agent_id),
        'agent_name': event.agent_name,
        'action_type': event.action_type,
        'action_details': event.action_details,
        'verdict': event.verdict,
        'threat_score': event.threat_score,
        'threat_category': event.threat_category,
        'rule_score': event.rule_score,
        'stat_score': event.stat_score,
        'llm_score': event.llm_score,
        'triggered_rules': event.triggered_rules,
        'anomalies': event.anomalies,
        'llm_reasoning': event.llm_reasoning,
        'agent_reasoning': event.agent_reasoning,
        'market_state': event.market_state,
        'cache_hit': event.cache_hit,
        'created_at': event.created_at.isoformat() if event.created_at else None,
    }

@router.get('/agents/{agent_name}/summary')
async def get_agent_audit_summary(
    agent_name: str,
    experiment_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get audit summary for a specific agent."""
    query = select(AuditEvent).where(AuditEvent.agent_name == agent_name)
    if experiment_id:
        query = query.where(AuditEvent.experiment_id == experiment_id)
    result = await db.execute(query)
    events = result.scalars().all()
    
    if not events:
        return {'agent_name': agent_name, 'total_actions': 0}
    
    flagged = [e for e in events if e.verdict == 'flagged']
    blocked = [e for e in events if e.verdict == 'blocked']
    scores = [e.threat_score for e in events]
    
    categories = [e.threat_category for e in events if e.threat_category and e.threat_category != 'none']
    dominant = max(set(categories), key=categories.count) if categories else None
    
    return {
        'agent_name': agent_name,
        'total_actions': len(events),
        'flagged_count': len(flagged),
        'blocked_count': len(blocked),
        'allowed_count': len(events) - len(flagged) - len(blocked),
        'avg_threat_score': sum(scores) / len(scores),
        'max_threat_score': max(scores),
        'dominant_threat_category': dominant,
        'threat_score_history': [{'cycle': e.cycle_number, 'score': e.threat_score} for e in sorted(events, key=lambda x: x.cycle_number)],
    }

@router.get('/stats')
async def get_audit_stats(
    experiment_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Aggregate audit statistics."""
    query = select(AuditEvent)
    if experiment_id:
        query = query.where(AuditEvent.experiment_id == experiment_id)
    result = await db.execute(query)
    events = result.scalars().all()
    
    if not events:
        return {'total': 0}
    
    by_verdict = {}
    by_category = {}
    by_agent = {}
    
    for e in events:
        by_verdict[e.verdict] = by_verdict.get(e.verdict, 0) + 1
        
        cat = e.threat_category or 'none'
        by_category[cat] = by_category.get(cat, 0) + 1
        
        if e.agent_name not in by_agent:
            by_agent[e.agent_name] = {'total': 0, 'flagged': 0, 'blocked': 0, 'avg_score': 0}
        by_agent[e.agent_name]['total'] += 1
        if e.verdict == 'flagged':
            by_agent[e.agent_name]['flagged'] += 1
        elif e.verdict == 'blocked':
            by_agent[e.agent_name]['blocked'] += 1
            
    for name, stats in by_agent.items():
        agent_events = [e for e in events if e.agent_name == name]
        stats['avg_score'] = sum(e.threat_score for e in agent_events) / len(agent_events)
    
    return {
        'total': len(events),
        'by_verdict': by_verdict,
        'by_category': by_category,
        'by_agent': by_agent,
    }

@router.get('/timeline')
async def get_audit_timeline(
    experiment_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Timeline of significant audit events for visualization."""
    query = select(AuditEvent).where(
        AuditEvent.verdict.in_(['flagged', 'blocked'])
    ).order_by(AuditEvent.cycle_number)
    if experiment_id:
        query = query.where(AuditEvent.experiment_id == experiment_id)
    result = await db.execute(query)
    events = result.scalars().all()
    
    return {
        'timeline': [
            {
                'cycle': e.cycle_number,
                'agent_name': e.agent_name,
                'action_type': e.action_type,
                'verdict': e.verdict,
                'threat_score': e.threat_score,
                'threat_category': e.threat_category,
                'llm_reasoning': e.llm_reasoning,
            }
            for e in events
        ]
    }
