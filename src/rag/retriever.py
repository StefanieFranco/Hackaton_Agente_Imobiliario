"""Retriever RAG — hybrid search (BM25 + vetorial + RRF) com fallback."""

from __future__ import annotations

from typing import Any

from src.rag.fallback import keyword_retrieve
from src.rag.hybrid import hybrid_retrieve


def retrieve(
    query: str,
    k: int = 4,
    filtro: dict[str, Any] | None = None,
    structured: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Entrada principal de recuperação.

    - `filtro`: igualdade simples de metadata (ex.: {"tipo": "juridico"})
    - `structured`: filtros de catálogo (bairro, preco_min/max, quartos_min/max, segmento, tipo)
    """
    try:
        results = hybrid_retrieve(
            query,
            k=k,
            filtro=filtro,
            structured=structured,
        )
        if results:
            return results
    except Exception:
        pass

    # Fallback lexical simples
    docs = keyword_retrieve(query, k=k * 3, filtro=filtro)
    if structured:
        filtered = []
        for d in docs:
            meta = d.get("metadata") or {}
            ok = True
            if structured.get("bairro") and structured["bairro"].lower() not in str(meta.get("bairro", "")).lower():
                if meta.get("doc_kind") == "imovel" or meta.get("tipo") == "imovel":
                    ok = False
            if structured.get("preco_max") is not None and meta.get("preco") is not None:
                if float(meta["preco"]) > float(structured["preco_max"]) and float(meta["preco"]) >= 0:
                    ok = False
            if structured.get("preco_min") is not None and meta.get("preco") is not None:
                if 0 <= float(meta["preco"]) < float(structured["preco_min"]):
                    ok = False
            if structured.get("quartos_min") is not None and meta.get("quartos") is not None:
                if int(meta["quartos"]) >= 0 and int(meta["quartos"]) < int(structured["quartos_min"]):
                    ok = False
            if structured.get("segmento") and meta.get("segmento") and meta["segmento"] != structured["segmento"]:
                ok = False
            if ok:
                filtered.append(d)
        docs = filtered or docs[:k]
    return docs[:k]


def format_context(docs: list[dict[str, Any]]) -> str:
    if not docs:
        return "Nenhum documento recuperado."
    parts = []
    for i, d in enumerate(docs, 1):
        titulo = d.get("metadata", {}).get("titulo", "doc")
        score = d.get("score")
        mode = d.get("retrieval", "rag")
        header = f"[{i}] {titulo}"
        if score is not None:
            header += f" (score={score:.4f}, {mode})"
        parts.append(f"{header}\n{d['conteudo']}")
    return "\n\n---\n\n".join(parts)
