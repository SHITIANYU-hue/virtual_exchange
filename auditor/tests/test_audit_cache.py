import pytest
from auditor.audit_cache import AuditCache
from auditor.models import AuditVerdictType

def test_audit_cache():
    cache = AuditCache(max_size=10)
    
    patterns = [
        {'agent_role': 'retail', 'action_type': 'buy_spot', 'asset': 'BTC', 'size_bucket': 'small', 'scope': 'universal'},
        {'agent_role': 'whale', 'action_type': 'sell_spot', 'asset': 'ETH', 'size_bucket': 'large', 'scope': 'once'}
    ]
    
    cache.store(patterns)
    
    # Universal hit
    verdict = cache.lookup('retail', 'buy_spot', 'BTC', 'small')
    assert verdict == AuditVerdictType.ALLOWED
    
    # Universal hit again (stays in cache)
    verdict = cache.lookup('retail', 'buy_spot', 'BTC', 'small')
    assert verdict == AuditVerdictType.ALLOWED
    
    # Once hit
    verdict = cache.lookup('whale', 'sell_spot', 'ETH', 'large')
    assert verdict == AuditVerdictType.ALLOWED
    
    # Once miss (consumed)
    verdict = cache.lookup('whale', 'sell_spot', 'ETH', 'large')
    assert verdict is None
    
    # Cache flush
    cache.flush_all()
    verdict = cache.lookup('retail', 'buy_spot', 'BTC', 'small')
    assert verdict is None
