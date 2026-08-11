# Research Proposal: Repositioning "Your Agent Says Yes" for AgenticOS @ NeurIPS 2026

This document plans a submission of *"Your Agent Says Yes: Emergent Market
Misconduct in Agentic Trading"* to
[AgenticOS: Co-designing Systems and ML Foundations of an OS Layer for
Agentic AI](https://agentic-fmos.github.io/), a NeurIPS 2026 workshop
(Sydney). Same three-part structure as the Trustworthy AI for Good proposal:
what the paper needs to change, a research plan, and the experiments that
plan implies. The reframe required here is larger than for the safety
workshop — this venue wants systems contributions, and the paper as written
is an empirical safety study. Section 1.1 makes the case for why the paper
still fits, and what has to change for that fit to be genuine rather than
cosmetic.

## 0. Workshop constraints (source of truth for everything below)

| Constraint | Value |
|---|---|
| Deadline | August 29, 2026 (AoE) |
| Notification | September 29, 2026 |
| Length | Extended abstract: ≤2 pages technical content. Regular paper: ≤6 pages technical content (refs/appendix unlimited, paper must be self-contained) |
| Template | NeurIPS 2026 formatting guidelines |
| Review | Double-blind (remove names, affiliations, acknowledgments) |
| Status | Non-archival, no formal proceedings; concurrent submission elsewhere allowed if that venue's policy permits |
| Review criteria | Technical novelty, community interest, lessons learned, **AgenticOS relevance** |

Six named topics: (1) Agentic OS foundations & abstractions, (2) memory,
state & storage, (3) resource management & execution, (4) long-horizon &
self-evolving agents, (5) **trust, safety & governance — isolation, access
control, observability, auditability of autonomous agents**, (6) evaluation
& deployment — benchmarks, testbeds, deployment solutions. The workshop also
explicitly welcomes experience reports, deployment lessons, and **negative
results** — worth remembering given several of the paper's own findings are
already framed as "no single aggregate direction" / "specific winners are
unstable."

## 1. What the paper still needs to change

### 1.1 This needs a real reframe, not a find-and-replace
The AAAI draft is written as a security/safety empirical study: the unit of
contribution is the finding (class-dependent containment, role-level
redistribution, etc.), and the virtual exchange and wallet policy are
*instruments* for producing those findings. AgenticOS's explicit review
criterion is "AgenticOS relevance," and its named topics are almost all
systems concepts (abstractions, state, scheduling, isolation) rather than
empirical-safety concepts. Submitting the paper unchanged risks reading as
off-topic. The honest fix is not to bolt on systems vocabulary — it is to
foreground the parts of the existing contribution that already *are* systems
contributions, because there are real ones:

- **The wallet policy is an authorization primitive**, structurally close to
  an OS-level reference monitor or capability check: every financial action
  a proposal, evaluated pre-execution, against a policy that returns
  allow/flag/block. Finding 1's core result — that transaction-local
  authorization does not compose across a sequence of otherwise-valid
  actions — is a specific instance of a general systems-security problem
  (a reference monitor evaluated per-call misses session-level state), not
  a finance-specific one. This is topic (5), directly.
- **The virtual exchange is a testbed.** Section 3's protocol (two
  time-blinded replay windows, two safeguard modes, repeated cells, full
  trace construction linking proposal → verdict → state change → outcome)
  is exactly the kind of reusable evaluation infrastructure topic (6) asks
  for, and it is already open-sourced. The paper currently frames this as
  "methods," which undersells it for this audience.
- **The batch auditor is a scheduling/resource decision.** The
  implementation batches multiple proposals from one agent's turn into a
  single LLM judgment call rather than auditing each action independently —
  this is a real resource-management tradeoff (latency and cost vs.
  per-action isolation) that the current paper does not discuss at all. It
  belongs under topic (3) if surfaced.

