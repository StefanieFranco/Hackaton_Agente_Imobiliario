"""Simulador de financiamento (regras seedadas — sistema Price)."""

from __future__ import annotations

import json
from typing import Any

from src.config import SEEDS_DIR


def load_rules() -> dict[str, Any]:
    path = SEEDS_DIR / "finance_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


def simulate_mortgage(
    valor_imovel: float,
    entrada_percent: float | None = None,
    prazo_meses: int | None = None,
) -> dict[str, Any]:
    rules = load_rules()
    entrada_percent = entrada_percent if entrada_percent is not None else rules["entrada_minima_percent"]
    prazo_meses = prazo_meses if prazo_meses is not None else 240

    if entrada_percent < rules["entrada_minima_percent"]:
        return {
            "ok": False,
            "erro": f"Entrada mínima fictícia: {rules['entrada_minima_percent']}%",
        }
    if prazo_meses > rules["prazo_max_meses"]:
        return {
            "ok": False,
            "erro": f"Prazo máximo fictício: {rules['prazo_max_meses']} meses",
        }

    entrada = valor_imovel * (entrada_percent / 100.0)
    principal = valor_imovel - entrada
    i = (rules["taxa_anual_percent"] / 100.0) / 12.0
    n = prazo_meses
    if i == 0:
        pmt = principal / n
    else:
        pmt = principal * (i * (1 + i) ** n) / ((1 + i) ** n - 1)

    return {
        "ok": True,
        "valor_imovel": valor_imovel,
        "entrada_percent": entrada_percent,
        "entrada_valor": round(entrada, 2),
        "financiado": round(principal, 2),
        "prazo_meses": prazo_meses,
        "taxa_anual_percent": rules["taxa_anual_percent"],
        "parcela_mensal": round(pmt, 2),
        "sistema": rules["sistema"],
        "observacao": rules["observacao"],
    }


def format_simulation(sim: dict[str, Any]) -> str:
    if not sim.get("ok"):
        return f"Simulação inválida: {sim.get('erro')}"
    return (
        f"Valor do imóvel: R$ {sim['valor_imovel']:,.2f}\n"
        f"Entrada ({sim['entrada_percent']}%): R$ {sim['entrada_valor']:,.2f}\n"
        f"Financiado: R$ {sim['financiado']:,.2f}\n"
        f"Prazo: {sim['prazo_meses']} meses | Taxa a.a.: {sim['taxa_anual_percent']}%\n"
        f"Parcela estimada ({sim['sistema']}): R$ {sim['parcela_mensal']:,.2f}\n"
        f"Obs.: {sim['observacao']}"
    )
