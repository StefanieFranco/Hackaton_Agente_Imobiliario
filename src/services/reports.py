"""Relatórios gerenciais do funil de leads."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.db import repository as repo
from src.llm import invoke_text


def period_bounds(periodo: str, reference: datetime | None = None) -> tuple[datetime, datetime]:
    now = reference or datetime.utcnow()
    if periodo == "dia":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif periodo == "semana":
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    else:  # mes
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    return start, end


def build_report(
    periodo: str = "mes",
    seller_id: str | None = None,
    with_narrative: bool = True,
    model: str | None = None,
) -> dict[str, Any]:
    start, end = period_bounds(periodo)
    # Para demo acadêmica: funil considera created_at no período OU todos se quiser visão geral.
    # Usamos visão geral do funil atual + agendamentos no período.
    funnel = repo.funnel_counts(seller_id=seller_id)
    appts = repo.appointment_stats(seller_id=seller_id, start=start, end=end)
    bairros = repo.top_bairros_buscados()
    origens = repo.origem_distribution()

    gerados = funnel.get("total", 0)
    interessados = funnel.get("interessado", 0)
    negociacao = funnel.get("negociacao", 0)
    comprados = funnel.get("comprado", 0)

    def rate(a: int, b: int) -> float:
        return round((a / b) * 100, 1) if b else 0.0

    metrics = {
        "periodo": periodo,
        "inicio": start.isoformat(),
        "fim": end.isoformat(),
        "seller_id": seller_id,
        "leads_gerados": gerados,
        "leads_interessados": interessados,
        "leads_negociacao": negociacao,
        "leads_comprados_pos_venda": comprados,
        "leads_novos": funnel.get("novo", 0),
        "leads_finalizados": funnel.get("finalizado", 0),
        "conv_interessado_pct": rate(interessados, gerados),
        "conv_negociacao_pct": rate(negociacao, interessados or gerados),
        "conv_compra_pct": rate(comprados, negociacao or gerados),
        "agendamentos": appts,
        "top_bairros": bairros,
        "origens": origens,
    }

    narrative = ""
    if with_narrative:
        system = (
            "Você é analista imobiliário. Explique os números em português claro, "
            "com 2–4 parágrafos, destacando insights úteis para gestores. "
            "Não invente métricas além das fornecidas."
        )
        user = f"Métricas do relatório:\n{metrics}"
        try:
            narrative = invoke_text(system, user, model=model)
        except Exception as exc:  # noqa: BLE001
            narrative = (
                f"No período ({periodo}) há {gerados} leads no funil, "
                f"{interessados} interessados, {negociacao} em negociação e "
                f"{comprados} comprados (pós-venda). "
                f"Principais origens: {origens}. Bairros mais buscados: {bairros}. "
                f"(Narrativa fallback sem LLM: {exc})"
            )
    metrics["narrative"] = narrative
    return metrics
