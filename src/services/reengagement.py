"""Job de reengajamento de leads inativos."""

from __future__ import annotations

from typing import Any

from src.config import REENGAGEMENT_DAYS
from src.db import repository as repo
from src.llm import invoke_text
from src.tools.lead_crm import format_lead_profile, get_lead_profile


SYSTEM = (
    "Você é o Consultor de Vendas de uma imobiliária. "
    "Escreva uma mensagem curta e cordial em português (PT-BR) para retomar contato "
    "com um lead inativo. Mencione preferências e incentive a continuar a conversa. "
    "Não invente imóveis específicos que não estejam no contexto."
)


def run_reengagement(days: int | None = None, model: str | None = None) -> list[dict[str, Any]]:
    leads = repo.inactive_leads_for_reengagement(days=days or REENGAGEMENT_DAYS)
    results = []
    for lead in leads:
        profile = get_lead_profile(lead.id)
        user = (
            f"Lead inativo há pelo menos {days or REENGAGEMENT_DAYS} dias.\n"
            f"{format_lead_profile(profile)}\n"
            "Gere a mensagem de reengajamento."
        )
        try:
            message = invoke_text(SYSTEM, user, model=model)
        except Exception as exc:  # noqa: BLE001
            message = (
                f"Olá {lead.nome}, sentimos sua falta! "
                f"Com base em suas preferências ({lead.preferencias_resumo}), "
                f"temos novidades. Podemos retomar? (fallback sem LLM: {exc})"
            )
        repo.add_interaction(lead.id, "reengajamento", message, agente="consultor_vendas")
        results.append({"lead_id": lead.id, "nome": lead.nome, "mensagem": message})
    return results
