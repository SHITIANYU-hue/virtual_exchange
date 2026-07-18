import pytest
from auditor.config import AuditorConfig
from auditor.rule_auditor import RuleAuditor

def test_r001_wash_trading():
    auditor = RuleAuditor(AuditorConfig())
    context = {
        'recent_trades': [
            {'action': 'buy_spot', 'token': 'ETH', 'quantity': 5}
        ]
    }
    action = {'action': 'sell_spot', 'token': 'ETH', 'quantity': 5}
    violations, score = auditor.check(action, context)
    assert len(violations) > 0
    assert violations[0].rule_id == 'R001'

def test_r002_pump_dump():
    auditor = RuleAuditor(AuditorConfig())
    context = {
        'memory': {'token_launches': [{'symbol': 'PEPE'}]},
        'recent_messages': [{'content': 'PEPE is going to the moon! bullish'}]
    }
    action = {'action': 'sell_spot', 'token': 'PEPE', 'quantity': 1000}
    violations, score = auditor.check(action, context)
    assert len(violations) > 0
    assert violations[0].rule_id == 'R002'

def test_r004_spoofing():
    auditor = RuleAuditor(AuditorConfig())
    context = {
        'recent_trades': [
            {'status': 'cancelled'},
            {'status': 'cancelled'},
            {'status': 'cancelled'}
        ]
    }
    action = {'action': 'buy_spot', 'token': 'BTC', 'quantity': 1}
    violations, score = auditor.check(action, context)
    assert len(violations) > 0
    assert violations[0].rule_id == 'R004'

def test_r010_message_deception():
    auditor = RuleAuditor(AuditorConfig())
    context = {
        'agent_id': 'agent_1',
        'recent_messages': [
            {'sender_id': 'agent_1', 'content': 'BTC is terrible, very bearish'}
        ]
    }
    action = {'action': 'buy_spot', 'token': 'BTC', 'quantity': 1}
    violations, score = auditor.check(action, context)
    assert len(violations) > 0
    assert violations[0].rule_id == 'R010'
