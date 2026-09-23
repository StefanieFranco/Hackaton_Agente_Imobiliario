"""Retriever RAG sobre Chroma (com fallback textual)."""

from __future__ import annotations

from typing import Any

from src.rag.fallback import keyword_retrieve


def retrieve(query: str, k: int = 4, filtro: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        from src.llm import ollama_available
        from src.rag.ingest import get_vectorstore

        if not ollama_available():
            return keyword_retrieve(query, k=k, filtro=filtro)

        store = get_vectorstore()
        if filtro:
            docs = store.similarity_search(query, k=k, filter=filtro)
        else:
            docs = store.similarity_search(query, k=k)
        if not docs:
            return keyword_retrieve(query, k=k, filtro=filtro)
        return [
            {"conteudo": d.page_content, "metadata": dict(d.metadata or {})}
            for d in docs
        ]
    except Exception:
        return keyword_retrieve(query, k=k, filtro=filtro)


def format_context(docs: list[dict[str, Any]]) -> str:
    if not docs:
        return "Nenhum documento recuperado."
    parts = []
    for i, d in enumerate(docs, 1):
        titulo = d.get("metadata", {}).get("titulo", "doc")
        parts.append(f"[{i}] {titulo}\n{d['conteudo']}")
    return "\n\n---\n\n".join(parts)
