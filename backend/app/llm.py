from groq import Groq

from app.config import settings

_client = Groq(api_key=settings.groq_api_key)

MODEL = "openai/gpt-oss-120b"


def generate(messages: list[dict]) -> str:
    response = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    return response.choices[0].message.content
