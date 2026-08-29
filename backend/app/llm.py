from groq import Groq

from app.config import settings

_client = Groq(api_key=settings.groq_api_key)

MODEL = "openai/gpt-oss-120b"


def generate(messages: list[dict], *, tools: list[dict] | None = None, response_format: dict | None = None):
    # Groq rejects tool_choice / response_format when passed as None — only
    # include a kwarg when it actually has a value.
    kwargs: dict = {"model": MODEL, "messages": messages, "timeout": 30}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if response_format is not None:
        kwargs["response_format"] = response_format

    response = _client.chat.completions.create(**kwargs)
    message = response.choices[0].message
    return message if tools else message.content
