"""Build a compact, token-bounded window digest for the discovery agent.

Primary source is the recognizer's `audit_events` (they already carry each
action + the agent's stated reasoning + the surveillance verdict), plus recent
public messages. Kept summarized so cost stays bounded as history grows.
"""
from collections import defaultdict

import httpx

_TIMEOUT = 30.0
_MAX_REASONING_PER_AGENT = 6
_THINK_CHARS = 280
_MSG_CHARS = 200
_MAX_MESSAGES = 30


def _get(url: str) -> dict:
    r = httpx.get(url, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _asset_of(details: dict) -> str:
    details = details or {}
    return details.get('pair') or details.get('token') or details.get('symbol') or ''


def build_digest(base_url: str, experiment_id: str, window_start: int, window_end: int) -> dict:
    """Digest the cycle window [window_start, window_end] across all agents."""
    events = _get(f"{base_url}/api/audit/events?experiment_id={experiment_id}"
                  f"&cycle_min={window_start}&cycle_max={window_end}&limit=1000").get('events', [])

    agents = defaultdict(lambda: {'actions': [], 'reasoning': [], 'nonallowed': 0})
    verdicts = defaultdict(int)
    categories = defaultdict(int)
    for e in events:
        a = agents[e['agent_name']]
        a['actions'].append({
            'cycle': e['cycle_number'],
            'action': e['action_type'],
            'asset': _asset_of(e.get('action_details')),
            'verdict': e['verdict'],
            'category': e.get('threat_category'),
        })
        if e['verdict'] != 'allowed':
            a['nonallowed'] += 1
        react = e.get('agent_reasoning') or {}
        think = react.get('think')
        if think and len(a['reasoning']) < _MAX_REASONING_PER_AGENT:
            a['reasoning'].append({'cycle': e['cycle_number'], 'think': think[:_THINK_CHARS]})
        verdicts[e['verdict']] += 1
        categories[e.get('threat_category') or 'none'] += 1

    # Recent public messages (best-effort — never let this break discovery).
    messages = []
    try:
        hist = _get(f"{base_url}/api/messages/history").get('messages', [])[-_MAX_MESSAGES:]
        for m in hist:
            messages.append({
                'from': m.get('sender_name') or m.get('sender_id'),
                'to': m.get('recipient_name') or ('all' if m.get('is_broadcast') else m.get('recipient_id')),
                'content': (m.get('content') or '')[:_MSG_CHARS],
            })
    except Exception:
        pass

    return {
        'window': [window_start, window_end],
        'n_events': len(events),
        'agents': {name: dict(v) for name, v in agents.items()},
        'auditor_verdicts': dict(verdicts),
        'auditor_categories': dict(categories),
        'recent_messages': messages,
    }
