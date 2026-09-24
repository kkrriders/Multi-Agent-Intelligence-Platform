import json
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

import app.llm as llm_module
from app.graph import build_graph, make_initial_state
from app.main import app
from app.metrics import NAMESPACE, instrument_node

client = TestClient(app)


def _sample(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


# ---- /metrics endpoint ----

def test_metrics_endpoint_serves_prometheus_text():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests_total" in response.text


# ---- api middleware ----

def test_api_middleware_counts_request_by_status():
    labels = {"service": "api", "namespace": NAMESPACE, "status": "200"}
    before = _sample("http_requests_total", labels)
    client.get("/health")
    assert _sample("http_requests_total", labels) == before + 1


def test_metrics_scrape_is_not_self_counted():
    before = _sample("http_requests_total", {"service": "api", "namespace": NAMESPACE, "status": "200"})
    client.get("/metrics")
    after = _sample("http_requests_total", {"service": "api", "namespace": NAMESPACE, "status": "200"})
    assert after == before


# ---- node wrapper ----

def test_node_wrapper_records_success_series():
    count_labels = {"service": "tool_runner", "namespace": NAMESPACE, "status": "200"}
    dur_labels = {"service": "tool_runner", "namespace": NAMESPACE}
    before_count = _sample("http_requests_total", count_labels)
    before_dur = _sample("http_request_duration_seconds_count", dur_labels)

    wrapped = instrument_node("tool_runner", lambda state: {**state, "ran": True})
    assert wrapped({"x": 1}) == {"x": 1, "ran": True}

    assert _sample("http_requests_total", count_labels) == before_count + 1
    assert _sample("http_request_duration_seconds_count", dur_labels) == before_dur + 1


def test_node_wrapper_records_failure_and_reraises():
    labels = {"service": "verifier", "namespace": NAMESPACE, "status": "500"}
    before = _sample("http_requests_total", labels)

    def boom(state):
        raise RuntimeError("node blew up")

    with pytest.raises(RuntimeError, match="node blew up"):
        instrument_node("verifier", boom)({})

    assert _sample("http_requests_total", labels) == before + 1


def test_chaos_fail_node_env_forces_the_named_node_to_raise(monkeypatch):
    calls = []
    wrapped = instrument_node("researcher", lambda state: calls.append(state))

    monkeypatch.setenv("CHAOS_FAIL_NODE", "researcher")
    with pytest.raises(RuntimeError, match="CHAOS_FAIL_NODE"):
        wrapped({})
    assert calls == []  # underlying node never ran


def test_chaos_fail_node_leaves_other_nodes_alone(monkeypatch):
    monkeypatch.setenv("CHAOS_FAIL_NODE", "executor")
    assert instrument_node("researcher", lambda state: "ok")({}) == "ok"


# ---- graph assembly is instrumented (spec Phase A1 step 6) ----

def test_build_graph_emits_per_node_request_series(monkeypatch):
    monkeypatch.setattr("app.graph.routing.generate", lambda *a, **k: json.dumps({"next": "done"}))
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: "stub answer")

    labels = {"service": "executor", "namespace": NAMESPACE, "status": "200"}
    before = _sample("http_requests_total", labels)

    build_graph({}).invoke(
        make_initial_state(input="hi", history=[], memory_context=[], retrieved_chunks=[], tool_specs=[])
    )

    assert _sample("http_requests_total", labels) >= before + 1


# ---- llm gateway error counter ----

class _FakeRateLimitError(Exception):
    status_code = 429


def test_generate_records_llm_gateway_error_and_reraises(monkeypatch):
    llm_module.reset_usage()
    llm_module.set_node("tool_runner")

    def raise_rate_limit(**kwargs):
        raise _FakeRateLimitError("429 too many requests")

    monkeypatch.setattr(llm_module._client.chat.completions, "create", raise_rate_limit)

    err_labels = {"service": "tool_runner", "kind": "rate_limit"}
    dep_labels = {"service": "tool_runner", "dependency": "groq"}
    before_err = _sample("llm_gateway_errors_total", err_labels)
    before_dep = _sample("service_dependency_failures_total", dep_labels)

    with pytest.raises(_FakeRateLimitError):
        llm_module.generate([{"role": "user", "content": "hi"}])

    assert _sample("llm_gateway_errors_total", err_labels) == before_err + 1
    assert _sample("service_dependency_failures_total", dep_labels) == before_dep + 1


def test_generate_classifies_timeout_errors(monkeypatch):
    llm_module.reset_usage()
    llm_module.set_node("executor")

    class _FakeTimeoutError(Exception):
        pass

    def raise_timeout(**kwargs):
        raise _FakeTimeoutError("request timed out")

    monkeypatch.setattr(llm_module._client.chat.completions, "create", raise_timeout)

    labels = {"service": "executor", "kind": "timeout"}
    before = _sample("llm_gateway_errors_total", labels)
    with pytest.raises(_FakeTimeoutError):
        llm_module.generate([{"role": "user", "content": "hi"}])
    assert _sample("llm_gateway_errors_total", labels) == before + 1
