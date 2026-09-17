# AI Security Review — 2026-09-15

Scope: OWASP LLM Top-10-style review of the agent pipeline (guardrails,
tool execution, RAG retrieval, output handling). Findings are from reading
the actual code — `app/guardrails/{engine,patterns}.py`,
`app/tools/rest_adapter.py`, `app/graph/{workers,tool_schemas}.py`,
`app/api/{documents,tools}.py` — not from the README's claims.

## What's already solid

| Control | Where | Note |
|---|---|---|
| Prompt injection (direct) | `guardrails/engine.py::check_input` | regex heuristics + Groq classifier fallback |
| Indirect injection (RAG) | same, scans `chunk_texts` too | retrieved context screened, not just user input |
| Tool abuse | `graph/tool_schemas.py::sanitize_tools` | autonomous tool set hard-filtered to GET only, *before* the model ever sees the schema — deny by construction |
| SSRF | `tools/rest_adapter.py::_guard_url` | blocks private/link-local/reserved IPs, `follow_redirects=False` |
| Excessive agency | tool set is read-only; deploy endpoint is owner-only + disabled by default | no open-ended autonomous write loop |
| Data leakage (PII) | `guardrails/engine.py::apply_post` | regex-masks email/phone/SSN/credit-card from answers before persistence |
| AuthZ | RLS-only, `app/auth.py` | proper JWKS-based JWT verify, ES256, audience check |

## Findings, prioritized

**Update 2026-09-15**: P0 items 1-2 and P1 items 3-4 below are FIXED
(`app/guardrails/{engine,patterns}.py`, `app/graph/workers.py`) and covered
by new tests in `test_guardrails.py` / `test_graph.py`. Full suite: 185
passed. P2 items (SSRF TOCTOU, ingestion-time flagging) are left as
documented residual risk per the rationale below — not fixed this pass.

### P0 — fail-closed the injection classifier — FIXED
`check_input`'s Groq classifier call catches all exceptions and returns
`InputVerdict(True, ...)` — i.e. if Groq is down, times out, or returns
malformed JSON, the run proceeds *unscreened* except for the regex pass.
Regex is the weak layer (easily evaded with paraphrase); the classifier is
the real defense. A fail-open security check means the guardrail
degrades exactly when it's under adversarial pressure (an attacker who
can trigger classifier errors bypasses screening entirely).
**Fix**: fail closed — on classifier error, block the run with a
`503`-style "guardrail unavailable, try again" rather than let it through.
Keep the regex pass as a fast-path allow only when it's *also* clean and
add a circuit breaker so a genuine Groq outage doesn't hard-block all
traffic — but default to deny, not allow, on ambiguity.

### P0 — add a secret-pattern set alongside PII — FIXED
`guardrails/patterns.py::PII_PATTERNS` covers email/phone/SSN/credit-card
only. Nothing catches API keys, bearer tokens, AWS-style credentials,
private-key blocks, etc. in either direction (input *or* output). This is
the same gap as AIRRA's `secret_redactor.py` (OWASP LLM06) closes for that
project — port the pattern set, don't design a new one.
**Fix**: add a `SECRET_PATTERNS` dict (common key-prefix formats: `sk-`,
`ghp_`, `AKIA`, `-----BEGIN ... PRIVATE KEY-----`, generic
high-entropy-token heuristic) and run it through `apply_post` alongside
PII masking. Consider also screening *input* before it's persisted to
`runs`/history, not just the answer.

### P1 — screen tool output for second-order injection — FIXED
`execute_tool_call` returns raw tool response body (truncated, but
unscreened) straight into `scratch.tools`, which `executor_node` then
folds into the prompt for the next LLM call. A tool response is
attacker-influenceable content (if the GET endpoint returns
user-controlled data) with the same injection risk as a RAG chunk, but it
never goes through `check_input`'s pattern/classifier pass — only the
original input and RAG chunks do.
**Fix**: run `_first_pattern_hit` (and ideally the classifier, budget
permitting) over tool result bodies before they're added to
`scratch.tools`, same as chunk_texts today.

### P1 — fix the classifier's truncation blind spot — PARTIALLY FIXED
`CLASSIFIER_INPUT_CHARS = 4000` total and `CHUNK_SCAN_CHARS = 2000` per
chunk mean a payload placed past those offsets — or split across a chunk
boundary — is invisible to both the regex pass and the classifier.
**Fix**: at minimum, scan the *tail* of long chunks too (injection payloads
are often appended, not prepended, to look like trailing instructions);
consider a sliding-window regex pass over the full chunk instead of a
single prefix slice, since regex is cheap. Classifier budget is a real
constraint (cost + Groq context limits) — document the accepted blind spot
if not fully closing it.

Done: the regex pass now scans both the head and tail of every chunk
(`_chunk_scan_windows` in `engine.py`), closing the cheap half of the gap.
`CLASSIFIER_INPUT_CHARS` itself is untouched — the classifier's combined
digest is still capped at 4000 chars, so a payload buried in the middle of
a very long chunk set can still miss the LLM classifier pass specifically
(though it's still caught if it lands in either scanned window of the
regex pass). Documented in-code as an accepted residual risk; raise the
budget if this gets exploited in practice.

### P2 — DNS-rebinding TOCTOU on the SSRF guard
`_guard_url` resolves the hostname via `socket.getaddrinfo` once, then
`httpx.request` re-resolves independently moments later. An attacker
controlling DNS for their tool's target host can return a public IP at
guard-check time and a private IP at request time.
**Fix**: resolve once, pin the IP, and pass the resolved IP (with a `Host`
header override) to `httpx.request` instead of letting it re-resolve — or
accept the residual risk explicitly with a comment, since this requires
the attacker to also control a tool config, which is already an
authenticated, owner-scoped action.

### P2 — no ingestion-time RAG poisoning check
Documents are only screened for injection at *retrieval* time (when a
run pulls chunks into context), not at *upload* time
(`app/api/documents.py::upload_document`). Retrieval-time screening is
arguably the right primary control (it's where the content actually
reaches the model), but there's no way to flag or reject an obviously
poisoned document at ingestion, so poisoned content sits in the corpus
indefinitely, re-triggering the guardrail on every retrieval that hits it.
**Fix**: low priority given retrieval-time coverage exists — optionally run
the same pattern scan at upload time and store a `flagged: bool` on the
document row for operator visibility, not as a hard block (avoid blocking
legitimate uploads that happen to contain a false-positive phrase).

## Explicitly out of scope / accepted as-is

- Loopback allowed in `_guard_url` — low risk in this deployment (container
  loopback, not the docker network), not fixed this pass.
- `/tools/{tool_id}/invoke` (human-driven direct endpoint) isn't GET-filtered
  like the autonomous loop — different threat model (authenticated human,
  RLS-scoped), not a bypass of the agent's own boundary.
- RBAC / audit log / data classification — tracked separately as compliance
  gaps, not AI-security-specific; see the broader compliance review.

## Suggested order of work

1. Fail-closed classifier (P0, smallest diff — one `except` branch)
2. Secret pattern set (P0, port from AIRRA's `secret_redactor.py`)
3. Tool-output injection scan (P1, reuses existing `_first_pattern_hit`)
4. Classifier truncation tail-scan (P1)
5. SSRF TOCTOU fix (P2, only if this becomes multi-tenant / higher-trust-boundary)
6. Ingestion-time flagging (P2, nice-to-have operator visibility)
