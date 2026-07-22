import logging

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger("qwen_client")
settings = get_settings()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=settings.qwen_base_url, api_key=settings.qwen_api_key)
    return _client


def ask_qwen(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=settings.qwen_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""
