# Agent Auditor — Implementation Tasks

## Component 1: Audit Engine Core
- [x] `auditor/__init__.py` — Package init
- [x] `auditor/config.py` — AuditorConfig dataclass
- [x] `auditor/models.py` — AuditVerdict, AuditResult, ThreatCategory dataclasses
- [x] `auditor/context_collector.py` — Agent context aggregation
- [x] `auditor/rule_auditor.py` — 10 financial market rules
- [x] `auditor/stat_auditor.py` — Statistical anomaly detection
- [x] `auditor/llm_auditor.py` — LLM-based intent analysis
- [x] `auditor/audit_cache.py` — Security query cache (Once/Task/Universal)
- [x] `auditor/threat_scorer.py` — ThreatSense score calculation
- [x] `auditor/trade_gate.py` — Main orchestrator

## Component 2: Database & API
- [x] `backend/app/models/audit.py` — AuditEvent + AuditSummary models
- [x] `backend/app/routes/audit.py` — Audit REST endpoints + WebSocket
- [x] Register audit router in `backend/app/main.py`
- [ ] DB migration for audit tables

## Component 3: Integration
- [ ] Instrument `agents/run.py` — Trade Gate interception
- [ ] Instrument `experiments/run_experiment.py` — Audit integration + report generation
- [ ] `auditor/analysis.py` — Post-experiment audit analysis

## Component 4: Frontend
- [ ] `frontend/src/pages/AuditDashboard.tsx` — Audit dashboard page
- [ ] `frontend/src/services/auditApi.ts` — Audit API client
- [ ] Register route in `frontend/src/App.tsx`

## Verification
- [ ] Test rule auditor with known manipulation scenarios
- [ ] Test full pipeline end-to-end
- [ ] Verify API endpoints return correct data
