"""Hybrid search: vetorial (Chroma) + BM25 (keyword) com Reciprocal Rank Fusion.

Suporta filtros estruturados para local, preço e quartos — ideais para catálogo
imobiliário, onde similarity semântica sozinha falha em restrições numéricas.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from src.rag.ingest import build_documents


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúãõâêôç0-9]+", text.lower())


def _is_property_doc(meta: dict[str, Any]) -> bool:
    return meta.get("doc_kind") == "imovel" or meta.get("tipo") == "imovel"


def _passes_structured(meta: dict[str, Any], structured: dict[str, Any] | None) -> bool:
    """Aplica filtros de catálogo. Docs não-imóvel passam (úteis como contexto RAG)."""
    if not structured:
        return True
    if not _is_property_doc(meta):
        # Se a busca pede só imóveis (flag), descarta docs gerais
        if structured.get("somente_imoveis"):
            return False
        return True

    if structured.get("segmento") and meta.get("segmento") != structured["segmento"]:
        return False

    wanted_tipo = structured.get("property_tipo") or structured.get("tipo_imovel")
    if wanted_tipo and meta.get("property_tipo") != wanted_tipo:
        return False

    if structured.get("bairro"):
        b = str(meta.get("bairro", "")).lower()
        if structured["bairro"].lower() not in b:
            return False

    preco = meta.get("preco")
    if preco is not None and float(preco) >= 0:
        if structured.get("preco_min") is not None and float(preco) < float(structured["preco_min"]):
            return False
        if structured.get("preco_max") is not None and float(preco) > float(structured["preco_max"]):
            return False

    quartos = meta.get("quartos")
    if quartos is not None and int(quartos) >= 0:
        if structured.get("quartos_min") is not None and int(quartos) < int(structured["quartos_min"]):
            return False
        if structured.get("quartos_max") is not None and int(quartos) > int(structured["quartos_max"]):
            return False

    return True


def _passes_equality_filter(meta: dict[str, Any], filtro: dict[str, Any] | None) -> bool:
    if not filtro:
        return True
    for key, val in filtro.items():
        if meta.get(key) != val:
            return False
    return True


def _doc_key(doc: Document) -> str:
    meta = doc.metadata or {}
    return str(meta.get("doc_id") or meta.get("titulo") or id(doc))


@lru_cache(maxsize=1)
def _bm25_index() -> tuple[BM25Okapi, tuple[Document, ...]]:
    docs = tuple(build_documents())
    corpus = [_tokenize(d.page_content) for d in docs]
    return BM25Okapi(corpus), docs


def invalidate_bm25_cache() -> None:
    _bm25_index.cache_clear()


def bm25_search(
    query: str,
    k: int = 10,
    filtro: dict[str, Any] | None = None,
    structured: dict[str, Any] | None = None,
) -> list[tuple[Document, float]]:
    bm25, docs = _bm25_index()
    scores = bm25.get_scores(_tokenize(query))
    ranked: list[tuple[Document, float]] = []
    for doc, score in zip(docs, scores):
        meta = dict(doc.metadata or {})
        if not _passes_equality_filter(meta, filtro):
            continue
        if not _passes_structured(meta, structured):
            continue
        if score <= 0:
            continue
        ranked.append((doc, float(score)))
    ranked.sort(key=lambda x: -x[1])
    return ranked[:k]


def _chroma_where(filtro: dict[str, Any] | None, structured: dict[str, Any] | None) -> dict[str, Any] | None:
    """Monta filtro Chroma ($and). Bairro parcial é pós-filtrado (Chroma só tem $eq)."""
    clauses: list[dict[str, Any]] = []
    if filtro:
        for key, val in filtro.items():
            clauses.append({key: {"$eq": val}})
    if structured:
        if structured.get("somente_imoveis"):
            clauses.append({"doc_kind": {"$eq": "imovel"}})
        if structured.get("segmento"):
            clauses.append({"segmento": {"$eq": structured["segmento"]}})
        wanted_tipo = structured.get("property_tipo") or structured.get("tipo_imovel")
        if wanted_tipo:
            clauses.append({"property_tipo": {"$eq": wanted_tipo}})
        if structured.get("preco_min") is not None:
            clauses.append({"preco": {"$gte": float(structured["preco_min"])}})
        if structured.get("preco_max") is not None:
            clauses.append({"preco": {"$lte": float(structured["preco_max"])}})
        if structured.get("quartos_min") is not None:
            clauses.append({"quartos": {"$gte": int(structured["quartos_min"])}})
        if structured.get("quartos_max") is not None:
            clauses.append({"quartos": {"$lte": int(structured["quartos_max"])}})
        # bairro exato ajuda no Chroma; parcial fica no pós-filtro
        if structured.get("bairro") and " " not in structured["bairro"].strip():
            clauses.append({"bairro": {"$eq": structured["bairro"]}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def vector_search(
    query: str,
    k: int = 10,
    filtro: dict[str, Any] | None = None,
    structured: dict[str, Any] | None = None,
) -> list[tuple[Document, float]]:
    from src.llm import ollama_available
    from src.rag.ingest import get_vectorstore

    if not ollama_available():
        return []

    store = get_vectorstore()
    try:
        if store._collection.count() == 0:
            return []
    except Exception:
        return []
    where = _chroma_where(filtro, structured)
    try:
        if where:
            pairs = store.similarity_search_with_relevance_scores(query, k=k, filter=where)
        else:
            pairs = store.similarity_search_with_relevance_scores(query, k=k)
    except Exception:
        try:
            pairs = store.similarity_search_with_relevance_scores(query, k=max(k * 3, 12))
        except Exception:
            return []

    out: list[tuple[Document, float]] = []
    for doc, score in pairs:
        meta = dict(doc.metadata or {})
        if not _passes_equality_filter(meta, filtro):
            continue
        if not _passes_structured(meta, structured):
            continue
        out.append((doc, float(score)))
    return out[:k]


def reciprocal_rank_fusion(
    rankings: list[list[tuple[Document, float]]],
    k: int = 4,
    rrf_k: int = 60,
) -> list[tuple[Document, float]]:
    fused: dict[str, dict[str, Any]] = {}
    for ranking in rankings:
        for rank, (doc, _raw) in enumerate(ranking, start=1):
            key = _doc_key(doc)
            entry = fused.setdefault(key, {"doc": doc, "score": 0.0})
            entry["score"] += 1.0 / (rrf_k + rank)
            entry["doc"] = doc
    ordered = sorted(fused.values(), key=lambda x: -x["score"])
    return [(e["doc"], float(e["score"])) for e in ordered[:k]]


def hybrid_retrieve(
    query: str,
    k: int = 4,
    filtro: dict[str, Any] | None = None,
    structured: dict[str, Any] | None = None,
    fetch_k: int = 12,
) -> list[dict[str, Any]]:
    """
    Hybrid search:
    1) BM25 (lexical) — bairro, '3 quartos', códigos RES-001
    2) Vetorial (Chroma) — semântica ('família', 'perto do metrô')
    3) RRF para fundir rankings
    4) Filtros estruturados (bairro/preço/quartos) em ambos os braços
    """
    bm25_hits = bm25_search(query, k=fetch_k, filtro=filtro, structured=structured)
    vector_hits = vector_search(query, k=fetch_k, filtro=filtro, structured=structured)

    rankings = [r for r in (bm25_hits, vector_hits) if r]
    if not rankings:
        bm25_hits = bm25_search(query, k=fetch_k, filtro=filtro, structured=None)
        rankings = [bm25_hits] if bm25_hits else []

    if not rankings:
        return []

    fused = reciprocal_rank_fusion(rankings, k=k)
    return [
        {
            "conteudo": doc.page_content,
            "metadata": dict(doc.metadata or {}),
            "score": score,
            "retrieval": "hybrid_rrf",
        }
        for doc, score in fused
    ]
