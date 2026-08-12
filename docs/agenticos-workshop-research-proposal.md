# Research Proposal: Repositioning "Your Agent Says Yes" for AgenticOS @ NeurIPS 2026 — Topic (5) Only

This document plans a submission of *"Your Agent Says Yes: Emergent Market
Misconduct in Agentic Trading"* to
[AgenticOS: Co-designing Systems and ML Foundations of an OS Layer for
Agentic AI](https://agentic-fmos.github.io/), a NeurIPS 2026 workshop
(Sydney), scoped **entirely to topic (5): trust, safety & governance —
isolation, access control, observability, auditability of autonomous
agents.** The earlier draft of this proposal tried to touch all six of the
workshop's topics; this version drops that and reads the paper through a
single lens instead. That's a better fit for the paper as it exists — the
wallet-policy system is already an access-control-and-auditability
mechanism, and narrowing to one topic means every recommendation below can
point at something concrete already in the paper, rather than reaching for
five different literatures at once.

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

Topic (5)'s exact wording — "isolation, access control, observability,
auditability of autonomous agents" — names four distinct properties, not one.
The paper currently has strong, direct coverage of two of them (access
control, auditability), partial coverage of a third (observability), and
essentially no explicit treatment of the fourth (isolation). Section 1 maps
each of the four onto the paper as written and says exactly where the gaps
are.

---

## 1. What the paper still needs to change

### 1.1 Access control — already the paper's core contribution, reframe the headline
The wallet policy *is* an access-control system: every financial proposal is
evaluated pre-execution against a policy returning allow/flag/block, which is
structurally a reference-monitor / capability-check design. Finding 1's
result — transaction-local authorization does not compose across a sequence
of individually-valid actions — is a general access-control-completeness
problem (the reference monitor is stateless across calls), stated in the
paper using finance vocabulary (pump-and-dump, liquidation exit) instead of
systems vocabulary (session state, capability revocation, TOCTOU-style gaps).
**Change:** rewrite the introduction and Finding 1's framing to lead with the
access-control claim explicitly, and use the finance scenario as the
concrete instance, not the headline. This is the smallest-effort, highest-value
edit in this whole proposal — no new experiments needed, just reframing text
that already exists.

### 1.2 Auditability — already covered by the trace-and-review protocol, needs one missing number
Section 3.5's trace construction (proposal → verdict → state change →
messages → outcome) and its two-reviewer-plus-reconciliation human review
protocol *is* an auditability mechanism, applied to the audit mechanism
itself (auditing the auditor's coverage, essentially). One thing the current
draft doesn't report: **inter-rater agreement between the two human
reviewers before reconciliation.** For an auditability claim to be credible,
the paper needs a number for how often the two independent reviewers agreed
before the third reviewer had to adjudicate — right now the paper describes
the *process* but not its *reliability*. This is very likely already
computable from existing review records (no new human review needed, just a
statistic over decisions already made) and is exactly the kind of concrete
auditability evidence this venue will look for.

### 1.3 Observability — partially covered, needs an explicit completeness claim
The trace links proposal, verdict, state change, and messages, but the paper
never states whether that structured trace is *sufficient* to reconstruct
misconduct, or whether reviewers had to go outside it. The turns-1-3 MOON
trace in Finding 1 is presented as if the structured log alone supports the
narrative — but the private message "disclosing control of over 70% of
supply" is qualitative content a categorical verdict field can't capture.
**Change:** add an explicit statement of what the observability layer does
and does not capture — e.g., "the structured trace records the verdict and
state change for every proposal; message content was read qualitatively by
human reviewers and is not itself a machine-readable audit field." This
turns an implicit limitation into a stated design property, which is what an
observability discussion for a systems audience needs.

### 1.4 Isolation — the real gap, and the strongest new-content opportunity
This is the one property topic (5) names that the paper does not currently
discuss at all, and it is the part of the paper's own data that most
directly supports it once named. **Isolation, in an access-control system,
means one principal's actions and their consequences stay contained to that
principal unless explicitly authorized to cross a boundary.** The paper
already has a documented isolation failure: in the Finding-1 trace, after
GoldenWhale's exit was eventually allowed, "LeverageKing kept 1.98 million
MOON yet lost \$1,870 in marked portfolio value despite a higher ETH price."
LeverageKing never authorized any interaction with GoldenWhale — the harm
crossed a wallet-policy boundary entirely through shared market state (the
pool price GoldenWhale's exit moved). **This is exactly the isolation
question topic (5) asks about, and it currently has no name in the paper.**
**Change:** name this explicitly as an isolation-boundary problem distinct
from the access-control problem in 1.1 — access control asks "was this
agent's own request authorized," isolation asks "did an authorized action's
consequences stay contained to consenting parties." The paper currently only
answers the first question.

### 1.5 Length and anonymization
Given 1.1–1.3 are largely reframing of existing material and 1.4 is the one
genuinely new analysis, this fits the **2-page extended abstract** track
comfortably even before any Section 3 experiment lands — access control +
auditability + observability reframes plus the isolation finding (even using
only existing trace data, see RQ4/Tier 1 below) is a complete, focused
2-pager. Move to the 6-page track only if the isolation-focused experiment in
Section 3 (Tier 2) produces enough new material to be worth the extra space.
Anonymization status unchanged from the other proposal: the
`anonymous.4open.science` link is already double-blind-compatible; re-check
camera-ready text once and reuse across both submissions.

### 1.6 Related work
Both previously-identified papers support topic (5) directly and both stay:
- *Multi-Agent Risks from Advanced AI* (arXiv:2502.14143) — its collusion
  failure mode and "multi-agent security" risk factor both bear on access
  control and isolation as defined here.
- *Open Challenges in Multi-Agent Security* (arXiv:2505.02077) — its
  argument that model-level safety is insufficient for multi-agent
  interaction security is the isolation argument in 1.4, generalized. Worth
  pulling a specific quote or claim from this paper that names cross-agent
  containment/isolation directly, if one exists — re-read with that
  specific question before the writing pass, since the earlier fetch of this
  paper was a summary, not a full read.
No further citation search needed for this narrower scope — the two existing
references cover all four sub-properties reasonably well once the isolation
angle is added, unlike the six-topic version of this proposal which had real
citation gaps for topics (1)-(4) and (6).

---

## 2. Research plan

Four questions, one per sub-property of topic (5), in order of how much new
work each needs.

**RQ1 (auditability — cheapest, do this first).** What was the inter-rater
agreement between the two independent human reviewers before reconciliation?
Pure statistic over already-completed review decisions; no new data
collection. Report simple percent agreement or Cohen's kappa per evidence
level (attempt / executed / consequential) and per behavior label.

**RQ2 (observability — writing, not experiment).** For each of the four
findings, what did the structured trace alone support, and where did the
human reviewers need to read raw message content or reconstruct context the
categorical fields didn't carry? Produces the explicit completeness
statement described in 1.3.

**RQ3 (isolation — the paper's new contribution for this venue).** How much
of a non-participating agent's outcome variance is attributable to *other*
agents' authorized-but-harmful actions, versus its own decisions? Concretely:
for agents not directly involved in a flagged/blocked sequence, measure
portfolio-value changes in the cycles immediately following a coordinated
exit or pump-and-dump elsewhere in the same world, and check whether the
LeverageKing-style spillover in the existing trace is a general pattern or a
one-off. This is answerable largely from the *existing* eight-run dataset —
it's a new analysis over old data, not new data collection — because every
run already logs full portfolio and verdict traces.

**RQ4 (access control — the one item that needs new experimental work).**
Does adding cross-agent isolation to the wallet policy — e.g., position or
exposure limits that cap how much one agent's pool-moving action can affect
another agent's marked portfolio value within a window, independent of
whether the *acting* agent's own request was authorized — reduce the
spillover measured in RQ3? This is a different mechanism than the
history-aware/stateful auditor proposed for the other workshop submission
(RQ-E2 there): that fix targets access control (catching a persistent
requester), this one targets isolation (containing a blast radius regardless
of whether the triggering request was itself allowed). Worth stating
explicitly in the paper that these are two different fixes for two different
properties, since conflating them would undercut the topic-(5) framing this
proposal is built around.

---

## 3. Experiments to add, ranked by cost vs. deadline

### Tier 1 — cheap, do these first, no new runs
- **RQ1 inter-rater agreement.** Compute from existing review records.
- **RQ3 isolation/spillover re-analysis.** Compute from the existing
  eight-run trace data: for each run, identify flagged/blocked/allowed
  sequences involving one agent, and measure portfolio-value deltas for
  *other* agents in the following 1–3 cycles. This is the paper's strongest
  new claim for this venue and costs no new experiments — reuse
  `analysis/analyze_run.py`-style tooling against `portfolio_performance.csv`
  and `audit_events.csv`, which already have everything needed (per-cycle
  portfolio values and per-action verdicts with timestamps).
- **World C (sideways) addition**, if time allows — strengthens RQ3's
  generality claim across a third market regime, using infrastructure
  (`configs/world_c_*.sh`) that already exists. Lower priority than the two
  items above since RQ3 doesn't strictly need a third regime to make its
  point.

### Tier 2 — moderate new work, the one thing worth building
- **RQ4 isolation-aware wallet policy.** Add a cross-agent exposure/position
  limit to the auditor — distinct from the stateful/history-aware auditor
  proposed for the Trustworthy AI for Good submission — and rerun the
  bull/bear matrix with it as a third condition. Measure whether it reduces
  the RQ3 spillover metric. This is the one genuinely new experimental
  result this proposal needs; everything else is analysis of existing data
  or reframed writing.

### Tier 3 — skip for this scope
Everything from the broader six-topic version of this proposal that isn't
about isolation, access control, observability, or auditability — resource
cost/scheduling (topic 3), memory/state architecture beyond RQ4's access-
control fix (topic 2), long-horizon self-evolving agents (topic 4), and
generic benchmark packaging (topic 6) — is out of scope for this narrower
submission. If a 6-page version is pursued later, RQ-New1/RQ-New2 from the
earlier draft of this proposal can be reintroduced, but they add topics the
double-blind reviewer didn't ask this version to cover.

### Suggested sequencing
Do Tier 1 first regardless of which length track gets chosen — both items
are cheap and RQ3 is the proposal's central new claim. Decide between the
2-page and 6-page track only after RQ3's re-analysis is in hand: if the
spillover pattern is clear and general across runs, a 2-pager built on RQ1–3
is complete and low-risk. Only build RQ4 (Tier 2) if aiming for the 6-page
track or if RQ3's result is strong enough to justify the added experimental
claim.
