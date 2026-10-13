"""Cliente LLM e embeddings via Ollama (Llama 3.1 8B)."""

from __future__ import annotations

from functools import lru_cache

import httpx
from langchain_ollama import ChatOllama, OllamaEmbeddings

from src.config import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
)


def ollama_available(timeout: float = 0.8) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


@lru_cache(maxsize=4)
def get_chat_model(
    model: str | None = None,
    temperature: float | None = None,
    num_predict: int = 320,
) -> ChatOllama:
    return ChatOllama(
        model=model or OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=OLLAMA_TEMPERATURE if temperature is None else temperature,
        # 8B com contexto enorme trava a máquina; resposta curta cabe na demo
        num_ctx=4096,
        num_predict=num_predict,
        keep_alive="10m",
        sync_client_kwargs={"timeout": 180},
    )


@lru_cache(maxsize=2)
def get_embeddings(model: str | None = None) -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=model or OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def invoke_llm(
    system: str,
    user: str,
    model: str | None = None,
    num_predict: int = 320,
) -> tuple[str, bool]:
    """Devolve o texto e se o modelo parou por limite de tokens (resposta cortada)."""
    if not ollama_available():
        raise ConnectionError(
            "Ollama indisponível. Instale/inicie o Ollama e rode "
            "`ollama pull llama3.1:8b`."
        )
    llm = get_chat_model(model=model, num_predict=num_predict)
    response = llm.invoke([("system", system), ("human", user)])
    content = response.content
    text = content if isinstance(content, str) else str(content)
    meta = getattr(response, "response_metadata", None) or {}
    done = str(meta.get("done_reason") or meta.get("finish_reason") or "").lower()
    return text, done in {"length", "max_tokens"}


def invoke_text(
    system: str,
    user: str,
    model: str | None = None,
    num_predict: int = 320,
) -> str:
    text, _truncated = invoke_llm(system, user, model=model, num_predict=num_predict)
    return text
