# Research Proposal: Repositioning "Your Agent Says Yes" for Trustworthy AI for Good @ NeurIPS 2026

This document plans the revision of the AAAI 2026 submission *"Your Agent Says Yes:
Emergent Market Misconduct in Agentic Trading"* into a submission for the
[Trustworthy AI for Good workshop](https://trustworthy-ai-for-good.github.io/#overview)
at NeurIPS 2026 (Paris). It covers three things: what the paper itself needs to
change, a research plan grounded in two multi-agent-security surveys plus four
empirical papers from the ICML 2026 sister-edition of this same workshop, and
the concrete new experiments that plan implies.

**Update (Aug 15):** the ICML 2026 edition of AI4GOOD has already run (Seoul,
July 10) and its award list is public. Four of those papers — one CoopAI Best
Paper, two CoopAI Outstanding, and one General Track Honourable Mention — are
close enough in method or topic to this paper that they've been read in full
and folded into this plan (see §1.3, §1.6, §1.7, and the reference list in
§4). These are a higher-value signal than the two survey papers alone: they
are not just "what this field cares about," they are literally this venue's
own bar for what an accepted/awarded paper looks like.

**Correction (this pass):** a fifth paper, "Hand and Brain: Defenses against
Agentic Steganography in Language Models" (attributed to Krzyzanowski,
Arcuschin, Lee, Meyer, Lange), was cited in an earlier version of this
document and has been removed. It could not be verified by search under
that title/author combination; the closest real match found was a
different, unrelated 2025 paper ("Scales of AI Covert Communication," MIT)
sharing two author surnames (Krzyzanowski, Arcuschin) but no other overlap.
Treat it as unverified/likely fabricated. Everything that depended on it —
the syntactic/semantic-"agentic"-channel framing for steganography — has
been removed along with it; §1.4/§2/§3's steganography items are back to
testing message wording only, not a second "agentic channel." The other
four papers (SCHEME, Norm Enforcement, CoopEval, Za et al.) were each
independently confirmed to exist via arXiv/OpenReview search, though the
more granular technical claims attributed to them below (e.g., Norm
Enforcement's exact three update-rule formalism) have only been checked
against abstracts, not full text — verify against the actual PDF before
relying on those specifics in a submission.

## 0. Workshop constraints (source of truth for everything below)

| Constraint | Value |
|---|---|
| Deadline | August 29, 2026, 11:59 PM AoE |
| Length | 2–9 pages, excluding references/appendix |
| Template | NeurIPS 2026 workshop style |
| Review | Double-blind via OpenReview |
| Status | Non-archival — may appear elsewhere |
| Tracks | (1) General — Trustworthy AI for Good; (2) Multi-Agent Track — Security and Safety |

The Multi-Agent Track explicitly names **"collusion and steganographic
communication between agents, secure interaction and delegation protocols"**
as topics of interest. This is close to a direct match for the paper's existing
framing (coordinated manipulation = collusion; the wallet policy = a secure
delegation protocol) but exposes one clear gap: the paper's Finding 1 and
Section 5 discuss *open* deceptive messaging, never *covert/coded* messaging.
"Steganographic communication" is the one CFP phrase the current draft does
not yet earn.

---

## 1. What the paper itself still needs to change

### 1.1 Fit the page budget and template
The AAAI draft is a dense two-column ~8-page paper with AAAI-style citations.
NeurIPS workshop format is different (single-column, different citation
macros, 9-page hard cap excluding references). This is not a pure reflow —
Table 1, Figures 4–5, and the related-work section will need real compression
to leave room for the new material below. Target the lower half of the 2–9
range (roughly 6–8 pages) rather than maxing it out; workshop reviewers
skim, and a tight paper reads better than a stuffed one.

### 1.2 Sharpen the "for Good" framing, not just the security framing
The current introduction is a security paper's introduction: it opens on the
agentic-trading security gap and backs it with real deployment numbers
(Coinbase's 165M x402 transactions, 480K transacting agents; AWS Bedrock
AgentCore Payments). That's a strong hook for the Multi-Agent Track, but the
General Track wants "AI for social good with real-world impact evidence" and
"evaluation and auditing of models for harmful behaviors." Two concrete edits:

- Make the retail-trader role's economic harm explicit and central, not a
  side effect of the manipulation analysis. Retail traders in the simulation
  are a direct stand-in for ordinary consumers who would be victimized by an
  agentic pump-and-dump or rug pull in a real agent-wallet deployment — say
  this plainly in the intro, not just in Section 2.2's background on scams.
- Expand Section 5 ("Security Implications") into something closer to
  practitioner recommendations: which of the paper's findings translate
  directly into a design change a wallet vendor (Coinbase, AWS, OKX — all
  already cited) could ship. The paper already gestures at this ("safeguards
  should carry forward risk state across semantically related actions") —
  make it a named subsection with 2–3 concrete recommendations tied to
  specific findings (Finding 1 → sequence-linked risk state; Finding 2 →
  report role-level, not just aggregate, outcomes).

### 1.3 Engage the survey papers — and the workshop's own award papers — in Related Work
All of the below are directly relevant and currently absent from the paper's
related-work section (2.1/2.2), which cites deployment products and
manipulation/scam literature but no general multi-agent-security taxonomy and
no empirical precedent from this exact venue:

- **Hammond et al., "Multi-Agent Risks from Advanced AI"** (arXiv:2502.14143)
  gives three failure modes (miscoordination, conflict, collusion) and seven
  risk factors (information asymmetries, network effects, selection
  pressures, destabilising dynamics, commitment problems, emergent agency,
  multi-agent security). The paper's own findings map onto this cleanly and
  should say so explicitly: Finding 1 (class-dependent containment) and the
  GoldenWhale/CryptoGuru/HappyTrader trace are a *collusion* failure mode
  instance; Finding 2's role-level redistribution is closest to
  *destabilising dynamics*; the private-coordination-then-block-then-allow
  sequence around turns 49–53 is a live instance of a *commitment problem*
  the paper has data for but doesn't currently name as such.
- **"Open Challenges in Multi-Agent Security: Towards Secure Systems of
  Interacting AI Agents"** (arXiv:2505.02077) is the more direct fit: it
  names secret collusion and covert/steganographic communication as an open
  problem, and argues model-level safety practices are insufficient for
  multi-agent interaction security — which is exactly the paper's own thesis
  (transaction-local authorization vs. episode-level conduct). Citing it lets
  the paper position the "agentic-trading security gap" as a concrete,
  measured instance of a challenge this survey only poses abstractly, and
  gives a citable source for the "steganographic communication" framing used
  in Section 1.4 below.
- **Radev, Haas, Arnav, Bernabeu-Pérez, "The Best-Laid SCHEMEs: Coordinated
  Sabotage and Monitoring in Multi-Agent Systems"** (AI4GOOD @ ICML 2026,
  CoopAI Outstanding Paper) is the closest empirical analog this paper has —
  closer than either survey. It studies exactly the same shape of problem
  (a team of agents pursuing a covert joint objective while a trusted monitor
  watches, with financial tasks — including a *portfolio-optimization*
  side-task setting — among its seven domains) and reports results the same
  way this paper should: monitor **TPR at a fixed FPR operating point**
  (≤2%), an explicit ablation of *what the monitor is allowed to see*
  (code-only vs. code+communication), and a "stealth-aware" condition where
  agents are told a monitor is present — which cuts attacker success without
  denting detection, the same qualitative shape as this paper's turns-49–53
  block→flag reclassification. Cite it as direct precedent for the auditor
  framing, and adopt its reporting convention (§1.6).
- **Ye & Steinhardt, "Norm Enforcement for AI Agents: Robustly Shaping
  Behavior in Multi-Agent Systems"** (AI4GOOD @ ICML 2026, CoopAI Best Paper)
  is less a topical match than a *design-pattern* one: it gives three formal
  update rules for a cross-turn reputation/risk score (symmetric, fixed-
  asymmetric, escalating) with proofs of which ones can be gamed
  indefinitely and which one provably can't. This directly upgrades RQ-E2's
  "history-aware wallet policy" from a single ad hoc heuristic into a
  principled comparison — see §2 and §3.

### 1.4 Either add the steganography experiment, or name the gap explicitly
Given the deadline, there are two honest options, not one required one:
1. Run E1 below (a real message-content gate and a look for coded language)
   and report whatever is found — including a null result, which is still a
   finding ("agents did not shift to covert language under a stricter
   message gate, at least at this scale") and directly answers a question
   the CFP asks.
2. If E1 doesn't finish in time, add one paragraph to Section 5 that
   explicitly names covert/steganographic coordination as future work,
   citing 2505.02077, rather than silently leaving the CFP's exact phrase
   unaddressed. Reviewers who skim for track fit will look for this word.

Option 1 is clearly better if the timeline allows it — see Section 3.

### 1.5 Anonymization check
The footnote pointing to `anonymous.4open.science/r/virtual_exchange-C62F/`
is already workshop-compatible (double-blind via OpenReview). Before
submission, re-check the camera-ready text for: acknowledgments, author-tied
infrastructure names (e.g., a specific university's cluster), and the GitHub
org name `SHITIANYU-hue` if any repository screenshots or paths are ever
pasted into the appendix.

### 1.6 Adopt this venue's reporting conventions
Reading the four ICML 2026 award papers side by side surfaces a consistent
methodological bar that this draft currently falls short of on two counts:

- **Report rates as detection/containment performance at a fixed operating
  point, not raw percentages.** SCHEME reports monitor performance as "TPR at
  FPR≤2%," which is directly transferable: the wallet auditor is a monitor,
  candidate classes are the workload, and block/flag verdicts are the
  monitor's calls. Reframe Finding 1's 45.8%/11.2% comparison (and the new
  E1/E2 results) in these terms where a false-positive rate can be defined
  (e.g., legitimate-looking proposals later confirmed benign by human
  review), and — copying SCHEME's most useful ablation — report what happens
  to that rate when the auditor's visible input changes (transaction-only,
  as today, vs. transaction+message, as in E1).
- **State the backbone model(s) explicitly, and be honest about statistical
  power.** CoopEval (6–9 models), Za et al. (7 models, 200,000+ decisions),
  and SCHEME (N=85 trajectories/model with Wilson 95% CIs on every rate) are
  the norm at this venue; this paper's current n=2 reruns/cell and
  undisclosed backbone model(s) are well below it. This is not fixable by
  the deadline, but it is fixable to *disclose* — see §1.7. Where the paper
  does report a rate over a small N (Finding 4's Spearman correlations from
  n=2/3 reruns in particular), say the N inline next to the number, not only
  in a figure caption, and avoid presenting it as more than exploratory
  evidence of a direction.

### 1.7 Add a Limitations section (currently absent from the draft)
None of the four award papers skip this, and Norm Enforcement's is a good
template: it doesn't just list caveats, it states precisely what its formal
results do and don't cover ("these propositions characterize a single
agent's reputation dynamics in isolation under stationary strategies... they
do not model adaptive strategies... or population-level dynamics"). Draft a
comparably precise paragraph for this paper, e.g.:

> This study characterizes agent behavior in a single simulator (Virtual
> Exchange) across two/three replay windows, [N backbone model(s)], with
> n=2–3 reruns per experimental cell. It does not establish how these
> containment failures generalize across simulators, market regimes beyond
> the replayed windows, or model families beyond [X]. The role-conditioned
> design (§1.1/§3.4) demonstrates red-team-elicited misconduct under
> role-assigned economic objectives; it does not by itself establish that
> the same misconduct would arise from a neutral objective absent
> role-conditioning (see the emergent-vs.-induced framing decision this
> paper makes explicitly). Candidate-class statistics in §4 are computed
> over auditor-assigned labels; the human-adjudicated ground-truth layer
> (§3.5) is [aggregated in Table X / reported only as a qualitative trace —
> update once §2's evidence-level table is done].

This is a required section, not an optional one, at this venue's evidenced
bar — treat it as Tier 1 work in §3 (near-zero cost, since it is mostly
honest bookkeeping of decisions already made elsewhere in this document).

---

## 2. Research plan (grounded in the papers above)

The plan is to use Hammond et al.'s taxonomy as the *organizing structure*
for what the paper already has, and Open Challenges in Multi-Agent Security's
list of open problems as the *source of new research questions*. Four
extensions, in priority order:

**RQ-E1 (from 2505.02077 — secret collusion / steganographic communication).**
Does message content shift toward covert or indirect coordination language
when messages themselves become an audited, block-capable channel? The
current auditor (Section 3.3 of the paper) explicitly leaves communication
outside the transaction gate — "Communication remains outside this
transaction-level gate, enabling strategies to continue or shift channels
even when an explicit financial request is rejected." This is stated as a
finding about the *current* design; RQ-E1 asks what happens once that gap is
closed. This is the single highest-priority extension because it is the
literal CFP phrase and the paper's own stated limitation.

**RQ-E2 (from 2505.02077 — secure interaction and delegation protocols).**
Does a *history-aware* wallet policy — one that carries a cumulative risk
score per agent or per token across turns, instead of scoring each proposal
independently — close the persistence gap documented in Finding 1 (four
blocked GoldenWhale liquidation requests followed by a fifth, differently
classified, non-blocking one)? This directly tests the paper's own proposed
fix in Section 5 rather than leaving it as an assertion. **Refinement from
Norm Enforcement (§1.3):** rather than one ad hoc escalating-score design,
implement and compare the three formally-motivated update rules from that
paper's reputation mechanism — symmetric (linear penalty), fixed-asymmetric
(linear, weighted toward penalties), and escalating (quadratic penalty
growth) — applied here to accumulated suspicion per agent/token instead of
per-report reliability. Their proofs show the symmetric and fixed-asymmetric
rules both admit a stable "laundering" plateau an adversarial agent can
operate under indefinitely, while the escalating rule provably closes it;
replaying the existing eight traces under all three turns this from one
heuristic fix into a principled three-way comparison with a citable
theoretical prediction to test against ("does escalating outperform the
other two on the turns-49–53 case, as the theory predicts?").

**RQ-E3 (from 2502.14143 — commitment problems).** Among agent pairs that
privately coordinate a pump-and-dump (already present in the trace data used
for Finding 1), how often does the party who agreed to exit second actually
defect and exit first? This is a re-analysis question, not a new experiment:
the DM + trade traces needed already exist in the eight-run dataset. It adds
a "commitment problem" result at near-zero additional data-collection cost,
which matters given the timeline.

**RQ-E4 (from 2502.14143 — network effects, selection pressures).** Does
collusion prevalence scale with the number of potential colluders (more
whale/shill-type agents), and does manipulation effectiveness increase across
successive episodes if agent memory persists instead of resetting? These are
the two risk factors from the taxonomy the paper currently has no data on at
all. Treat as stretch goals (Section 3) given the deadline — flag as future
work if not completed, but scope them concretely enough in the paper that
"future work" doesn't read as filler.

**RQ5 (from the paper's own Section 5 — who bears the cost of enforcement).**
Section 5 already states the question and never answers it: "one price path
or aggregate return alone can obscure who benefits and who bears the cost of
enforcement." Is auditor protection distributed equitably across capital
tiers? Concretely: does block/flag rate, conditioned on candidate class,
differ systematically between whale/market-maker roles ($500K) and retail
roles ($10K) — and separately, are retail agents' own defensive or
reactive actions more likely to be misclassified than whales' offensive
ones? This doesn't need either external reference paper — it operationalizes
a question the paper already poses about itself, which makes it a
low-risk, high-relevance addition for a "for Good"/equity-of-protection
angle the General Track explicitly wants ("AI for social good with
real-world impact evidence").

**RQ6 (isolation and third-party harm — shared with the AgenticOS
proposal's RQ3).** The existing Finding-1 trace already contains a
documented case of harm to a non-participating agent: LeverageKing, never
directly interacting with GoldenWhale, lost \$1,870 in marked value as a
side effect of GoldenWhale's eventually-allowed exit. Is this a one-off or
a general pattern — how much of a non-participating agent's outcome
variance is attributable to *other* agents' authorized-but-harmful actions,
not its own decisions? Framed for this venue as a direct "who bears the
cost of AI-agent harm" accountability question, distinct from the same
re-analysis framed as a systems-isolation question in the parallel
AgenticOS proposal (`docs/agenticos-workshop-research-proposal.md`, RQ3).
**Run this analysis once and write it up twice** — the underlying
computation over `portfolio_performance.csv` and `audit_events.csv` is
identical; only the framing differs between the two submissions.

---

## 3. Experiments to add, ranked by cost vs. deadline

Given the August 29 deadline, experiments are grouped by how much new
infrastructure they need versus what the codebase already has.

### Tier 1 — cheap, do these first

- **E0 — required disclosures (§1.6/§1.7).** State the backbone model(s) for
  the ten trading agents and the auditor's LLM-judgment component; add the
  Limitations paragraph drafted in §1.7; and, anywhere the paper reports a
  rate computed from a small N (Finding 4 especially), put the N inline next
  to the number. Zero new data collection — this is writing, not
  experimentation — but per §1.6 it is close to a hard requirement for
  credibility at this venue, so it belongs in Tier 1 despite not being an
  "experiment."
- **E3 — add the third replay regime (World C / sideways).**
  The codebase already has this: `configs/world_c_auditor.sh` and
  `configs/world_c_noauditor.sh` exist and have been smoke-tested against the
  live pipeline. Finding 3 currently rests on two replay windows (bull, bear)
  and explicitly flags its own small-N caveat ("only one bull repetition
  shows a similar shift"). Running World C costs one more `--world C` pass
  through infrastructure that already works — this is the best
  effort-to-evidence ratio available before the deadline.
- **E-RQ-E3 — commitment-problem re-analysis.** No new runs; scan the
  existing eight-run trace data for private pump-and-dump agreements and
  measure defection rate. Pure analysis script, reuses the existing
  `analysis/analyze_run.py`-style tooling.
- **E4 — one more repetition per cell.** Finding 4 already reports
  paired-rerun Spearman correlations from n=2 as unstable (−0.03 to 0.21).
  A third repetition per condition doesn't fix small-N instability on its
  own, but strengthens "a relation repeated within a matched condition" —
  the evidentiary bar the paper sets for itself in Finding 4 — with one more
  data point per bar.
- **E-RQ5 — equitable-protection breakdown.** No new runs; group the
  existing `audit_events.csv` verdicts by agent capital tier (whale/market
  maker $500K, mid-tier $50K, retail $10K) and compare block/flag rates
  within candidate class, plus a spot check of whether retail agents'
  defensive actions get misclassified more often than whales' offensive
  ones. Pure `pandas`-style groupby over data that already exists.
- **E-RQ6 — isolation/third-party-harm re-analysis.** No new runs; same
  computation as the AgenticOS proposal's RQ3 (portfolio-value deltas for
  non-participating agents in the 1–3 cycles following a flagged/blocked
  sequence elsewhere in the same world). Compute once, write up in both
  submissions with different framing — see the note in Section 2.

### Tier 2 — moderate new work, directly answers the CFP

- **E1 — steganography/covert-communication stress test (RQ-E1).**
  Extend the auditor (`auditor/`) with a stricter message-content signal
  that treats explicit coordination language (specific plans, timing,
  named targets) as block-eligible, not just flag-eligible under R010. Rerun
  the bull/bear matrix with this stricter message gate as a third condition
  alongside the existing on/off auditor modes. Read the resulting messages
  (LLM-assisted coding, then human spot-check, matching the paper's existing
  two-reviewer protocol) for indirect language, euphemism, or coded
  references that increase relative to the baseline runs. **Report using
  SCHEME's convention**: TPR at a fixed FPR operating point for "auditor
  with message access" vs. the existing transaction-only auditor, rather
  than raw block-rate deltas. Report the result either way — a null result
  is still evidence for the CFP's question.
- **E2 — history-aware wallet policy (RQ-E2).** Add auditor variants that
  maintain cross-turn state — implement **all three of Norm Enforcement's
  update rules** (symmetric, fixed-asymmetric, escalating; see §2) applied
  to a cumulative suspicion score keyed on agent-pair or token, rather than
  a single ad hoc heuristic — instead of the current proposal-local scoring.
  Rerun the same replay windows with these as additional auditor modes. The
  target result is a direct, falsifiable test of Finding 1's turns-49–53
  sequence: does the stateful policy block the fifth liquidation request
  that the current stateless policy allowed, and if so, is it specifically
  the escalating rule that does it (as the theory predicts) or do all three
  variants perform similarly (a negative result for the theoretical
  prediction, which is itself worth reporting)?

### Tier 3 — stretch goals, scope as future work if time runs out

- **E5 — scale agent population (RQ-E4, network effects).** Re-run with 2–3
  agents per adversarial role instead of 1, holding total capital
  constant, to see whether collusion dynamics change with more potential
  colluders.
- **E6 — iterated multi-episode runs (RQ-E4, selection pressures).** Chain
  multiple 72-turn episodes with persistent agent memory across episode
  boundaries (current `--hard-reset` wipes memory between runs; this needs a
  new "soft continuation" mode) to see whether manipulative strategies
  strengthen across episodes.
- **E7 — adversarial red-team condition.** Deliberately prompt one agent
  (e.g., via its role prompt) to maximize covert manipulation and minimize
  detectability, as a worst-case robustness stress test of the auditor,
  rather than relying only on emergent behavior. Matches the workshop's
  explicit interest in "evaluation and auditing of models for harmful
  behaviors" but is the most novel-infrastructure item on this list.

### Suggested sequencing
Given the deadline, Tier 1 should be treated as required — all six items
(including the new E0 disclosures) are pure analysis/writing over data that
already exists and directly strengthen existing findings, answer a question
(RQ5, RQ6) the paper already poses about itself, or close a credibility gap
this venue's own award papers make hard to ignore (E0). E1 and E2 in Tier 2
should be prioritized over anything in Tier 3 since they are the only two
items that directly answer the Multi-Agent Track's named topics rather than
just adding statistical power or accountability framing, and Tier 3 items
should be scoped in the paper as named, concrete future work rather than
attempted if time is short. Do E0 first regardless of what else gets cut —
it's the cheapest item on the entire list and the one most likely to
determine whether a reviewer trusts the rest of the paper's numbers.

---

## 4. New references to add (from the ICML 2026 AI4GOOD award list)

All four are workshop papers from the ICML 2026 edition of AI4GOOD (Seoul,
July 10, 2026), each independently confirmed to exist via arXiv/OpenReview
search during this revision pass. Their arXiv IDs (verified) are given below;
the award-track labels and the more granular technical claims attributed to
each paper elsewhere in this document were checked only against abstracts,
not full text — re-verify against the actual PDF before finalizing citations:

- Radev, N., Haas, L., Arnav, B., Bernabeu-Pérez, P. "The Best-Laid SCHEMEs:
  Coordinated Sabotage and Monitoring in Multi-Agent Systems." arXiv:2605.29178.
  AI4GOOD @ ICML 2026 (CoopAI Track, Outstanding Paper — award-track label
  not independently re-verified against the paper itself).
- Ye, Y., Steinhardt, J. "Norm Enforcement for AI Agents: Robustly Shaping
  Behavior in Multi-Agent Systems." arXiv:2607.09766. AI4GOOD @ ICML 2026
  Trustworthy AI for Good Workshop (confirmed venue; award-track label not
  independently re-verified).
- Tewolde, E., Zhang, X., Piedrahita, D.G., Conitzer, V., Jin, Z. "CoopEval:
  Benchmarking Cooperation-Sustaining Mechanisms and LLM Agents in Social
  Dilemmas." arXiv:2604.15267. AI4GOOD @ ICML 2026 — cite only if space
  allows, as general evidence for the venue's expectation of multi-model
  evaluation (§1.6); not a direct topical fit.
- Za, J., Panos, A., Čuhel, J. "Towards Predictive Models of Strategic
  Behaviour in Large Language Model Agents." AI4GOOD @ ICML 2026 (General
  Track) — confirmed via the author's personal academic homepage; arXiv ID
  not yet located, check OpenReview directly. Same role as CoopEval above:
  cite for the large-N/multi-model convention, not topical overlap.
