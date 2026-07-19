"""API routes for the Discovery Auditor Agent Loop."""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.discovery import DiscoveredPattern, DiscoveryRun

router = APIRouter(prefix='/api/discovery', tags=['discovery'])


class PatternCreate(BaseModel):
    experiment_id: Optional[str] = None
    name: str
    description: str = ''
    mechanism: str = ''
    involved_agents: list = []
    evidence: list = []
    is_novel: bool = True
    known_category: Optional[str] = None
    first_seen_cycle: Optional[int] = None
    proposed_rule: Optional[dict] = None


class RunCreate(BaseModel):
    experiment_id: Optional[str] = None
    cycle: int
    window_start_cycle: int
    patterns_found: int = 0
    novel_count: int = 0
    llm_reasoning: Optional[str] = None


def _serialize_pattern(p: DiscoveredPattern) -> dict:
    return {
        'id': str(p.id),
        'experiment_id': p.experiment_id,
        'name': p.name,
        'description': p.description,
        'mechanism': p.mechanism,
        'involved_agents': p.involved_agents,
        'evidence': p.evidence,
        'is_novel': p.is_novel,
        'known_category': p.known_category,
        'occurrence_count': p.occurrence_count,
        'first_seen_cycle': p.first_seen_cycle,
        'proposed_rule': p.proposed_rule,
        'status': p.status,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post('/patterns')
async def upsert_pattern(body: PatternCreate, db: AsyncSession = Depends(get_db)):
    """Create a discovered pattern, or increment occurrence + merge evidence if a
    same-name pattern already exists in this experiment (de-dupes across passes)."""
    existing = await db.scalar(select(DiscoveredPattern).where(
        DiscoveredPattern.experiment_id == body.experiment_id,
        DiscoveredPattern.name == body.name))
    if existing:
        existing.occurrence_count = (existing.occurrence_count or 1) + 1
        existing.evidence = (existing.evidence or []) + (body.evidence or [])
        # keep the richer description/mechanism if the new one is longer
        if body.description and len(body.description) > len(existing.description or ''):
            existing.description = body.description
        if body.mechanism and len(body.mechanism) > len(existing.mechanism or ''):
            existing.mechanism = body.mechanism
        await db.commit()
        return {'id': str(existing.id), 'status': 'incremented',
                'occurrence_count': existing.occurrence_count}

    p = DiscoveredPattern(
        experiment_id=body.experiment_id, name=body.name, description=body.description,
        mechanism=body.mechanism, involved_agents=body.involved_agents, evidence=body.evidence,
        is_novel=body.is_novel, known_category=body.known_category,
        first_seen_cycle=body.first_seen_cycle, proposed_rule=body.proposed_rule)
    db.add(p)
    await db.commit()
    return {'id': str(p.id), 'status': 'created'}


@router.get('/patterns')
async def list_patterns(experiment_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(DiscoveredPattern).order_by(desc(DiscoveredPattern.occurrence_count),
                                           desc(DiscoveredPattern.created_at))
    if experiment_id:
        q = q.where(DiscoveredPattern.experiment_id == experiment_id)
    rows = (await db.execute(q)).scalars().all()
    return {'patterns': [_serialize_pattern(p) for p in rows], 'count': len(rows)}


@router.post('/runs')
async def create_run(body: RunCreate, db: AsyncSession = Depends(get_db)):
    run = DiscoveryRun(
        experiment_id=body.experiment_id, cycle=body.cycle,
        window_start_cycle=body.window_start_cycle, patterns_found=body.patterns_found,
        novel_count=body.novel_count, llm_reasoning=body.llm_reasoning)
    db.add(run)
    await db.commit()
    return {'id': str(run.id), 'status': 'recorded'}


@router.get('/runs')
async def list_runs(experiment_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(DiscoveryRun).order_by(DiscoveryRun.cycle)
    if experiment_id:
        q = q.where(DiscoveryRun.experiment_id == experiment_id)
    rows = (await db.execute(q)).scalars().all()
    return {'runs': [{'id': str(r.id), 'cycle': r.cycle,
                      'window_start_cycle': r.window_start_cycle,
                      'patterns_found': r.patterns_found, 'novel_count': r.novel_count,
                      'llm_reasoning': r.llm_reasoning,
                      'created_at': r.created_at.isoformat() if r.created_at else None}
                     for r in rows], 'count': len(rows)}
