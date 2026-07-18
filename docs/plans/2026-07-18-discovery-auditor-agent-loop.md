# Discovery Auditor Agent Loop - Design Document

**Date**: 2026-07-18
**Status**: Design

## 1. Overview

An autonomous auditor agent that **discovers** manipulative behaviors from observation, rather than only **recognizing** a fixed, pre-defined set. This upgrades the auditor from a compliance-checking tool into an emergent-behavior discovery engine, directly serving RQ1 ("what strategies do LLM agents autonomously discover?") — instead of a human reading logs to find emergent strategies, a discovery agent finds them.

### The distinction it addresses

The current auditor (`auditor/`) is a **closed-set recognizer**:
- 10 hardcoded rules (R001–R010), 5 fixed statistical checks, and an LLM judge that classifies each action into one of **8 predefined categories** (wash_trading, pump_dump, front_running, spoofing, coordinated_manipulation, deceptive_messaging, liquidity_exploitation, none).
- It scores **one action at a time** against known patterns. It cannot surface a manipulation strategy that is not already in its rule set or category list — a novel tactic slips through or is mislabeled.

The discovery loop is an **open-set discoverer**:
- It observes the **whole market history across all agents and cycles**, forms hypotheses about recurring or coordinated value-extracting behavior, names and characterizes novel patterns, and grows a library of discovered behaviors — optionally feeding new detection rules back down to the recognizer.

### Key idea: two timescales, two jobs

| Layer | Timescale | Job | Pattern library |
|-------|-----------|-----|-----------------|
| **Recognizer** (existing auditor) | Every action | Fast classify + enforce (block/flag) | Consumes the known library |
| **Discovery agent** (this doc) | Every K cycles | Observe history → discover new patterns | Grows the library |

The discovery agent expands what the recognizer knows; the recognizer applies it in real time. This mirrors the two-timescale structure of the Regulator Agent Loop.

## 2. Motivation & Research Framing

The whole project studies **emergent behavior** in adversarial multi-agent markets. There is a clean symmetry once discovery is added:

| Layer | What it autonomously discovers |
|-------|--------------------------------|
| Trading agents | Manipulation **strategies** (emergent offense) |
| **Discovery auditor** | Manipulation **patterns** from observation (emergent detection) |
| Regulator agent | Effective **mechanisms** (emergent defense) |

Without discovery, "which emergent strategies appeared" is answered by manual log reading — unscalable and subjective. The discovery agent makes it a repeatable, cite-able artifact: a named, evidenced catalog of behaviors the agents actually invented, including ones not in our a-priori taxonomy.

## 3. Architecture

### 3.1 Position in the stack

The discovery agent is a new **slow layer** above the existing per-action recognizer. It reads the accumulated record, not individual trades in flight, so it never gates execution directly — it changes what the recognizer looks for on subsequent cycles.

