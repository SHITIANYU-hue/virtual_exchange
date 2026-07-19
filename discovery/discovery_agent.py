"""The discovery agent: observe a window -> mine patterns -> persist.

Runs in the experiment runner every K cycles. Observe-only (v1): it grows the
discovered-pattern catalog; it never gates execution.
"""
import os

import httpx

from discovery.digest import build_digest
from discovery.prompt import DISCOVERY_SYSTEM_PROMPT, build_discovery_prompt
# Reuse the auditor's robust text extraction (ThinkingBlock-safe) + tolerant JSON parse.
from auditor.llm_auditor import LLMAuditor

_TIMEOUT = 120.0


class DiscoveryAgent:
    def __init__(self, base_url: str = 'http://localhost:8000', model: str = None):
        self.base_url = base_url
        self.model = model or os.environ.get('DISCOVERY_LLM_MODEL', 'claude-sonnet-5')

    def run(self, experiment_id: str, cycle: int, window_start: int) -> dict:
        """One discovery pass over cycles [window_start, cycle]. Returns a small summary."""
        digest = build_digest(self.base_url, experiment_id, window_start, cycle)
        library = self._get(f"{self.base_url}/api/discovery/patterns"
                            f"?experiment_id={experiment_id}").get('patterns', [])

        prompt = build_discovery_prompt(digest, library)
        result = self._call_llm(prompt) or {}
        patterns = result.get('patterns', []) if isinstance(result, dict) else []

        novel = 0
        for p in patterns:
            if not isinstance(p, dict) or not p.get('name'):
                continue
            if p.get('is_novel'):
                novel += 1
            self._post(f"{self.base_url}/api/discovery/patterns", {
                'experiment_id': experiment_id,
                'name': p.get('name'),
                'description': p.get('description', ''),
                'mechanism': p.get('mechanism', ''),
                'involved_agents': p.get('involved_agents', []) or [],
                'evidence': p.get('evidence', []) or [],
                'is_novel': bool(p.get('is_novel', True)),
                'known_category': p.get('known_category'),
                'first_seen_cycle': window_start,
                'proposed_rule': p.get('proposed_rule'),
            })

        self._post(f"{self.base_url}/api/discovery/runs", {
            'experiment_id': experiment_id, 'cycle': cycle,
            'window_start_cycle': window_start,
            'patterns_found': len(patterns), 'novel_count': novel,
            'llm_reasoning': (result.get('summary', '') if isinstance(result, dict) else '')[:2000],
        })
        return {'patterns_found': len(patterns), 'novel': novel}

    def _call_llm(self, prompt: str):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
            response = client.messages.create(
                model=self.model,
                # Generous budget: Sonnet-5 emits a thinking block AND a multi-pattern
                # JSON with evidence; 4096 truncated mid-JSON (stop_reason=max_tokens).
                max_tokens=int(os.environ.get('DISCOVERY_MAX_TOKENS', '16000')),
                system=DISCOVERY_SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': prompt}], timeout=_TIMEOUT)
            raw = LLMAuditor._response_text(response)          # ThinkingBlock-safe
            return LLMAuditor._extract_json_obj(raw)           # tolerant JSON parse
        except Exception as e:
            print(f'[DiscoveryAgent] discovery call failed: {e}')
            return None

    @staticmethod
    def _get(url: str) -> dict:
        r = httpx.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _post(url: str, payload: dict):
        try:
            httpx.post(url, json=payload, timeout=_TIMEOUT)
        except Exception as e:
            print(f'[DiscoveryAgent] persist failed: {e}')
