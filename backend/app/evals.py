import json

from app.llm import MODEL_CHEAP, generate

PASS_THRESHOLD = 0.7
MAX_ITEMS = 20

_JUDGE_SYSTEM = (
    "You are grading an AI answer against a reference. Given INPUT, REFERENCE, and ANSWER, "
    'reply ONLY with JSON: {"score": <0..1 float, how well ANSWER matches REFERENCE and '
    'addresses INPUT>, "hallucinated": <true if ANSWER asserts facts absent from or contrary '
    'to REFERENCE>, "reason": "<one sentence>"}.'
)


def judge_item(input: str, expected: str, output: str) -> dict:
    """One Groq JSON call grading `output` against `expected`. Never raises;
    an unparseable response scores 0.0 / hallucinated."""
    try:
        raw = generate(
            [
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": f"INPUT: {input}\n\nREFERENCE: {expected}\n\nANSWER: {output}"},
            ],
            response_format={"type": "json_object"},
            model=MODEL_CHEAP,
        )
        parsed = json.loads(raw)
        score = float(parsed.get("score", 0.0))
        return {
            "score": max(0.0, min(1.0, score)),
            "hallucinated": bool(parsed.get("hallucinated", False)),
            "reason": str(parsed.get("reason", "")),
        }
    except Exception:  # noqa: BLE001 - judge is fail-open: any failure scores worst-case
        return {"score": 0.0, "hallucinated": True, "reason": "judge response unparseable"}


def aggregate(results: list[dict]) -> dict:
    """{accuracy, hallucination_rate, mean_score} over judged items.
    accuracy = fraction with score >= PASS_THRESHOLD. Empty -> all zeros."""
    if not results:
        return {"accuracy": 0.0, "hallucination_rate": 0.0, "mean_score": 0.0}
    n = len(results)
    return {
        "accuracy": sum(1 for r in results if r["score"] >= PASS_THRESHOLD) / n,
        "hallucination_rate": sum(1 for r in results if r["hallucinated"]) / n,
        "mean_score": sum(r["score"] for r in results) / n,
    }
