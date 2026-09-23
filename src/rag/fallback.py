"""Fallback de RAG por busca textual quando Chroma/Ollama não estão disponíveis."""

from __future__ import annotations

import json
import re
from typing import Any

from src.config import SEEDS_DIR
from src.rag.ingest import build_documents


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-záéíóúãõâêôç0-9]{3,}", text.lower()))


def keyword_retrieve(query: str, k: int = 4, filtro: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    docs = build_documents()
    q = _tokenize(query)
    scored: list[tuple[int, Any]] = []
    for d in docs:
        meta = dict(d.metadata or {})
        if filtro:
            if any(meta.get(key) != val for key, val in filtro.items()):
                continue
        tokens = _tokenize(d.page_content)
        score = len(q & tokens)
        if score:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    results = []
    for _, d in scored[:k]:
        results.append({"conteudo": d.page_content, "metadata": dict(d.metadata or {})})
    if not results and docs:
        for d in docs[:k]:
            results.append({"conteudo": d.page_content, "metadata": dict(d.metadata or {})})
    return results
