# Research Proposal: Repositioning "Your Agent Says Yes" for Trustworthy AI for Good @ NeurIPS 2026

This document plans the revision of the AAAI 2026 submission *"Your Agent Says Yes:
Emergent Market Misconduct in Agentic Trading"* into a submission for the
[Trustworthy AI for Good workshop](https://trustworthy-ai-for-good.github.io/#overview)
at NeurIPS 2026 (Paris). It covers three things: what the paper itself needs to
change, a research plan grounded in two multi-agent-security surveys, and the
concrete new experiments that plan implies.

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

### 1.3 Engage the two suggested papers in Related Work
Both are directly relevant and currently absent from the paper's related-work
section (2.1/2.2), which cites deployment products and manipulation/scam
literature but no general multi-agent-security taxonomy:

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

---

## 2. Research plan (grounded in the two papers above)

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
fix in Section 5 rather than leaving it as an assertion.

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

---

## 3. Experiments to add, ranked by cost vs. deadline

Given the August 29 deadline, experiments are grouped by how much new
infrastructure they need versus what the codebase already has.

### Tier 1 — cheap, do these first

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

### Tier 2 — moderate new work, directly answers the CFP

- **E1 — steganography/covert-communication stress test (RQ-E1).**
  Extend the auditor (`auditor/`) with a stricter message-content signal
  that treats explicit coordination language (specific plans, timing,
  named targets) as block-eligible, not just flag-eligible under R010. Rerun
  the bull/bear matrix with this stricter message gate as a third condition
  alongside the existing on/off auditor modes. Read the resulting messages
  (LLM-assisted coding, then human spot-check, matching the paper's existing
  two-reviewer protocol) for indirect language, euphemism, or coded
  references that increase relative to the baseline runs. Report the result
  either way — a null result is still evidence for the CFP's question.
- **E2 — history-aware wallet policy (RQ-E2).** Add a second auditor variant
  that maintains cross-turn state (e.g., an escalating suspicion score keyed
  on agent-pair or token, decaying over turns) instead of the current
  proposal-local scoring. Rerun the same replay windows with this as a third
  auditor mode. The target result is a direct, falsifiable test of Finding
  1's turns-49–53 sequence: does the stateful policy block the fifth
  liquidation request that the current stateless policy allowed?

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
Given the deadline, Tier 1 should be treated as required (all three are low
cost and directly strengthen existing findings), E1 and E2 in Tier 2 should
be prioritized over anything in Tier 3 since they are the only two items that
directly answer the Multi-Agent Track's named topics rather than just adding
statistical power, and Tier 3 items should be scoped in the paper as named,
concrete future work rather than attempted if time is short.