Recommendation: keep the empirical findings, but lead the paper with the
systems framing (reference-monitor incompleteness, testbed contribution,
audit-pipeline resource cost), and demote the finance-specific manipulation
taxonomy (pump-and-dump, wash trading, etc.) to supporting detail rather than
the paper's headline. The target reader for this venue is a systems
researcher, not a finance-security researcher.

### 1.2 Pick a length track deliberately
Two very different options here, not a formatting afterthought:
- **2-page extended abstract**: report the reframe (1.1) and the
  strongest single result (Finding 1's persistence-boundary trace, since
  it's the cleanest illustration of "transaction-local checks don't compose")
  plus a pointer to the open testbed. Fastest to produce, lowest risk given
  the deadline, and matches the CFP's stated interest in "visionary ideas...
  or conceptual frameworks" if positioning is emphasized over exhaustive
  results.
- **6-page regular paper**: keep the full experimental matrix (all four
  findings) but reframed per 1.1, plus at least one addition from Section 3
  below to earn "systems experience" or "empirical analysis" credit.
Given the same August 29 deadline as the Trustworthy AI for Good workshop and
the larger reframing burden here, the 2-page track is the lower-risk choice
unless Tier 1/2 work in Section 3 is comfortably on track.

### 1.3 Related work needs an OS/systems anchor, not just a safety anchor
The two papers referenced for the Trustworthy AI for Good proposal — Hammond
et al.'s multi-agent risk taxonomy (arXiv:2502.14143) and *Open Challenges in
Multi-Agent Security* (arXiv:2505.02077) — still support topic (5) here
(both discuss isolation, secure interaction, and auditability of interacting
agents), so they carry over into this submission's related work without
change. But neither is a systems paper, and this venue's other five topics
have no citation coverage yet. **This is a real gap, not something to paper
over**: topics (1)-(4) and (6) (OS abstractions, memory/state architectures,
scheduling for agents, long-horizon/self-evolving agents, benchmarks/
testbeds for agentic systems) each have their own literatures that the
current draft doesn't touch. I have not verified any specific citations for
these — before drafting related work for this section, identify and read
2-4 papers on agent memory/state architecture and agentic evaluation
testbeds specifically (do not fabricate citations here; this needs the same
fetch-and-verify pass done for the other two papers).

### 1.4 Anonymization
Same status as the other workshop: the `anonymous.4open.science` link is
already double-blind-compatible. Re-check camera-ready text for
acknowledgments and any author-identifying infrastructure names before
submission — do this once, for whichever version (this workshop or
Trustworthy AI for Good) is finalized first, and carry the same anonymized
text to the other.

---

## 2. Research plan

Same two source papers as before, reframed for a systems audience plus one
new direction specific to this venue's topics.

**RQ-E2 (carried over, reframed as topic 5 — access control /
auditability).** Does a history-aware wallet policy — one that maintains
state across turns instead of scoring each proposal independently — close
the gap Finding 1 documents? For this venue, frame this explicitly as an
access-control systems question: is a stateless reference-monitor design
(current auditor) fundamentally insufficient for session-scoped agent
authorization, and does adding session state fix it, or only shift where the
gap reappears? This is the strongest crossover experiment between both
workshop submissions — same implementation work, different framing, and now
also touches topic (2) (state) directly since the fix *is* adding a state
layer to the auditor.

**RQ-New1 (topic 3 — resource management under uncertainty).** What does the
batch auditor actually cost, and what does batching trade away? Report
LLM-call count, latency, and estimated cost per cycle for batched
vs. per-action auditing, and check whether batching changes verdict quality
(does judging N proposals in one call miss things a per-action call would
catch?). This is close to free — the data needed (call counts, timings) is
almost certainly already being logged by `run_experiment.py`'s existing
retry/backoff instrumentation — and it is a genuine systems contribution the
current paper has zero coverage of.

**RQ-New2 (topic 6 — evaluation & deployment, testbeds).** Package the
virtual exchange's existing eight-run protocol (two replay windows, two
auditor modes, repeated cells, full trace schema) explicitly as a reusable
benchmark: name the task, define the metrics already used in the paper
(block/flag rate by class, role-level return, cross-agent spread,
rerun-correlation) as a standard reporting protocol, and state what a future
auditor design would need to beat to count as an improvement. This does not
require new experiments — it requires writing the existing methodology
section as a benchmark specification rather than a one-off protocol.

