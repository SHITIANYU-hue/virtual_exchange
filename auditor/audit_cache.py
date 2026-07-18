"""Security Query Cache for Agent Auditor."""
from collections import OrderedDict
import hashlib
from typing import Optional

from auditor.models import AuditVerdictType, CacheScope, CachedVerdict


class AuditCache:
    """Security Query Cache with Once/Task/Universal scopes.
    Adapted from AgentSentinel's Security Query Cache.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.universal_cache: OrderedDict[str, CachedVerdict] = OrderedDict()
        self.task_cache: OrderedDict[str, CachedVerdict] = OrderedDict()
        self.once_cache: OrderedDict[str, CachedVerdict] = OrderedDict()
    
    def _build_key(self, agent_role: str, action_type: str, 
                   asset: str = '', size_bucket: str = '') -> str:
        raw = f"{agent_role}:{action_type}:{asset}:{size_bucket}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def lookup(self, agent_role: str, action_type: str, 
              asset: str = '', size_bucket: str = '') -> Optional[AuditVerdictType]:
        key = self._build_key(agent_role, action_type, asset, size_bucket)
        
        # Check Once first (consume on hit)
        if key in self.once_cache:
            entry = self.once_cache.pop(key)
            return entry.verdict
            
        # Check Task
        if key in self.task_cache:
            self.task_cache.move_to_end(key)
            return self.task_cache[key].verdict
            
        # Check Universal
        if key in self.universal_cache:
            self.universal_cache.move_to_end(key)
            return self.universal_cache[key].verdict
            
        return None
    
    def store(self, verified_patterns: list[dict]):
        for pattern in verified_patterns:
            scope_str = pattern.get('scope', 'once')
            try:
                scope = CacheScope(scope_str)
            except ValueError:
                scope = CacheScope.ONCE
                
            key = self._build_key(
                pattern.get('agent_role', ''),
                pattern.get('action_type', ''),
                pattern.get('asset', ''),
                pattern.get('size_bucket', ''),
            )
            entry = CachedVerdict(verdict=AuditVerdictType.ALLOWED, pattern=pattern)
            
            if scope == CacheScope.ONCE:
                target = self.once_cache
            elif scope == CacheScope.TASK:
                target = self.task_cache
            else:
                target = self.universal_cache
                
            target[key] = entry
            
            # Evict if needed (LRU)
            while len(target) > self.max_size:
                target.popitem(last=False)
    
    def flush_task_cache(self):
        """Clear task-specific caches (called at start of experiment)."""
        self.task_cache.clear()
        self.once_cache.clear()
    
    def flush_all(self):
        """Clear all caches."""
        self.universal_cache.clear()
        self.task_cache.clear()
        self.once_cache.clear()
    
    @property
    def stats(self) -> dict:
        return {
            'universal': len(self.universal_cache),
            'task': len(self.task_cache),
            'once': len(self.once_cache),
        }
