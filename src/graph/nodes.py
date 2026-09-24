"""Nós dos agentes LangGraph."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage

from src.graph.state import AgentState
from src.llm import invoke_text
from src.rag.retriever import format_context, retrieve
from src.tools import lead_crm, mortgage_simulator, property_search, scheduling


INTENTS = [
    "busca",
    "avaliacao",
    "juridico",
    "financiamento",
    "vendas",
    "crm",
    "agendamento",
    "geral",
]


def _merge_output(state: AgentState, key: str, text: str) -> dict[str, Any]:
    outputs = dict(state.get("agent_outputs") or {})
    outputs[key] = text
    return {"agent_outputs": outputs}


def _heuristic_intent(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ("agendar", "visita", "calendário", "consulta")):
        return "agendamento"
    if any(w in q for w in ("financi", "parcela", "entrada")):
        return "financiamento"
    if any(w in q for w in ("contrato", "itbi", "juríd", "jurid", "document")):
        return "juridico"
    if any(w in q for w in ("avali", "quanto vale", "preço justo", "preco justo")):
        return "avaliacao"
    if any(w in q for w in ("lead", "origem", "crm", "contato")):
        return "crm"
    if any(w in q for w in ("buscar", "apto", "apartamento", "casa", "galpão", "galpao", "escritório", "escritorio", "imóvel", "imovel", "comprar")):
        return "busca"
    return "vendas"


def supervisor_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    # Classificação local: uma chamada extra ao Llama 8B deixava o chat parado.
    intent = _heuristic_intent(query)

    route_map = {
        "busca": ["busca", "crm", "sintese"],
        "avaliacao": ["avaliacao", "sintese"],
        "juridico": ["juridico", "sintese"],
        "financiamento": ["financiamento", "sintese"],
        "vendas": ["vendas", "sintese"],
        "crm": ["crm", "sintese"],
        "agendamento": ["agendamento", "sintese"],
        "geral": ["vendas", "sintese"],
    }
    return {"intent": intent, "route": route_map[intent]}


def _extract_filters(query: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    q = query.lower()
    if "empresarial" in q or "comercial" in q or "galpão" in q or "escritório" in q or "escritorio" in q:
        filters["segmento"] = "empresarial"
    elif "residencial" in q or "apartamento" in q or "casa" in q or "cobertura" in q:
        filters["segmento"] = "residencial"

    for tipo in ("apartamento", "casa", "cobertura", "kitnet", "escritorio", "escritório", "loja", "galpao", "galpão", "sala_comercial"):
        if tipo in q or tipo.replace("ó", "o").replace("ã", "a") in q:
            normalized = (
                tipo.replace("ó", "o").replace("ã", "a").replace("escritorio", "escritorio")
            )
            if normalized == "galpao":
                filters["tipo"] = "galpao"
            elif "escritor" in normalized:
                filters["tipo"] = "escritorio"
            elif "sala" in normalized:
                filters["tipo"] = "sala_comercial"
            else:
                filters["tipo"] = normalized
            break

    m = re.search(r"até\s*r?\$?\s*([\d\.]+)", q)
    if m:
        filters["preco_max"] = float(m.group(1).replace(".", ""))
    m_min = re.search(r"(?:a\s*partir\s*de|desde|mínimo)\s*r?\$?\s*([\d\.]+)", q)
    if m_min:
        filters["preco_min"] = float(m_min.group(1).replace(".", ""))

    m_q = re.search(r"(\d+)\s*quartos?", q)
    if m_q:
        filters["quartos_min"] = int(m_q.group(1))
    m_q2 = re.search(r"pelo\s*menos\s*(\d+)\s*quartos?", q)
    if m_q2:
        filters["quartos_min"] = int(m_q2.group(1))

    m2 = re.search(r"em\s+([a-záéíóúãõç\s]+?)(?:\s+até|\s+com|\s+de\s+\d|,|\.|$)", q)
    if m2:
        bairro = m2.group(1).strip().title()
        if len(bairro) > 2 and bairro.lower() not in ("sao paulo", "são paulo"):
            filters["bairro"] = bairro
    return filters


def _structured_from_filters(filters: dict[str, Any]) -> dict[str, Any]:
    structured: dict[str, Any] = {"somente_imoveis": True}
    if filters.get("segmento"):
        structured["segmento"] = filters["segmento"]
    if filters.get("tipo"):
        structured["property_tipo"] = filters["tipo"]
    if filters.get("bairro"):
        structured["bairro"] = filters["bairro"]
    if filters.get("preco_min") is not None:
        structured["preco_min"] = filters["preco_min"]
    if filters.get("preco_max") is not None:
        structured["preco_max"] = filters["preco_max"]
    if filters.get("quartos_min") is not None:
        structured["quartos_min"] = filters["quartos_min"]
    if filters.get("quartos_max") is not None:
        structured["quartos_max"] = filters["quartos_max"]
    return structured


def busca_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    filters = _extract_filters(query)
    props = property_search.search_properties(
        segmento=filters.get("segmento"),
        tipo=filters.get("tipo"),
        bairro=filters.get("bairro"),
        preco_min=filters.get("preco_min"),
        preco_max=filters.get("preco_max"),
        quartos_min=filters.get("quartos_min"),
        quartos_max=filters.get("quartos_max"),
        limit=6,
    )
    structured = _structured_from_filters(filters)
    docs = retrieve(query, k=4, structured=structured)
    context = format_context(docs)
    listing = property_search.summarize_properties(props)

    lead_id = state.get("lead_id")
    if lead_id:
        lead_crm.register_search(lead_id, filters)

    system = (
        "Você é o Agente de Busca imobiliária. Com base na lista e no contexto RAG, "
        "recomende imóveis em PT-BR de forma objetiva."
    )
    user = f"Pergunta: {query}\n\nImóveis:\n{listing}\n\nContexto RAG:\n{context}"
    try:
        text = invoke_text(system, user, model=state.get("model_name"))
    except Exception as exc:  # noqa: BLE001
        text = f"Resultados da busca:\n{listing}\n\n(LLM indisponível: {exc})"

    out = _merge_output(state, "busca", text)
    out["properties_found"] = props
    out["retrieved_docs"] = docs
    return out


def avaliacao_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    docs = retrieve(query, k=4)
    context = format_context(docs)
    system = (
        "Você é o Agente de Avaliação. Estime faixa de valor com base no contexto "
        "(dados fictícios). Deixe claro que é estimativa acadêmica."
    )
    try:
        text = invoke_text(system, f"Pergunta: {query}\n\nContexto:\n{context}", model=state.get("model_name"))
    except Exception as exc:  # noqa: BLE001
        text = f"Avaliação preliminar com base no RAG:\n{context}\n\n(LLM: {exc})"
    out = _merge_output(state, "avaliacao", text)
    out["retrieved_docs"] = docs
    return out


def juridico_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    docs = retrieve(query, k=4, filtro={"tipo": "juridico"})
    if not docs:
        docs = retrieve(query, k=4)
    context = format_context(docs)
    system = (
        "Você é o Agente Jurídico imobiliário (conteúdo fictício/educacional). "
        "Explique de forma clara e avise que não substitui advogado."
    )
    try:
        text = invoke_text(system, f"Pergunta: {query}\n\nContexto:\n{context}", model=state.get("model_name"))
    except Exception as exc:  # noqa: BLE001
        text = f"Orientação jurídica seed:\n{context}\n\n(LLM: {exc})"
    out = _merge_output(state, "juridico", text)
    out["retrieved_docs"] = docs
    return out


def financiamento_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    valor = 800_000.0
    # tenta pegar valor mais plausível
    nums = re.findall(r"(\d[\d\.]{4,})", query.replace(",", "."))
    if nums:
        try:
            valor = float(nums[0].replace(".", "")) if nums[0].count(".") <= 1 else float(nums[0].replace(".", ""))
            if valor < 10000 and len(nums) > 0:
                valor = float(re.sub(r"[^\d]", "", nums[0]))
        except ValueError:
            pass
    # fallback simples: se mencionar milhão
    if "milhão" in query.lower() or "milhao" in query.lower():
        valor = 1_000_000.0

    entrada = None
    prazo = 240
    m_ent = re.search(r"entrada\s*(?:de\s*)?(\d{1,2})\s*%", query.lower())
    if m_ent:
        entrada = float(m_ent.group(1))
    m_prazo = re.search(r"(\d{2,3})\s*meses", query.lower())
    if m_prazo:
        prazo = int(m_prazo.group(1))

    # se houver imóvel selecionado
    props = state.get("properties_found") or []
    if props:
        valor = float(props[0]["preco"])

    sim = mortgage_simulator.simulate_mortgage(valor, entrada_percent=entrada, prazo_meses=prazo)
    sim_txt = mortgage_simulator.format_simulation(sim)
    docs = retrieve("financiamento imobiliário taxa entrada", k=2)
    context = format_context(docs)
    system = "Você é o Agente de Financiamento. Explique a simulação em PT-BR."
    try:
        text = invoke_text(
            system,
            f"Pergunta: {query}\n\nSimulação:\n{sim_txt}\n\nRAG:\n{context}",
            model=state.get("model_name"),
        )
    except Exception as exc:  # noqa: BLE001
        text = f"{sim_txt}\n\n(LLM: {exc})"
    out = _merge_output(state, "financiamento", text)
    out["retrieved_docs"] = docs
    return out


def vendas_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    lead_id = state.get("lead_id")
    profile_txt = ""
    if lead_id:
        profile_txt = lead_crm.format_lead_profile(lead_crm.get_lead_profile(lead_id))
    docs = retrieve(query, k=3)
    context = format_context(docs)
    system = (
        "Você é o Consultor de Vendas. Esclareça dúvidas gerais, conduza a conversa "
        "comercial com empatia e sugira próximos passos (busca, visita, financiamento)."
    )
    user = f"Pergunta: {query}\n\nLead:\n{profile_txt}\n\nRAG:\n{context}"
    try:
        text = invoke_text(system, user, model=state.get("model_name"))
    except Exception as exc:  # noqa: BLE001
        text = (
            "Olá! Sou o consultor de vendas. Posso ajudar com dúvidas gerais, "
            f"busca de imóveis e agendamento de visitas.\nLead:\n{profile_txt}\n(LLM: {exc})"
        )
    if lead_id:
        from src.db import repository as repo

        repo.add_interaction(lead_id, "chat", text, agente="consultor_vendas")
    out = _merge_output(state, "vendas", text)
    out["retrieved_docs"] = docs
    return out


def crm_node(state: AgentState) -> dict[str, Any]:
    lead_id = state.get("lead_id")
    profile = lead_crm.get_lead_profile(lead_id) if lead_id else None
    text = lead_crm.format_lead_profile(profile)
    if not profile:
        text = (
            "Nenhum lead vinculado. Selecione um lead na sidebar do chat para "
            "catalogar origem (Google, QuintoAndar, ZAP), contatos e preferências."
        )
    return _merge_output(state, "crm", text)


def agendamento_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    lead_id = state.get("lead_id")
    if not lead_id:
        text = "Para agendar, selecione um lead na sidebar."
        return _merge_output(state, "agendamento", text)

    profile = lead_crm.get_lead_profile(lead_id)
    seller_id = (profile or {}).get("seller_id") or "SEL-001"
    # data: tenta ISO ou amanhã 10h
    from datetime import datetime, timedelta

    inicio = (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    m = re.search(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})", query)
    if m:
        inicio = datetime.fromisoformat(m.group(1).replace(" ", "T"))

    tipo = "consulta" if "consulta" in query.lower() else "visita"
    prop_id = None
    props = state.get("properties_found") or []
    if props:
        prop_id = props[0]["id"]
    m_prop = re.search(r"(RES|COM)-\d{3}", query.upper())
    if m_prop:
        prop_id = m_prop.group(0)

    result = scheduling.schedule_visit_or_consult(
        lead_id=lead_id,
        seller_id=seller_id,
        inicio_iso=inicio.isoformat(),
        tipo=tipo,
        property_id=prop_id,
        send_email=True,
    )
    text = (
        f"Agendamento criado: {result['appointment_id']}\n"
        f"{result['titulo']}\n"
        f"Início: {result['inicio']}\n"
        f"E-mail/ICS: {json.dumps(result.get('email'), ensure_ascii=False)}"
    )
    out = _merge_output(state, "agendamento", text)
    out["schedule_draft"] = result
    return out


def sintese_node(state: AgentState) -> dict[str, Any]:
    outputs = state.get("agent_outputs") or {}
    intent = state.get("intent") or ""
    final = outputs.get(intent) or ""
    if not final and outputs:
        final = next(iter(outputs.values()))
    if not final:
        final = "Não foi possível gerar resposta."
    return {
        "final_response": final,
        "messages": [AIMessage(content=final)],
    }
