import logging

import pytest

from app.cost import MODEL_PRICING, cost_for
from app.llm import MODEL, MODEL_CHEAP


def test_pricing_table_covers_both_model_tiers():
    assert MODEL in MODEL_PRICING
    assert MODEL_CHEAP in MODEL_PRICING


def test_cost_for_input_tokens_only():
    in_rate, _ = MODEL_PRICING[MODEL]
    assert cost_for(MODEL, 1_000_000, 0) == pytest.approx(in_rate)


def test_cost_for_output_tokens_only():
    _, out_rate = MODEL_PRICING[MODEL]
    assert cost_for(MODEL, 0, 1_000_000) == pytest.approx(out_rate)


def test_cost_for_mixed_tokens_is_sum_of_both_sides():
    in_rate, out_rate = MODEL_PRICING[MODEL]
    assert cost_for(MODEL, 2_000_000, 500_000) == pytest.approx(2 * in_rate + 0.5 * out_rate)


def test_cost_for_zero_tokens_is_zero():
    assert cost_for(MODEL, 0, 0) == 0.0


def test_cost_for_unknown_model_is_zero_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        result = cost_for("some/unknown-model", 1_000_000, 1_000_000)
    assert result == 0.0
    assert any("unknown-model" in r.message for r in caplog.records)
