"""Ferramenta de busca estruturada no catálogo de imóveis."""

from __future__ import annotations

from typing import Any

from src.db import repository as repo


def search_properties(
    segmento: str | None = None,
    tipo: str | None = None,
    bairro: str | None = None,
    preco_min: float | None = None,
    preco_max: float | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    props = repo.list_properties(
        segmento=segmento,
        tipo=tipo,
        bairro=bairro,
        preco_min=preco_min,
        preco_max=preco_max,
        limit=limit,
    )
    return [repo.property_to_dict(p) for p in props]


def summarize_properties(props: list[dict[str, Any]]) -> str:
    if not props:
        return "Nenhum imóvel encontrado com esses filtros."
    lines = []
    for p in props:
        lines.append(
            f"- {p['id']} | {p['titulo']} | {p['bairro']} | "
            f"R$ {p['preco']:,.0f} | {p['area_m2']} m² | segmento={p['segmento']}"
        )
    return "\n".join(lines)
