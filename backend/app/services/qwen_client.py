import logging

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger("qwen_client")
settings = get_settings()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.qwen_base_url,
            api_key=settings.qwen_api_key,
            timeout=settings.qwen_timeout_seconds,
        )
    return _client


def ask_qwen(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    meta: dict | None = None,
) -> str:
    """max_tokens verilmezse ayarlardaki üst sınır kullanılır. Üretilen her
    token ayrı ayrı beklendiği için bu sınır doğrudan cevap süresini etkiler;
    kısa çıktı beklenen çağrılarda (örn. PubMed anahtar kelimesi) küçük bir
    değer verilmeli.

    meta verilirse `finish_reason` oraya yazılır. "length" gelmesi cevabın
    sınıra takılıp YARIDA KESİLDİĞİ anlamına gelir; bunu bilmeden yarım bir
    klinik cevap tam sanılabiliyordu.
    """
    client = get_client()
    extra_body = {"enable_thinking": False} if settings.qwen_disable_thinking else None
    response = client.chat.completions.create(
        model=settings.qwen_model,
        temperature=temperature,
        max_tokens=max_tokens or settings.qwen_max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        extra_body=extra_body,
    )
    choice = response.choices[0]
    if meta is not None:
        meta["finish_reason"] = choice.finish_reason
    return choice.message.content or ""
