# Discovery Auditor Agent Loop - Implementation Plan

> **For Claude:** Implement this plan task-by-task. Each task lists the files to touch, steps with code, a verification, and a commit. Focus is **v1 (observe-only discovery)**; v2/v3 tasks are scaffolded at the end.

**Goal:** Add a slow-layer discovery agent that runs every K cycles, mines the accumulated market record across all agents/cycles, and persists named, evidenced manipulation patterns — including novel ones not in the recognizer's fixed taxonomy. Produces the RQ1 artifact: a catalog of emergent behaviors.

**Architecture:** A new `discovery/` module (runs inside the experiment runner) reads history via the backend API + the recognizer's `audit_events`, calls an LLM to mine patterns, and persists them to new `discovered_patterns` / `discovery_runs` tables via backend endpoints. It never gates execution — enforcement stays with the per-action recognizer. See the design doc for rationale.

**Tech Stack:** Python 3.11 / FastAPI / async SQLAlchemy / Alembic / PostgreSQL / Anthropic SDK

**Design Doc:** `docs/plans/2026-07-18-discovery-auditor-agent-loop.md`

---

## Task 1: Discovery Tables + Models

**Files:**
- Create: `backend/app/models/discovery.py`
- Create: `backend/alembic/versions/<rev>_add_discovery_tables.py`

**Step 1: Models** (`discovery.py`)

Same `Base` as the audit models (`from app.database import Base`).

```python
class DiscoveredPattern(Base):
    __tablename__ = 'discovered_patterns'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(String(100), index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    mechanism = Column(Text)
    involved_agents = Column(JSON)          # ["GoldenWhale", "CryptoGuru"]
    evidence = Column(JSON)                 # [{cycle, agent, action, quote}]
    is_novel = Column(Boolean, default=True)
    known_category = Column(String(50), nullable=True)
    occurrence_count = Column(Integer, default=1)
    first_seen_cycle = Column(Integer, nullable=True)
    proposed_rule = Column(JSON, nullable=True)
    status = Column(String(20), default='proposed')  # proposed/confirmed/merged/rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiscoveryRun(Base):
    __tablename__ = 'discovery_runs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(String(100), index=True)
    cycle = Column(Integer, nullable=False)
    window_start_cycle = Column(Integer, nullable=False)
    patterns_found = Column(Integer, default=0)
    novel_count = Column(Integer, default=0)
    llm_reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Step 2: Migration** — `down_revision = 'f3a8b1c2d4e5'` (the audit-tables head). Follow the `f3a8b1c2d4e5_add_audit_tables.py` style, including the `if 'discovered_patterns' in inspector.get_table_names(): return` skip-guard.

**Step 3: Verify**

Run: `docker compose exec backend alembic upgrade head`
Expected: `discovered_patterns` and `discovery_runs` tables created.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: discovered_patterns + discovery_runs tables"
```

---

## Task 2: Backend Persistence + Read Endpoints

**Files:**
- Create: `backend/app/routes/discovery.py`
- Modify: `backend/app/main.py` (include the router)

**Step 1: Router** (`discovery.py`) — mirror `routes/audit.py`.

```python
router = APIRouter(prefix='/api/discovery', tags=['discovery'])

class PatternCreate(BaseModel):
    experiment_id: str | None = None
    name: str
    description: str = ''
    mechanism: str = ''
    involved_agents: list = []
    evidence: list = []
    is_novel: bool = True
    known_category: str | None = None
    first_seen_cycle: int | None = None
    proposed_rule: dict | None = None

@router.post('/patterns')          # create OR increment occurrence if a same-name
                                   # pattern already exists in this experiment
async def upsert_pattern(body: PatternCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(DiscoveredPattern).where(
        DiscoveredPattern.experiment_id == body.experiment_id,
        DiscoveredPattern.name == body.name))
    if existing:
        existing.occurrence_count += 1
        existing.evidence = (existing.evidence or []) + (body.evidence or [])
        await db.commit()
        return {'id': str(existing.id), 'status': 'incremented'}
    p = DiscoveredPattern(**body.model_dump())
    db.add(p); await db.commit()
    return {'id': str(p.id), 'status': 'created'}

@router.get('/patterns')           # list current library (for the agent's next pass + UI)
async def list_patterns(experiment_id: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(DiscoveredPattern).order_by(desc(DiscoveredPattern.occurrence_count))
    if experiment_id:
        q = q.where(DiscoveredPattern.experiment_id == experiment_id)
    rows = (await db.execute(q)).scalars().all()
    return {'patterns': [ ... serialize ... ], 'count': len(rows)}

@router.post('/runs')              # record a discovery pass
async def create_run(...): ...

@router.get('/runs')               # list passes
async def list_runs(...): ...
```

