"""USD cost for Groq LLM calls. Rates are per 1M tokens, from Groq's public
pricing — confirm against groq.com/pricing when rates change."""

import logging

from app.llm import MODEL, MODEL_CHEAP

logger = logging.getLogger(__name__)

# model: (usd_per_1M_input_tokens, usd_per_1M_output_tokens)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    MODEL: (0.15, 0.75),
    MODEL_CHEAP: (0.10, 0.50),
}


def cost_for(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD cost of one call. Unknown model -> 0.0 (fail-open) with a warning;
    a run must never fail over a missing price row."""
    rates = MODEL_PRICING.get(model)
    if rates is None:
        logger.warning("no pricing for model %r; charging 0.0", model)
        return 0.0
    in_rate, out_rate = rates
    return prompt_tokens / 1_000_000 * in_rate + completion_tokens / 1_000_000 * out_rate