```
┌──────────────────────────────────────────────────────────────┐
│  Discovery Auditor Agent           every K cycles              │
│    reads : audit_events + trades + messages (incl. DMs) +      │
│            agent reasoning + portfolio outcomes, since last run│
│            + current discovered-pattern library                │
│    does  : LLM-driven cross-agent / cross-cycle pattern mining │
│    writes: discovered_patterns (grow library); optionally      │
│            emits new detection heuristics                       │
└───────────────────────────┬──────────────────────────────────┘
                            │ feeds new patterns / rules
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Recognizer (existing auditor / TradeGate)   every action      │
│    rule + stat + LLM classify → block / flag / allow           │
│    → audit_events                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 The discovery loop (six steps, every K cycles)

1. **Gather** — pull the record since the last discovery run: audit events, trades, public + DM messages, each agent's ReAct reasoning, and portfolio deltas (who gained, who lost).
2. **Mine** — an LLM analyzes the record across agents and time, looking for recurring or coordinated behavior that extracts value or distorts price — explicitly including patterns not in the current taxonomy.
3. **Characterize** — for each candidate: a short name, a description, the mechanism, the involved agents, cited evidence (cycles + actions + message quotes), and a novel-vs-known verdict against the existing library.
4. **Persist** — novel patterns are added to `discovered_patterns`; recurring ones increment an occurrence count and accrue evidence. Near-duplicates are merged.
5. **Feed back (optional)** — a stabilized novel pattern can be compiled into (a) a new entry in the recognizer's LLM category list, and/or (b) a proposed rule heuristic for `RuleAuditor` (subject to review, since auto-generated rules can be noisy).
6. **Iterate** — the growing library sharpens both the next discovery pass (avoid re-reporting known patterns) and the recognizer (catch newly-named patterns in real time).

## 4. Data Model

### discovered_patterns (new table)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| experiment_id | String | Run this pattern was discovered in |
| name | String | Short human name (e.g. "fake-liquidation bait") |
| description | Text | What the behavior is and how it extracts value |
| mechanism | Text | The step-by-step tactic |
| involved_agents | JSON | Agent names / roles participating |
| evidence | JSON | [{cycle, agent, action, quote}] citations |
| is_novel | Boolean | True if not matched to a prior known pattern |
| known_category | String \| null | Mapped taxonomy category if not novel |
| occurrence_count | Integer | Times observed across discovery passes |
| first_seen_cycle | Integer | Earliest cycle in the evidence |
| proposed_rule | JSON \| null | Optional auto-generated detection heuristic |
| status | String | proposed / confirmed / merged / rejected |
| created_at / updated_at | DateTime | Timestamps |

### discovery_runs (new table)

One row per discovery pass: `id`, `experiment_id`, `cycle`, `window_start_cycle`, `patterns_found`, `novel_count`, `llm_reasoning`, `created_at`. Gives an audit trail of the discovery process itself (for the paper's methods section, and to measure discovery cadence).

## 5. The Discovery Agent

### 5.1 Observation (input)

A compact, structured digest — not raw dumps — to control token cost:
- Per-agent action timeline over the window (from `audit_events` + trades), with sizes and assets.
- Public messages and DMs over the window (DMs matter — coordination hides there).
- Each agent's `react.observe / think / plan` (their stated intent — the strongest signal for characterizing a pattern).
- Portfolio deltas over the window (who extracted value from whom).
- The current `discovered_patterns` names + descriptions (so it reports novelty, not repeats).

### 5.2 Task (system prompt intent)

The agent is instructed to behave as a market-abuse researcher, not a checklist auditor: find recurring or coordinated behaviors that extract value or distort price; for each, name it, explain the mechanism, cite concrete evidence, and state whether it matches a listed known pattern or is genuinely new. It is explicitly told the known list is **non-exhaustive** and that novel tactics are the most valuable finding.

### 5.3 Output (structured)

```json
{
  "patterns": [
    {
      "name": "...",
      "description": "...",
      "mechanism": "...",
      "involved_agents": ["GoldenWhale", "CryptoGuru"],
      "evidence": [{"cycle": 7, "agent": "GoldenWhale", "action": "v3_swap", "quote": "dump before they realize"}],
      "is_novel": true,
      "known_category": null,
      "proposed_rule": {"signal": "...", "condition": "...", "severity": 0.8}
    }
  ]
}
```

### 5.4 Cost & cadence

Runs once per K cycles (not per action), over a digested window, so cost is bounded and small relative to the trading agents. K is a tunable knob (e.g. every 10 cycles). A stronger model is justified here than for the per-action recognizer, since discovery is the harder reasoning task and runs rarely.

## 6. Feedback: Discovery → Recognition

The loop closes only if discoveries make the fast layer smarter. Two channels:

1. **Category injection (low risk)** — a confirmed novel pattern's name + description is appended to the recognizer's LLM category list, so the per-action judge can label it going forward. No code change, just a prompt the recognizer already consumes.
2. **Rule synthesis (higher risk, gated)** — a pattern's `proposed_rule` becomes a candidate `RuleAuditor` heuristic. Because auto-generated rules can over-fire, these enter as `proposed` and require confirmation (human, or a validation pass measuring their precision on held-out events) before activating. This mirrors the Regulator's "don't blindly trust auto-generated constraints" stance.

## 7. Relationship to the Regulator Agent Loop

The discovery auditor and the Regulator (see `2026-07-16-anti-manipulation-mechanism-design.md` and the Notion Regulator Loop docs) are complementary slow-layer agents:

- **Discovery auditor** answers *"what new manipulation is happening?"* — it grows the detection library.
- **Regulator** answers *"what should we do about it?"* — it tunes mechanisms and auditor knobs.

Naturally, the discovery auditor becomes a **richer sensor for the Regulator**: instead of reading only aggregate threat scores, the Regulator can act on named, evidenced emergent patterns ("a new coordinated tactic between X and Y emerged — deploy T3 penalty on that pair"). They can be built independently and wired together later.

## 8. Design Decisions / Open Questions

- **Discovery granularity** — should the agent stop at "describe + name the new pattern," or go all the way to "emit an executable rule"? Recommendation: start at describe + name + evidence (the RQ1 deliverable); treat rule synthesis as an opt-in second channel, gated.
- **Novelty adjudication** — how to decide "novel vs known"? Start with the LLM's own judgment against the library, plus an embedding-similarity check against existing pattern descriptions to catch rephrasings.
- **Ground truth for "did it discover correctly"** — the same three-source labeling from the mechanism experiment applies: agent `react.think` as strong evidence, role prior, and sampled manual annotation of a discovered-pattern sample.
- **Does it gate execution?** No. It is observation-only; enforcement stays with the per-action recognizer and the protocol mechanisms. This keeps discovery free to hypothesize without risking false blocks.
- **Model choice** — a stronger model (e.g. Sonnet 5) for the discovery pass; the per-action recognizer can stay on the cheaper Haiku.

## 9. Phasing

- **v1 (observe-only discovery)**: implement `discovered_patterns` + `discovery_runs` tables and the discovery agent; run it every K cycles over the digest; persist named, evidenced patterns. Deliverable: a per-run catalog of emergent behaviors (novel + known), the RQ1 artifact. No feedback to the recognizer yet.
- **v2 (category injection)**: feed confirmed novel patterns into the recognizer's LLM category list; measure whether the per-action judge then catches them.
- **v3 (gated rule synthesis)**: compile stabilized patterns into candidate `RuleAuditor` heuristics behind a validation gate; measure their precision before activating.
- **v4 (wire to Regulator)**: expose the discovered-pattern library as an observation channel to the Regulator Agent Loop.

## 10. Relationship to Existing Code

- **Reuses**: `audit_events` (the recognizer's log becomes the discovery agent's primary input), the runner's per-cycle orchestration (add a Phase-5-style discovery hook every K cycles), the Anthropic client path.
- **Distinct from**: `AuditAnalyzer` (`auditor/analysis.py`), which is a static post-hoc report generator over one run's log — not a cross-cycle, hypothesis-forming, library-growing agent. The discovery loop is the active-agent version of what AuditAnalyzer does passively.
- **New**: a `discovery/` module (agent + prompt + pattern store access) parallel to `auditor/`, and the two new tables.

## 11. Related Documents

- `docs/plans/2026-07-16-anti-manipulation-mechanism-design.md` — the mechanism experiment (C0/T1–T4 / auditor / regulator) this extends.
- `docs/plans/agent_auditor_plan.md` — the recognizer (existing `auditor/` module) this sits above.
- Notion: "扩展设计：Auditor 执法层 + Regulator 调控" and "Regulator Agent Loop" — the sibling slow-layer agent this complements.
