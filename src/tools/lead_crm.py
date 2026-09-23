"""Ferramentas de CRM de leads (origem, preferências, status)."""

from __future__ import annotations

import json
from typing import Any

from src.db import repository as repo

ORIGENS_VALIDAS = {"google", "quinto_andar", "zap", "indicacao", "direto"}


def get_lead_profile(lead_id: str) -> dict[str, Any] | None:
    lead = repo.get_lead(lead_id)
    if not lead:
        return None
    return {
        "id": lead.id,
        "nome": lead.nome,
        "email": lead.email,
        "telefone": lead.telefone,
        "origem": lead.origem,
        "status": lead.status,
        "chat_finalizado": lead.chat_finalizado,
        "preferencias_resumo": lead.preferencias_resumo,
        "ultimas_buscas": json.loads(lead.ultimas_buscas or "[]"),
        "seller_id": lead.seller_id,
    }


def format_lead_profile(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "Lead não encontrado."
    buscas = profile.get("ultimas_buscas") or []
    buscas_txt = "\n".join(
        f"  - {b.get('bairro')} | {b.get('segmento')} | max R$ {b.get('preco_max', 'n/d')}"
        for b in buscas[:5]
    ) or "  (sem buscas)"
    return (
        f"Lead {profile['id']} — {profile['nome']}\n"
        f"Contato: {profile['email']} | {profile['telefone']}\n"
        f"Origem: {profile['origem']} | Status: {profile['status']}\n"
        f"Chat finalizado: {profile['chat_finalizado']}\n"
        f"Preferências: {profile['preferencias_resumo']}\n"
        f"Últimas buscas:\n{buscas_txt}"
    )


def register_search(lead_id: str, busca: dict[str, Any]) -> None:
    repo.append_search_preference(lead_id, busca)


def set_chat_finalizado(lead_id: str, finalizado: bool = True) -> None:
    status = "finalizado" if finalizado else None
    repo.update_lead(lead_id, chat_finalizado=finalizado, status=status, touch_interaction=True)
