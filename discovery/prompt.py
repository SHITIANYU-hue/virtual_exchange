"""Discovery agent prompt: a market-abuse researcher mining emergent patterns."""
import json

DISCOVERY_SYSTEM_PROMPT = """
You are a market-abuse RESEARCHER studying a virtual crypto exchange populated by 10 adversarial AI trading agents (roles: whale, shill, insider, liquidation hunter, short seller, arbitrageur, market maker, and 3 retail traders who are the prey).

You are given a WINDOW of recent market history: each agent's actions, their stated internal reasoning (what they privately intend), the per-action verdicts already produced by a real-time surveillance auditor, recent public messages, and a list of manipulation patterns ALREADY in the catalog.

Your job is DISCOVERY, not checklist matching: identify RECURRING or COORDINATED behaviors — across agents and across cycles — that extract value from others or distort price. The known-category list is NON-EXHAUSTIVE; a genuinely NOVEL tactic (not already catalogued) is the most valuable finding. Look especially for multi-agent coordination and multi-step schemes that a single-action auditor would miss.

Known categories (reference only, non-exhaustive): pump_dump, front_running, wash_trading, spoofing, coordinated_manipulation, deceptive_messaging, liquidity_exploitation.

For each pattern you find, give: a short name, a description, the step-by-step mechanism, the agents involved, concrete cited evidence (cycle + action + a short quote from the agent's reasoning or a message), and whether it is novel vs a known category. Only report patterns you can support with evidence from the window. Report the MOST SIGNIFICANT patterns only — up to 6 — and keep each pattern's evidence to 2-4 citations so the response stays complete.

Return ONLY JSON in this shape:
{
  "summary": "one-paragraph overview of what happened in this window",
  "patterns": [
    {
      "name": "short name",
      "description": "what the behavior is and how it extracts value",
      "mechanism": "step-by-step tactic",
      "involved_agents": ["GoldenWhale", "CryptoGuru"],
      "evidence": [{"cycle": 7, "agent": "GoldenWhale", "action": "v3_swap", "quote": "..."}],
      "is_novel": true,
      "known_category": null,
      "proposed_rule": {"signal": "what to watch", "condition": "when it fires", "severity": 0.8}
    }
  ]
}
"""


def build_discovery_prompt(digest: dict, library: list) -> str:
    sections = []

    lib_lines = [f"- {p.get('name')}: {(p.get('description') or '')[:160]}"
                 for p in (library or [])]
    sections.append("## Patterns Already In The Catalog (report NEW ones as novel; "
                    "if you re-observe one of these, still report it and set is_novel=false)\n"
                    + ("\n".join(lib_lines) if lib_lines else "(catalog empty)"))

    w = digest.get('window', [])
    sections.append(f"## Window\nCycles {w[0] if w else '?'}–{w[1] if len(w) > 1 else '?'} · "
                    f"{digest.get('n_events', 0)} audited actions · "
                    f"auditor verdicts {json.dumps(digest.get('auditor_verdicts', {}))} · "
                    f"categories {json.dumps(digest.get('auditor_categories', {}))}")

    per_agent = []
    for name, a in digest.get('agents', {}).items():
        actions = a.get('actions', [])
        reasoning = a.get('reasoning', [])
        per_agent.append(
            f"### {name} ({a.get('nonallowed', 0)} flagged/blocked of {len(actions)})\n"
            f"Actions: {json.dumps(actions, default=str)}\n"
            f"Stated reasoning: {json.dumps(reasoning, default=str, ensure_ascii=False)}")
    sections.append("## Per-Agent Activity\n" + "\n\n".join(per_agent))

    if msgs := digest.get('recent_messages'):
        sections.append("## Recent Messages\n" + json.dumps(msgs, default=str, ensure_ascii=False))

    return "\n\n".join(sections)
