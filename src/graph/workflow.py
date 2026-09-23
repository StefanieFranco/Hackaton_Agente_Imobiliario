"""Compilação do StateGraph multiagente."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from src.graph import nodes
from src.graph.state import AgentState


def _route_after_supervisor(state: AgentState) -> str:
    route = state.get("route") or ["vendas", "sintese"]
    return route[0]


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("supervisor", nodes.supervisor_node)
    g.add_node("busca", nodes.busca_node)
    g.add_node("avaliacao", nodes.avaliacao_node)
    g.add_node("juridico", nodes.juridico_node)
    g.add_node("financiamento", nodes.financiamento_node)
    g.add_node("vendas", nodes.vendas_node)
    g.add_node("crm", nodes.crm_node)
    g.add_node("agendamento", nodes.agendamento_node)
    g.add_node("sintese", nodes.sintese_node)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "busca": "busca",
            "avaliacao": "avaliacao",
            "juridico": "juridico",
            "financiamento": "financiamento",
            "vendas": "vendas",
            "crm": "crm",
            "agendamento": "agendamento",
            "sintese": "sintese",
        },
    )

    # após especialista: CRM opcional na busca, senão síntese
    def after_busca(state: AgentState) -> Literal["crm", "sintese"]:
        route = state.get("route") or []
        return "crm" if "crm" in route else "sintese"

    g.add_conditional_edges("busca", after_busca, {"crm": "crm", "sintese": "sintese"})
    g.add_edge("avaliacao", "sintese")
    g.add_edge("juridico", "sintese")
    g.add_edge("financiamento", "sintese")
    g.add_edge("vendas", "sintese")
    g.add_edge("crm", "sintese")
    g.add_edge("agendamento", "sintese")
    g.add_edge("sintese", END)

    return g.compile()


_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = build_graph()
    return _APP


def run_agent(
    user_query: str,
    lead_id: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    app = get_app()
    result = app.invoke(
        {
            "user_query": user_query,
            "lead_id": lead_id,
            "model_name": model_name,
            "messages": [],
            "agent_outputs": {},
            "retrieved_docs": [],
            "properties_found": [],
            "route": [],
        }
    )
    return result
