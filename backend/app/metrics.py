"""Prometheus metrics for the AIRRA integration.

See docs/superpowers/specs/2026-09-10-airra-ai-platform-integration-design.md.
AIRRA scrapes /metrics and drives anomaly detection off the three golden
signals (request_rate, error_rate, latency_p95) per logical service, where
`service` is one of api / orchestrator / researcher / tool_runner / executor /
verifier.

The graph nodes run in-process, not as HTTP handlers, so their
`http_requests_total` is emitted by `instrument_node` below (one node
execution = one request). `api` is the only real HTTP service; its counter
comes from middleware in app.main.
"""

import os
import time

from prometheus_client import Counter, Histogram

# ponytail: constant. In Phase C (k8s) the namespace label comes from the pod,
# not from here.
NAMESPACE = "ai-platform"

http_requests_total = Counter(
    "http_requests_total",
    "Requests per logical service (one graph-node execution counts as one request)",
    ["service", "namespace", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Request duration per logical service, in seconds",
    ["service", "namespace"],
)
service_dependency_failures_total = Counter(
    "service_dependency_failures_total",
    "Calls from a service to a downstream dependency that raised",
    ["service", "dependency"],
)
llm_gateway_errors_total = Counter(
    "llm_gateway_errors_total",
    "Groq gateway errors, by kind",
    ["service", "kind"],
)


def observe_request(service: str, status: str, seconds: float) -> None:
    http_requests_total.labels(service=service, namespace=NAMESPACE, status=status).inc()
    http_request_duration_seconds.labels(service=service, namespace=NAMESPACE).observe(seconds)


def groq_error_kind(exc: BaseException) -> str:
    """Map a Groq client exception onto the contract's kinds: timeout | rate_limit | 5xx."""
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "ratelimit" in name or getattr(exc, "status_code", None) == 429:
        return "rate_limit"
    return "5xx"


def instrument_node(name: str, fn):
    """Wrap a LangGraph node callable: time the call, emit
    http_requests_total + http_request_duration_seconds for service=<name>,
    and count any exception as status=500 (then re-raise).

    CHAOS_FAIL_NODE=<name> forces this node to raise before running — the
    worker-crash injection for the chaos harness (spec Phase A1 step 5).
    """

    def wrapped(state):
        start = time.perf_counter()
        try:
            if os.environ.get("CHAOS_FAIL_NODE") == name:
                raise RuntimeError(f"CHAOS_FAIL_NODE: forced failure of node {name!r}")
            result = fn(state)
        except Exception:
            observe_request(name, "500", time.perf_counter() - start)
            raise
        observe_request(name, "200", time.perf_counter() - start)
        return result

    return wrapped
