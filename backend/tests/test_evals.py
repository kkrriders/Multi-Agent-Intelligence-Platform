import app.evals as evals
from app.evals import aggregate, judge_item


def test_aggregate_empty_is_all_zero():
    assert aggregate([]) == {"accuracy": 0.0, "hallucination_rate": 0.0, "mean_score": 0.0}


def test_aggregate_computes_fractions_and_mean():
    r = [
        {"score": 0.9, "hallucinated": False},
        {"score": 0.8, "hallucinated": False},
        {"score": 0.5, "hallucinated": True},
        {"score": 0.2, "hallucinated": True},
    ]
    out = aggregate(r)
    assert out["accuracy"] == 0.5
    assert out["hallucination_rate"] == 0.5
    assert round(out["mean_score"], 3) == 0.6


def test_judge_item_passes_valid_json_through(monkeypatch):
    monkeypatch.setattr(evals, "generate", lambda *a, **k: '{"score": 0.83, "hallucinated": false, "reason": "close"}')
    v = judge_item("q", "ref", "ans")
    assert v == {"score": 0.83, "hallucinated": False, "reason": "close"}


def test_judge_item_clamps_score(monkeypatch):
    monkeypatch.setattr(evals, "generate", lambda *a, **k: '{"score": 1.7, "hallucinated": true, "reason": "x"}')
    assert judge_item("q", "r", "a")["score"] == 1.0
    monkeypatch.setattr(evals, "generate", lambda *a, **k: '{"score": -3, "hallucinated": false, "reason": "x"}')
    assert judge_item("q", "r", "a")["score"] == 0.0


def test_judge_item_unparseable_is_worst_case(monkeypatch):
    monkeypatch.setattr(evals, "generate", lambda *a, **k: "not json")
    v = judge_item("q", "r", "a")
    assert v["score"] == 0.0 and v["hallucinated"] is True
    assert "unparseable" in v["reason"]


def test_judge_item_generate_error_is_worst_case(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("groq 400 json_validate_failed")

    monkeypatch.setattr(evals, "generate", boom)
    v = judge_item("q", "r", "a")
    assert v["score"] == 0.0 and v["hallucinated"] is True


def test_judge_item_uses_cheap_model(monkeypatch):
    from app.llm import MODEL_CHEAP

    calls = []
    monkeypatch.setattr(evals, "generate", lambda *a, **k: calls.append(k) or '{"score": 1, "hallucinated": false, "reason": ""}')
    judge_item("q", "r", "a")
    assert calls[0]["model"] == MODEL_CHEAP