**RQ-New3 (topic 4 — long-horizon & self-evolving agents, stretch).** The
current design resets agent memory between episodes (`--hard-reset`). Topic
(4) explicitly wants "continual adaptation while maintaining safety" —
this is close to RQ-E4 from the Trustworthy AI for Good proposal (iterated
episodes with persistent memory) but reframed around whether the *auditor's*
containment holds up as agents adapt across episodes, not just whether
manipulation strategies strengthen. Treat as a stretch goal given the
implementation cost (persistent memory across episode boundaries is not
currently supported) and the shared deadline with the other submission.

---

## 3. Experiments to add, ranked by cost vs. deadline

### Tier 1 — cheap, do these first
- **RQ-New1 resource-cost reporting.** Almost certainly a data-extraction
  and write-up task, not a new experiment: pull LLM call counts and timing
  from existing run logs (`experiment_logs/*/actions/`,
  `audit_events.csv` timestamps) across the existing eight runs and report
  batched-vs-per-action cost. If per-action-call timing data isn't already
  logged at fine enough granularity, this becomes a Tier 2 item (needs a
  short instrumented rerun).
- **RQ-New2 benchmark packaging.** Writing task, not an experiment: turn
  the existing methodology section (Section 3 of the paper) into an
  explicit benchmark specification with named metrics and a reporting
  protocol. The underlying artifacts (`analysis/analyze_run.py`,
  `sample_data/`, `configs/`) already exist and already compute exactly
  these metrics — this is packaging existing work for a different framing,
  not new work.
- **World C (sideways) addition.** Same rationale as the Trustworthy AI for
  Good proposal — infrastructure already exists (`configs/world_c_*.sh`),
  and a third regime strengthens the testbed's completeness claim for topic
  (6) specifically (a benchmark with two conditions is a weaker claim than
  one with three).

### Tier 2 — moderate new work, directly answers this venue's topics
- **RQ-E2 stateful auditor.** Same implementation as proposed for the other
  workshop; reuse the same code and runs if both submissions move forward
  in parallel, and just write up the result twice with different framing
  (safety framing there, access-control/state-systems framing here).
- **Per-action audit-latency instrumentation**, if not already logged at
  fine enough granularity to answer RQ-New1 from existing data: a short
  rerun (does not need the full 72-turn matrix — a handful of cycles per
  condition is enough to characterize batching's latency/cost tradeoff)
  with explicit per-call timing added to the auditor's logging.

### Tier 3 — stretch, scope as future work if time runs out
- **RQ-New3 persistent-memory long-horizon runs.** Needs new
  infrastructure (episode chaining without a hard reset) not currently
  supported by `run_experiment.py`. Given this is shared scope with RQ-E4
  from the other proposal, prioritize whichever workshop's deadline
  pressure is worse if only one gets built before August 29.
- **Formal abstraction/interface writeup for the wallet policy as a
  general-purpose authorization primitive** (topic 1) — a design/position
  contribution rather than an experiment: specify the interface (proposal
  in, verdict out, what state it may consult) abstractly enough that it
  reads as a reusable OS-layer component spec, not just this paper's
  specific implementation. Highest conceptual value for topic (1) but the
  least experimentally grounded item on this list — better suited to the
  2-page extended-abstract track (Section 1.2) than a claim needing full
  empirical backing.

### Suggested sequencing
If both this and the Trustworthy AI for Good submission are pursued for the
same deadline, RQ-E2 (the stateful auditor) is the one piece of new
experimental work worth building once and reporting twice — it is Tier 2
priority on both proposals. Everything else in this proposal's Tier 1 is
writing/packaging of what already exists, which makes the 2-page
extended-abstract track (1.2) realistic even without any of the Tier 2/3
work landing in time.
