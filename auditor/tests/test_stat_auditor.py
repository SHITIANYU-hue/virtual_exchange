import pytest
from auditor.stat_auditor import StatAuditor

def test_volume_anomaly():
    auditor = StatAuditor()
    # 5 previous trades of size 10
    for _ in range(5):
        auditor.update_stats('agent_1', 10.0, 1, 1000.0)
    
    context = {'agent_id': 'agent_1'}
    # New trade of size 1000
    action = {'action': 'buy_spot', 'quantity': 1000.0}
    
    anomalies, score = auditor.check(action, context)
    assert len(anomalies) > 0
    assert anomalies[0].anomaly_type == 'Volume Anomaly'
    assert score > 0

def test_correlation():
    auditor = StatAuditor()
    context = {
        'agent_id': 'agent_1',
        'cycle_trades': [
            {'agent_id': 'agent_2', 'action': {'action': 'buy_spot', 'token': 'ETH'}},
            {'agent_id': 'agent_3', 'action': {'action': 'buy_spot', 'token': 'ETH'}}
        ]
    }
    action = {'action': 'buy_spot', 'token': 'ETH', 'quantity': 1.0}
    
    anomalies, score = auditor.check(action, context)
    assert len(anomalies) > 0
    assert anomalies[0].anomaly_type == 'High Correlation'
    assert score > 0
