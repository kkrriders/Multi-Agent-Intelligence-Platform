import os
import pytest

from app.config import settings
from app.llm import generate


@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_generate_returns_nonempty_string():
    result = generate([{"role": "user", "content": "Say the word 'pong' and nothing else."}])
    assert isinstance(result, str)
    assert len(result) > 0
