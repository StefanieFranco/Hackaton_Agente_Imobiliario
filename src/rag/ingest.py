"""Ingestão de documentos seed no ChromaDB."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHROMA_COLLECTION, CHROMA_DIR, SEEDS_DIR, ensure_data_dirs
from src.llm import get_embeddings


def _load_json(name: str):
    return json.loads((SEEDS_DIR / name).read_text(encoding="utf-8"))


def build_documents() -> list[Document]:
    docs: list[Document] = []

    for item in _load_json("market_docs.json") + _load_json("legal_docs.json"):
        docs.append(
            Document(
                page_content=f"{item['titulo']}\n\n{item['conteudo']}",
                metadata={
                    "doc_id": item["id"],
                    "tipo": item.get("tipo", "geral"),
                    "titulo": item["titulo"],
                    "fonte": "seed",
                },
            )
        )

    finance = _load_json("finance_rules.json")
    docs.append(
        Document(
            page_content=(
                "Regras de financiamento fictícias\n\n"
                f"Taxa anual: {finance['taxa_anual_percent']}%\n"
                f"Entrada mínima: {finance['entrada_minima_percent']}%\n"
                f"Prazo máximo: {finance['prazo_max_meses']} meses\n"
                f"Sistema: {finance['sistema']}\n"
                f"{finance['observacao']}"
            ),
            metadata={
                "doc_id": "FIN-RULES",
                "tipo": "financiamento",
                "titulo": "Regras de financiamento",
                "fonte": "seed",
            },
        )
    )

    # descrições de imóveis também entram no RAG (amostra rica)
    for name in ("properties_residential.json", "properties_commercial.json"):
        for p in _load_json(name):
            docs.append(
                Document(
                    page_content=(
                        f"{p['titulo']} ({p['id']})\n"
                        f"Segmento: {p['segmento']} | Tipo: {p['tipo']}\n"
                        f"Local: {p['bairro']}, {p['cidade']}\n"
                        f"Preço: R$ {p['preco']:,.2f} | Área: {p['area_m2']} m²\n"
                        f"{p['descricao']}\n"
                        f"Comodidades: {', '.join(p.get('amenities', []))}"
                    ),
                    metadata={
                        "doc_id": p["id"],
                        "tipo": "imovel",
                        "titulo": p["titulo"],
                        "bairro": p["bairro"],
                        "segmento": p["segmento"],
                        "fonte": "seed",
                    },
                )
            )
    return docs


def ingest_all_documents(reset: bool = True) -> int:
    ensure_data_dirs()
    if reset and CHROMA_DIR.exists():
        # remove coleção anterior
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    raw_docs = build_documents()
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
    chunks = splitter.split_documents(raw_docs)

    embeddings = get_embeddings()
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=CHROMA_COLLECTION,
    )
    return len(chunks)


def get_vectorstore() -> Chroma:
    ensure_data_dirs()
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=get_embeddings(),
        collection_name=CHROMA_COLLECTION,
    )
