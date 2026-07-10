"""
Tests for run_experiment.py's bad-cycle classification.

Run directly: python3 experiments/test_run_experiment.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import anthropic

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
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