Persistence is auth-free (read/observability layer), matching the GET audit routes. The upsert-by-name keeps the library de-duplicated across passes (design doc step 4).

**Step 2: Wire router** (`main.py`)

```python
from app.routes.discovery import router as discovery_router
app.include_router(discovery_router)
```

**Step 3: Verify** — POST a pattern, GET it back; POST same name again → `incremented`.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: discovery persistence + read API (/api/discovery/*)"
```

---

## Task 3: Observation Digest Builder

**Files:**
- Create: `discovery/__init__.py`
- Create: `discovery/digest.py`

**Step 1: Digest** (`digest.py`) — build a compact, token-bounded window summary from data the runner/backend already have. Sources: `audit_events` (via `/api/audit/events?cycle_min=&cycle_max=`, which already carry `agent_reasoning` + `action_details` + verdict), public+DM messages (`/api/messages/history`), and portfolio deltas (`get_agent_state` per agent at window start vs end).

```python
def build_digest(base_url, window_start, window_end, agent_keys) -> dict:
    events = _get(f"{base_url}/api/audit/events?cycle_min={window_start}&cycle_max={window_end}&limit=1000")["events"]
    # Per-agent action timeline (compact): agent -> [(cycle, action_type, asset, verdict)]
    # ReAct intent: pull distinct agent_reasoning per (agent, cycle)
    # Messages: public + DM over the window
    # Portfolio delta: per agent, value_end - value_start
    return {
        "window": [window_start, window_end],
        "actions_by_agent": {...},
        "reasoning_by_agent": {...},   # observe/think/plan snippets
        "messages": [...],
        "pnl_delta": {...},
    }
```

Keep it summarized (truncate reasoning, cap message count) — the digest, not raw dumps, controls token cost.

**Step 2: Verify** — call `build_digest` over the last run's cycle range against the live backend; print sizes and confirm it's well under the model context.

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: discovery observation digest builder"
```

---

## Task 4: Discovery Agent

**Files:**
- Create: `discovery/prompt.py`
- Create: `discovery/discovery_agent.py`

**Step 1: System prompt** (`prompt.py`) — a market-abuse researcher, not a checklist auditor. Explicitly: the known-pattern list is **non-exhaustive**; novel tactics are the most valuable finding; every pattern must cite concrete evidence (cycle + action + message quote). Output schema:

```json
{
  "patterns": [
    {"name": "...", "description": "...", "mechanism": "...",
     "involved_agents": ["..."],
     "evidence": [{"cycle": 7, "agent": "GoldenWhale", "action": "v3_swap", "quote": "..."}],
     "is_novel": true, "known_category": null,
     "proposed_rule": {"signal": "...", "condition": "...", "severity": 0.8}}
  ]
}
```

**Step 2: Agent** (`discovery_agent.py`)

```python
class DiscoveryAgent:
    def __init__(self, base_url, model="claude-sonnet-4-6"):  # stronger model than the recognizer
        self.base_url = base_url
        self.model = os.environ.get("DISCOVERY_LLM_MODEL", model)

    def run(self, experiment_id, cycle, window_start, agent_keys) -> dict:
        digest = build_digest(self.base_url, window_start, cycle, agent_keys)
        library = _get(f"{self.base_url}/api/discovery/patterns?experiment_id={experiment_id}")["patterns"]
        prompt = build_prompt(digest, library)          # includes current library names+descriptions
        raw = self._call_llm(prompt)
        result = parse_json_lenient(raw)                # reuse the auditor's tolerant parser
        patterns = result.get("patterns", [])
        for p in patterns:
            p["experiment_id"] = experiment_id
            p.setdefault("first_seen_cycle", window_start)
            _post(f"{self.base_url}/api/discovery/patterns", p)
        _post(f"{self.base_url}/api/discovery/runs", {
            "experiment_id": experiment_id, "cycle": cycle,
            "window_start_cycle": window_start,
            "patterns_found": len(patterns),
            "novel_count": sum(1 for p in patterns if p.get("is_novel")),
            "llm_reasoning": result.get("summary", ""),
        })
        return {"patterns_found": len(patterns)}
```

Reuse `LLMAuditor._extract_json_obj` (the tolerant parser) so Haiku/Sonnet JSON malformations don't drop discoveries. Novelty in v1 is the LLM's own judgment against the library passed in the prompt; embedding-similarity dedup is a later enhancement.

**Step 3: Verify** — run `DiscoveryAgent.run(...)` over the completed 5-cycle experiment's range; confirm rows appear in `discovered_patterns` and one `discovery_runs` row.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: discovery agent (mine → characterize → persist)"
```

---

## Task 5: Runner Hook (every K cycles)

**Files:**
- Modify: `experiments/run_experiment.py`

**Step 1: Instantiate + gate**

```python
from discovery.discovery_agent import DiscoveryAgent
DISCOVERY_ENABLED = os.environ.get("DISCOVERY_ENABLED", "0") == "1"
DISCOVERY_K = int(os.environ.get("DISCOVERY_K", "10"))
discovery_agent = DiscoveryAgent(BASE_URL) if DISCOVERY_ENABLED else None
```

**Step 2: Hook after the last phase each cycle** — a "Phase 5: Discovery", after Phase 4 (PoolMaster), only when enabled and `cycle % DISCOVERY_K == 0`:

```python
if discovery_agent and cycle % DISCOVERY_K == 0:
    window_start = max(1, cycle - DISCOVERY_K + 1)
    print(f"\n  ── Phase 5: Discovery (cycles {window_start}-{cycle}) ──")
    try:
        res = discovery_agent.run(exp_dir.name, cycle, window_start, keys)
        print(f"  [discovery] {res['patterns_found']} patterns")
    except Exception as e:
        print(f"  [discovery error] {e}")   # never break the run
```

**Step 3: Verify** — run `DISCOVERY_ENABLED=1 DISCOVERY_K=2 python3 experiments/run_experiment.py --cycles 4 ...`; confirm two discovery passes fire (cycles 2 and 4) and patterns persist.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: wire discovery agent into runner (Phase 5, every K cycles)"
```

---

## Task 6: Discovery Report + (optional) Frontend

**Files:**
- Create: `experiments/analyze_discovery.py`
- Optional: `frontend/src/pages/DiscoveryDashboard.tsx` + route

**Step 1: Report** — over a run, list discovered patterns sorted by occurrence, split novel vs known, with evidence counts and first-seen cycle. This is the RQ1 deliverable table.

**Step 2 (optional): Frontend** — a `/discovery` page mirroring the audit dashboard, reading `/api/discovery/patterns`. Same login gate applies.

**Step 3: Verify** — run the report over a `DISCOVERY_ENABLED=1` experiment; confirm a readable emergent-behavior catalog.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: discovery analysis report"
```

---

## Later Phases (scaffolded)

### v2 — Category injection (feed discovery → recognizer)

**Files:** `auditor/llm_auditor.py`

Make `AUDITOR_SYSTEM_PROMPT` dynamic: at `TradeGate` init (or per cycle), fetch `confirmed` patterns from `/api/discovery/patterns` and append their `name: description` to the recognizer's category list, so the per-action judge can label newly-discovered patterns. Measure whether flag/block rate on those patterns rises after injection.

### v3 — Gated rule synthesis

**Files:** `auditor/rule_auditor.py`, a validation script

Compile a stabilized pattern's `proposed_rule` into a candidate `RuleAuditor` heuristic in `status='proposed'`. Before activating, run it over held-out `audit_events` and measure precision; only `confirmed` rules become active. Prevents auto-generated rules from over-firing.

### v4 — Wire to Regulator

Expose `/api/discovery/patterns` as an observation channel to the Regulator Agent Loop, so it can act on named, evidenced emergent patterns (e.g. "new coordinated tactic between X and Y → deploy T3 on that pair") rather than only aggregate threat scores.

---

## Summary

| Task | Deliverable |
|------|-------------|
| 1 | `discovered_patterns` + `discovery_runs` tables |
| 2 | `/api/discovery/*` persistence + read API |
| 3 | Observation digest builder |
| 4 | Discovery agent (mine → characterize → persist) |
| 5 | Runner hook (Phase 5, every K cycles) |
| 6 | Discovery report (+ optional frontend) |
| v2–v4 | Category injection → gated rule synthesis → wire to Regulator |

**Phasing**: Tasks 1–6 deliver v1 (observe-only discovery = the RQ1 emergent-behavior catalog). v2–v4 close the discovery→recognition→regulation loop incrementally, each behind its own flag and validation.
