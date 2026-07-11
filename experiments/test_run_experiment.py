"""
Tests for run_experiment.py's bad-cycle classification.

Run directly: python3 experiments/test_run_experiment.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import anthropic
import openai

import experiments.run_experiment as run_experiment
from experiments.run_experiment import (
    _classify_bad_cycle,
    _is_retryable_llm_error,
    _is_permanent_llm_error,
)


def _status_error(status_code):
    request = httpx.Request("POST", "http://x/v1/messages")
    response = httpx.Response(status_code=status_code, request=request)
    return anthropic.APIStatusError("boom", response=response, body=None)


def _connection_error():
    request = httpx.Request("POST", "http://x/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _openai_status_error(status_code, body=None):
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    response = httpx.Response(status_code=status_code, request=request)
    return openai.APIStatusError("boom", response=response, body=body)


def _openai_quota_exceeded_error():
    # Real body captured from exp2_openai_5cycles_v3_part2/errors/DiamondHands_cycle_37.txt —
    # OpenAI uses status 429 for this AND for ordinary rate limiting, distinguished only
    # by the body's "code" field.
    return _openai_status_error(429, body={
        "message": "You exceeded your current quota, please check your plan and billing details.",
        "type": "insufficient_quota",
        "param": None,
        "code": "insufficient_quota",
    })


def test_classify_bad_cycle_ok_below_error_threshold():
    result = _classify_bad_cycle(cycle_errors=3, cycle_attempted=10, cycle_permanent_errors=3)
    assert result == "ok", f"expected ok, got {result}"
    print("  ok below threshold ✓")


def test_classify_bad_cycle_backoff_when_all_errors_transient():
    # A real network outage — every agent failed with a connection blip.
    # Must keep retrying, not abort (the exp2_sonnet_100cycles_v7 scenario).
    result = _classify_bad_cycle(cycle_errors=10, cycle_attempted=10, cycle_permanent_errors=0)
    assert result == "backoff", f"expected backoff, got {result}"
    print("  backoff on all-transient errors ✓")


def test_classify_bad_cycle_backoff_when_errors_mixed():
    result = _classify_bad_cycle(cycle_errors=10, cycle_attempted=10, cycle_permanent_errors=6)
    assert result == "backoff", f"expected backoff, got {result}"
    print("  backoff on mixed errors ✓")


def test_classify_bad_cycle_abort_when_all_errors_permanent():
    # exp2_fable_100cycles_v2 — every agent failed with the same "Insufficient
    # Balance" 402 every cycle from 27 to 100. Backing off never helps here,
    # so the runner must stop instead of burning the rest of the run.
    result = _classify_bad_cycle(cycle_errors=10, cycle_attempted=10, cycle_permanent_errors=10)
    assert result == "abort", f"expected abort, got {result}"
    print("  abort when all errors permanent ✓")


def test_classify_bad_cycle_ok_when_no_agents_attempted():
    result = _classify_bad_cycle(cycle_errors=0, cycle_attempted=0, cycle_permanent_errors=0)
    assert result == "ok", f"expected ok, got {result}"
    print("  ok when nothing attempted ✓")


def test_is_retryable_llm_error_anthropic_dispatch():
    run_experiment.LLM_PROVIDER = "anthropic"
    assert _is_retryable_llm_error(_status_error(402)) is False
    assert _is_retryable_llm_error(_status_error(429)) is True
    assert _is_retryable_llm_error(_status_error(500)) is True
    assert _is_retryable_llm_error(_connection_error()) is True
    print("  anthropic error dispatch ✓")


def test_is_permanent_llm_error_true_for_client_error_status_codes():
    run_experiment.LLM_PROVIDER = "anthropic"
    assert _is_permanent_llm_error(_status_error(402)) is True  # insufficient balance
    assert _is_permanent_llm_error(_status_error(401)) is True  # bad auth
    assert _is_permanent_llm_error(_status_error(400)) is True  # bad request
    print("  permanent for 400/401/402 ✓")


def test_is_permanent_llm_error_false_for_retryable_status_codes():
    run_experiment.LLM_PROVIDER = "anthropic"
    assert _is_permanent_llm_error(_status_error(429)) is False  # rate limit — retry
    assert _is_permanent_llm_error(_status_error(500)) is False  # server error — retry
    print("  not permanent for 429/500 ✓")


def test_is_permanent_llm_error_false_for_connection_error():
    run_experiment.LLM_PROVIDER = "anthropic"
    assert _is_permanent_llm_error(_connection_error()) is False
    print("  not permanent for dropped connection ✓")


def test_is_permanent_llm_error_false_for_unrecognized_exception():
    # A backend hiccup, a bug in our own code, anything that isn't a
    # positively-identified LLM client error must NOT be treated as permanent —
    # otherwise a single unrelated exception type would abort a multi-hour
    # experiment that a plain backoff-and-retry would have recovered from.
    run_experiment.LLM_PROVIDER = "anthropic"
    assert _is_permanent_llm_error(ValueError("some unrelated bug")) is False
    assert _is_permanent_llm_error(httpx.ConnectError("backend down")) is False
    print("  not permanent for unrecognized exceptions ✓")


def test_is_retryable_llm_error_false_for_openai_insufficient_quota():
    # exp2_openai_5cycles_v3_part2 cycle 37 — DiamondHands and HappyTrader both hit
    # this. OpenAI returns 429 for quota exhaustion same as ordinary rate limiting,
    # but waiting/retrying never helps quota exhaustion — it's a billing wall like
    # the Fable 402 case, just wearing a 429's clothes.
    run_experiment.LLM_PROVIDER = "openai"
    assert _is_retryable_llm_error(_openai_quota_exceeded_error()) is False
    print("  not retryable for openai insufficient_quota ✓")


def test_is_retryable_llm_error_true_for_openai_generic_rate_limit():
    # A 429 without the insufficient_quota code is ordinary rate limiting and
    # must still be retried — the fix must not treat every 429 as permanent.
    run_experiment.LLM_PROVIDER = "openai"
    assert _is_retryable_llm_error(_openai_status_error(429, body={
        "message": "Rate limit reached for requests",
        "type": "requests",
        "param": None,
        "code": "rate_limit_exceeded",
    })) is True
    print("  retryable for openai generic rate limit ✓")


def test_is_permanent_llm_error_true_for_openai_insufficient_quota():
    run_experiment.LLM_PROVIDER = "openai"
    assert _is_permanent_llm_error(_openai_quota_exceeded_error()) is True
    print("  permanent for openai insufficient_quota ✓")


def test_is_permanent_llm_error_false_for_openai_generic_rate_limit():
    run_experiment.LLM_PROVIDER = "openai"
    assert _is_permanent_llm_error(_openai_status_error(429, body={
        "message": "Rate limit reached for requests",
        "type": "requests",
        "param": None,
        "code": "rate_limit_exceeded",
    })) is False
    print("  not permanent for openai generic rate limit ✓")


if __name__ == "__main__":
    test_classify_bad_cycle_ok_below_error_threshold()
    test_classify_bad_cycle_backoff_when_all_errors_transient()
    test_classify_bad_cycle_backoff_when_errors_mixed()
    test_classify_bad_cycle_abort_when_all_errors_permanent()
    test_classify_bad_cycle_ok_when_no_agents_attempted()
    test_is_retryable_llm_error_anthropic_dispatch()
    test_is_permanent_llm_error_true_for_client_error_status_codes()
    test_is_permanent_llm_error_false_for_retryable_status_codes()
    test_is_permanent_llm_error_false_for_connection_error()
    test_is_permanent_llm_error_false_for_unrecognized_exception()
    test_is_retryable_llm_error_false_for_openai_insufficient_quota()
    test_is_retryable_llm_error_true_for_openai_generic_rate_limit()
    test_is_permanent_llm_error_true_for_openai_insufficient_quota()
    test_is_permanent_llm_error_false_for_openai_generic_rate_limit()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
