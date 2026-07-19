# Audit Annotation Dashboard - Design Document

**Date**: 2026-07-19
**Status**: Design

## 1. Overview

Extend the read-only Audit Dashboard into a **human-annotation tool** that collects ground-truth labels on audited actions, so the auditor's detection accuracy (precision / recall) can be measured. This is the third source in the three-source ground-truth plan (agent `react.think` weak labels + role prior + **sampled manual annotation**); the dashboard owns the manual source.

### Why it's needed

The auditor produces verdicts (allowed / flagged / blocked), but "was this *actually* manipulation?" cannot be read off the auditor's own output — that's circular. To claim the auditor detects accurately, we need an independent human label per audited action and then compare. The current dashboard only *displays* audit events; it cannot capture human judgments.

### What changes

- Current: read-only view of `audit_events` (agent, action, verdict, score, category, reasoning).
- After: each event (or a sampled subset) gets human-annotation controls — "Is this manipulation? [Yes] [No] [Unsure]" + true category + notes — stored independently and used to compute precision/recall against the auditor's verdicts.

## 2. Data Model

### audit_annotations (new table)

One row per (event, annotator) — a separate table, not a column on `audit_events`, so multiple annotators can label the same event (needed for inter-annotator agreement) and audit data stays clean.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| audit_event_id | FK → audit_events | The event being labeled |
| label | ENUM | `manipulation` / `legit` / `unsure` (the human ground truth) |
| true_category | VARCHAR \| null | If manipulation: the real category (pump_dump, coordinated_manipulation, …) |
| annotator_id | VARCHAR | Who labeled it (for agreement / provenance) |
| notes | TEXT \| null | Free-text rationale |
| created_at | DateTime | Timestamp |

Unique on `(audit_event_id, annotator_id)` so one annotator has one label per event (re-labeling updates).

## 3. Backend API

- `POST /api/audit/events/{id}/annotate` — body `{label, true_category?, annotator_id, notes?}`; upserts an `audit_annotations` row.
- `GET /api/audit/events?needs_annotation=1&strata=allowed,flagged,blocked&per_stratum=N` — returns a **stratified sample** of events for labeling (see §5).
- `GET /api/audit/evaluation` — computes the confusion matrix + precision/recall/kappa from annotations vs auditor verdicts (§6).

Annotation write endpoints should be auth'd to a human user (not agent keys).

## 4. Dashboard UI

Two modes on the `/audit` page (or a sibling `/audit/annotate`):

1. **Monitor mode** (existing): live read-only stream of verdicts.
2. **Annotation mode** (new): work through a sample; for each event show the context needed to judge and collect a label.

Each annotation card shows:
- The **action** (type, asset, amount, direction).
- The agent's **stated reasoning** (ReAct observe/think/plan) — the strongest signal.
- **Relevant messages** (public + the agent's DMs in the window).
- Controls: `Manipulation? [Yes] [No] [Unsure]`, category dropdown (enabled if Yes), notes box.
- A short **codebook** reminder inline (what counts as manipulation vs legit).

## 5. Methodological Requirements (do not skip)

**① Blind labeling — avoid anchoring bias.** If the annotator sees the auditor's verdict/reasoning first, they anchor to it and agreement is inflated (they rubber-stamp the auditor). The dashboard must support a **blind mode**: hide the auditor's verdict, score, category, and reasoning during labeling, and reveal them only after the human commits a label. This makes the human label genuinely independent.

**② Stratified sampling — so precision AND recall are both measurable.**
- **Precision** (false-positive / over-blocking rate) needs a sample of **flagged/blocked** events → what fraction the auditor caught are truly manipulation.
- **Recall** (miss rate) needs a sample of **allowed** events → what fraction the auditor let through were actually manipulation.
- Therefore sample **across all three verdicts**, not just the flagged ones. Sampling only flagged events makes recall uncomputable.

**③ Multiple annotators + agreement.** Label a subset with ≥2 independent annotators and report Cohen's kappa, to show "manipulation" is a reproducible judgment (reviewers will ask). The schema (row per event×annotator) supports this.

**④ A written codebook.** Define up front what counts as manipulation (pump & dump, front-running, wash trading, rug pull, coordinated schemes, deceptive messaging) vs legit (genuine arbitrage, market-making liquidity, retail FOMO as *victim* not perpetrator). Show it in the UI and include it in the paper's methods.

## 6. Producing the Metric

With human labels in hand, the evaluation view builds the confusion matrix (auditor verdict vs human label), treating flagged **or** blocked as the auditor's "positive":

| | human = manipulation | human = legit |
|---|---|---|
| **auditor = flagged/blocked** | TP | FP |
| **auditor = allowed** | FN | TN |

- Precision = TP / (TP + FP) — how much of what the auditor caught was real (over-regulation cost lives here).
- Recall = TP / (TP + FN) — how much real manipulation the auditor caught (misses live here).
- Optionally per-category precision/recall, and precision/recall separately for **blocked** vs **flagged** (blocked is the high-confidence subset).

Note the enforcement confound: in `block_and_flag`, a blocked action did not execute, so its downstream outcome is unobservable — human labeling judges the *action's intent*, which is fine for precision/recall; "damage prevented" still requires cross-arm comparison (C0 vs auditor-on), not within-run.

## 7. Integration with the Three-Source Ground Truth (reduce human effort)

Human annotation is expensive; use the two automatic sources to minimize it:
- **Auto weak labels**: agent `react.think` keyword/intent signal + role prior (whale/shill actions have higher manipulation prior; retail actions lower).
- **Prioritize** for human labeling the events where the auto labels and the auditor **disagree**, or where the auditor is **low-confidence** — the informative, ambiguous cases. High-confidence agreements among all sources can be trusted without a human.
- Target roughly **100–200 labeled events per experiment condition** (stratified), which is enough for meaningful precision/recall; only the gray-zone subset needs human eyes.

## 8. Phasing

- **v1 (minimal)**: `audit_annotations` table + `POST …/annotate` + per-row Yes/No/Unsure buttons in the dashboard (blind mode). Just capture labels.
- **v2**: stratified sampling endpoint + evaluation view (confusion matrix, precision/recall).
- **v3**: multi-annotator + Cohen's kappa; auto-weak-label pre-fill and disagreement-based prioritization.

## 9. Relationship to Existing Code

- **Reuses**: the `audit_events` table + `/api/audit/*` routes (`backend/app/routes/audit.py`), the React `AuditDashboard` page (`frontend/src/pages/AuditDashboard.tsx`).
- **New**: `audit_annotations` model + migration, annotate/sample/evaluation endpoints, an annotation view in the frontend.
- **Related**: the ground-truth scheme referenced in `2026-07-16-anti-manipulation-mechanism-design.md` (§6 metrics) and `2026-07-18-discovery-auditor-agent-loop.md`; this dashboard is how the "sampled manual annotation" source is actually collected.
