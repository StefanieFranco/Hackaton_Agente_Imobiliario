"""Nós dos agentes LangGraph."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage

from src.graph.state import AgentState
from src.llm import invoke_llm
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


def _merge_output(state: AgentState, key: str, text: str, truncated: bool = False) -> dict[str, Any]:
    outputs = dict(state.get("agent_outputs") or {})
    outputs[key] = text
    return {
        "agent_outputs": outputs,
        "response_truncated": bool(truncated) or bool(state.get("response_truncated")),
    }


def _history_block(state: AgentState) -> str:
    lines = []
    for item in (state.get("chat_history") or [])[-3:]:
        who = "Cliente" if item.get("role") == "user" else "Atendente"
        content = (item.get("content") or "").strip()
        if content:
            lines.append(f"{who}: {content}")
    if not lines:
        return ""
    return "Mensagens anteriores:\n" + "\n".join(lines)


def _style(state: AgentState) -> str:
    return (
        " Responda em português, em no máximo 5 linhas. "
        "Seja objetivo: responda só o que foi perguntado. "
        "Não cumprimente, não diga o nome da pessoa e não repita a pergunta. "
        "Não ofereça outros imóveis, a menos que a pessoa peça uma busca."
    )


def _objective(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(
        r"^(?:ol[áa]|oi|bom dia|boa tarde|boa noite)[!,.]?\s+[^!\n.]{1,40}[!.]\s*",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    )
    return cleaned.strip() or (text or "").strip()


def _speak(state: AgentState, system: str, user: str) -> tuple[str, bool]:
    history = _history_block(state)
    if history:
        user = f"{history}\n\n{user}"
    return invoke_llm(system + _style(state), user, model=state.get("model_name"))


def _looks_cut(text: str) -> bool:
    cleaned = (text or "").rstrip()
    if len(cleaned) < 80:
        return False
    if cleaned[-1] in ".!?…":
        return False
    if cleaned.endswith(('."', ".'", '!"', '?"', "…”")):
        return False
    return True


def _starts_contract(query: str) -> bool:
    q = query.lower()
    return any(
        w in q
        for w in (
            "iniciar a contrat",
            "inicia a contrat",
            "começar a contrat",
            "comecar a contrat",
            "quero contratar",
        )
    )


def _contract_payment_method(query: str) -> str | None:
    q = query.lower()
    if "na contratação" not in q and "na contratacao" not in q:
        return None
    if "vista" in q:
        return "à vista"
    if "financi" in q:
        return "financiamento"
    if "cartão" in q or "cartao" in q or "crédito" in q or "credito" in q:
        return "cartão de crédito"
    return None


def _heuristic_intent(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ("agendar", "visita", "calendário", "consulta")):
        return "agendamento"
    if _starts_contract(query) or _contract_payment_method(query):
        return "juridico"
    if any(w in q for w in ("pagamento", "pagamentos", "pagar", "a vista", "à vista", "financi", "parcela", "entrada")):
        return "financiamento"
    if any(w in q for w in ("contrat", "itbi", "juríd", "jurid", "document")):
        return "juridico"
    if any(w in q for w in ("avali", "quanto vale", "preço justo", "preco justo")):
        return "avaliacao"
    if any(w in q for w in ("lead", "origem", "crm", "contato")):
        return "crm"
    if any(w in q for w in ("abaixo de", "até ", "preço", "preco", "preços", "precos")) and any(
        w in q for w in ("imóv", "imov", "residenc", "comercial", "apartamento", "casa", "buscar", "busca")
    ):
        return "busca"
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


def _br_number(raw: str) -> float:
    if "," in raw:
        return float(raw.replace(".", "").replace(",", "."))
    if raw.count(".") > 1 or re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        return float(raw.replace(".", ""))
    return float(raw)


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

    m = re.search(r"(?:até|abaixo\s+de|menos\s+de)\s*r?\$?\s*([\d\.]+(?:,\d+)?)", q)
    if m:
        filters["preco_max"] = _br_number(m.group(1))
    m_min = re.search(r"(?:a\s*partir\s*de|desde|mínimo|acima\s+de)\s*r?\$?\s*([\d\.]+(?:,\d+)?)", q)
    if m_min:
        filters["preco_min"] = _br_number(m_min.group(1))

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


def _catalog_reply(props: list[dict[str, Any]], filters: dict[str, Any]) -> str:
    if not props and not filters:
        return ""
    label = "comerciais" if filters.get("segmento") == "empresarial" else "residenciais"
    if filters.get("segmento") is None:
        label = ""
    local = f" em {filters['bairro']}" if filters.get("bairro") else ""
    faixa = ""
    if filters.get("preco_max") is not None:
        faixa = f" até R$ {filters['preco_max']:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    elif filters.get("preco_min") is not None:
        faixa = f" a partir de R$ {filters['preco_min']:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    titulo = " ".join(part for part in (f"imóveis {label}".strip(), local.strip(), faixa.strip()) if part)
    if not props:
        return f"Não encontrei {titulo} no catálogo. Posso ampliar a busca sem o limite de valor ou de bairro."
    lines = [f"Encontrei estes {titulo}:", ""]
    for item in props[:5]:
        quartos = item.get("quartos")
        quartos_txt = ""
        if quartos:
            quartos_txt = f" — {quartos} quarto" if int(quartos) == 1 else f" — {quartos} quartos"
        preco = f"{float(item['preco']):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lines.append(f"- {item['id']} — {item['titulo']} — {item['bairro']} — R$ {preco}{quartos_txt}")
    return "\n".join(lines)


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

    text = _catalog_reply(props, filters)
    truncated = False
    if not text:
        system = (
            "Você é o Agente de Busca imobiliária. Liste apenas os imóveis do contexto, "
            "um por linha, com código, bairro, área e preço."
        )
        user = f"Pergunta: {query}\n\nImóveis:\n{listing}\n\nContexto RAG:\n{context}"
        try:
            text, truncated = _speak(state, system, user)
        except Exception as exc:  # noqa: BLE001
            text = f"Resultados da busca:\n{listing}\n\n(LLM indisponível: {exc})"

    out = _merge_output(state, "busca", text, truncated)
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
    truncated = False
    try:
        text, truncated = _speak(state, system, f"Pergunta: {query}\n\nContexto:\n{context}")
    except Exception as exc:  # noqa: BLE001
        text = f"Avaliação preliminar com base no RAG:\n{context}\n\n(LLM: {exc})"
    out = _merge_output(state, "avaliacao", text, truncated)
    out["retrieved_docs"] = docs
    return out


def _mentioned_property(*texts: str) -> str | None:
    found = re.search(r"(RES|COM)-\d{3}", " ".join(texts).upper())
    return found.group(0) if found else None


def _lead_email(state: AgentState) -> str | None:
    lead_id = state.get("lead_id")
    if not lead_id:
        return None
    from src.db import repository as repo

    lead = repo.get_lead(lead_id)
    if not lead or not repo.lead_is_identified(lead.email):
        return None
    return lead.email


def _contract_message(state: AgentState, query: str) -> str | None:
    history = " ".join((item.get("content") or "") for item in (state.get("chat_history") or []))
    code = _mentioned_property(query, history)
    alvo = f" do imóvel {code}" if code else ""
    method = _contract_payment_method(query)
    email = _lead_email(state)
    destino = f" para {email}" if email else ""
    if method:
        return (
            f"Pagamento {method} registrado para a contratação{alvo}.\n\n"
            f"O contrato será enviado por e-mail{destino}."
        )
    if _starts_contract(query):
        return (
            f"Para seguir com a contratação{alvo}, qual método de pagamento você prefere?\n\n"
            f"O contrato será enviado por e-mail{destino}."
        )
    return None


def juridico_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    contract = _contract_message(state, query)
    if contract:
        out = _merge_output(state, "juridico", contract, False)
        out["retrieved_docs"] = []
        return out
    docs = retrieve(query, k=4, filtro={"tipo": "juridico"})
    if not docs:
        docs = retrieve(query, k=4)
    context = format_context(docs)
    system = (
        "Você é o Agente Jurídico imobiliário (conteúdo fictício/educacional). "
        "Explique de forma clara e avise que não substitui advogado."
    )
    truncated = False
    try:
        text, truncated = _speak(state, system, f"Pergunta: {query}\n\nContexto:\n{context}")
    except Exception as exc:  # noqa: BLE001
        text = f"Orientação jurídica seed:\n{context}\n\n(LLM: {exc})"
    out = _merge_output(state, "juridico", text, truncated)
    out["retrieved_docs"] = docs
    return out


def _brl(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _payment_reply(code: str | None, valor: float, sims: list[dict[str, Any]]) -> str:
    alvo = f"o imóvel {code}" if code else "este imóvel"
    lines = [f"Os meios de pagamento para {alvo} incluem:", ""]
    lines.append(
        "Pagamento à vista: é possível pagar o valor integral do imóvel em uma única parcela, "
        f"de {_brl(valor)}."
    )
    lines.append("")
    ok = [item for item in sims if item.get("ok")]
    if ok:
        base = ok[0]
        taxa = str(base["taxa_anual_percent"]).replace(".", ",")
        parcelas = "; ".join(
            f"{int(item['prazo_meses'])} meses de {_brl(float(item['parcela_mensal']))}" for item in ok
        )
        lines.append(
            "Financiamento: é possível financiar o imóvel com juros e parcelas mensais. "
            f"Entrada de {float(base['entrada_percent']):.0f}% ({_brl(float(base['entrada_valor']))}), "
            f"saldo de {_brl(float(base['financiado']))}, "
            f"taxa de {taxa}% ao ano no sistema {base['sistema']}. "
            f"Parcelas estimadas: {parcelas}."
        )
    else:
        lines.append(f"Financiamento: {sims[0].get('erro') if sims else 'simulação indisponível'}.")
    lines.append("")
    lines.append(
        "Cartão de crédito: é possível pagar o valor do imóvel com cartão de crédito, "
        f"no total de {_brl(valor)}, conforme o limite e a análise da operadora."
    )
    lines.append("")
    lines.append("Outras opções: é possível discutir outras opções de pagamento com o vendedor ou o banco.")
    lines.append("")
    lines.append("Quer iniciar a contratação ou ver imóveis parecidos?")
    return "\n".join(lines)


def financiamento_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    valor = 800_000.0
    nums = re.findall(r"(\d[\d\.]{4,})", query.replace(",", "."))
    if nums:
        try:
            valor = float(nums[0].replace(".", "")) if nums[0].count(".") <= 1 else float(nums[0].replace(".", ""))
            if valor < 10000 and len(nums) > 0:
                valor = float(re.sub(r"[^\d]", "", nums[0]))
        except ValueError:
            pass
    if "milhão" in query.lower() or "milhao" in query.lower():
        valor = 1_000_000.0

    entrada = None
    m_ent = re.search(r"entrada\s*(?:de\s*)?(\d{1,2})\s*%", query.lower())
    if m_ent:
        entrada = float(m_ent.group(1))

    mentioned = query
    for item in state.get("chat_history") or []:
        mentioned += " " + (item.get("content") or "")
    found = re.search(r"(RES|COM)-\d{3}", mentioned.upper())
    code = found.group(0) if found else None
    if code:
        from src.db import repository as repo

        chosen = repo.get_property(code)
        if chosen:
            valor = float(chosen.preco)

    rules = mortgage_simulator.load_rules()
    prazos = [int(item) for item in rules.get("prazo_opcoes") or [120, 180, 240, 360]]
    sims = [
        mortgage_simulator.simulate_mortgage(valor, entrada_percent=entrada, prazo_meses=prazo)
        for prazo in prazos
    ]
    text = _payment_reply(code, valor, sims)
    out = _merge_output(state, "financiamento", text, False)
    out["retrieved_docs"] = []
    return out


def _is_thanks(query: str) -> bool:
    cleaned = query.strip()
    return bool(
        re.match(
            r"^(?:muito\s+)?(?:obrigad[oa]|valeu|agradec\w*|perfeito|combinado|ok|beleza|show|tchau|at[eé]\s+logo)[!.\s]*$",
            cleaned,
            flags=re.IGNORECASE,
        )
    )


def _contract_just_sent(state: AgentState) -> bool:
    history = " ".join((item.get("content") or "") for item in (state.get("chat_history") or [])).lower()
    return "contrato será enviado" in history or "contrato sera enviado" in history


def vendas_node(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query") or ""
    if _is_thanks(query) and _contract_just_sent(state):
        text = "Estou à disposição e fico no aguardo."
        out = _merge_output(state, "vendas", text, False)
        out["retrieved_docs"] = []
        return out
    lead_id = state.get("lead_id")
    profile_txt = ""
    if lead_id:
        profile_txt = lead_crm.format_lead_profile(lead_crm.get_lead_profile(lead_id))
    docs = retrieve(query, k=3)
    context = format_context(docs)
    system = (
        "Você é o Consultor de Vendas. Responda só a dúvida desta mensagem, "
        "em poucos fatos. Não liste imóveis se a pessoa não pediu busca."
    )
    user = f"Pergunta: {query}\n\nLead:\n{profile_txt}\n\nRAG:\n{context}"
    truncated = False
    try:
        text, truncated = _speak(state, system, user)
    except Exception as exc:  # noqa: BLE001
        text = (
            "Posso ajudar com dúvidas gerais, busca de imóveis e agendamento de visitas. "
            f"\nLead:\n{profile_txt}\n(LLM: {exc})"
        )
    if lead_id:
        from src.db import repository as repo

        repo.add_interaction(lead_id, "chat", text, agente="consultor_vendas")
    out = _merge_output(state, "vendas", text, truncated)
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
        text = "Para agendar, preciso de um atendimento identificado."
        return _merge_output(state, "agendamento", text)

    from src.db import repository as repo

    profile = lead_crm.get_lead_profile(lead_id)
    sellers = {s.id: s.nome for s in repo.list_sellers()}
    seller_id = (profile or {}).get("seller_id") or (next(iter(sellers), "SEL-001"))
    seller_name = sellers.get(seller_id, "nosso atendente")

    latest = None
    for appt in repo.list_appointments():
        if appt.lead_id != lead_id:
            continue
        if latest is None or appt.inicio > latest.inicio:
            latest = appt
    latest_info = None
    if latest:
        latest_info = {
            "seller_name": sellers.get(latest.seller_id, seller_name),
            "when": latest.inicio.strftime("%d/%m/%Y às %H:%M"),
            "appointment_id": latest.id,
        }

    text, draft, booking = scheduling.advance_visit_plan(
        query,
        state.get("schedule_draft"),
        seller_id=seller_id,
        seller_name=seller_name,
        property_id=None,
        latest=latest_info,
    )
    if booking:
        result = scheduling.schedule_visit_or_consult(
            lead_id=lead_id,
            seller_id=booking["seller_id"],
            inicio_iso=booking["inicio_iso"],
            tipo=booking.get("tipo") or "visita",
            property_id=booking.get("property_id"),
            send_email=True,
        )
        inicio = datetime.fromisoformat(result["inicio"])
        text = scheduling.format_visit_confirmation(
            seller_name=booking["seller_name"],
            property_id=booking.get("property_id"),
            inicio=inicio,
            appointment_id=result["appointment_id"],
        )
    out = _merge_output(state, "agendamento", text)
    out["schedule_draft"] = draft
    return out


def sintese_node(state: AgentState) -> dict[str, Any]:
    outputs = state.get("agent_outputs") or {}
    intent = state.get("intent") or ""
    final = outputs.get(intent) or ""
    if not final and outputs:
        final = next(iter(outputs.values()))
    if not final:
        final = "Não foi possível gerar resposta."
    final = _objective(final)
    return {
        "final_response": final,
        "messages": [AIMessage(content=final)],
    }


def verificar_resposta_node(state: AgentState) -> dict[str, Any]:
    """Se a resposta veio cortada, pede só o trecho que falta."""
    text = (state.get("final_response") or "").strip()
    if not text or "(LLM" in text:
        return {"response_complete": True}
    cut = bool(state.get("response_truncated")) or _looks_cut(text)
    if not cut:
        return {"response_complete": True}

    system = (
        "A resposta abaixo foi interrompida. Escreva somente a continuação, "
        "em português, sem repetir o trecho já dito e sem saudação. "
        "Feche a última frase."
    )
    try:
        extra, _again = invoke_llm(system, text, model=state.get("model_name"))
    except Exception:
        return {"response_complete": False}
    extra = extra.strip()
    if not extra or extra in text:
        return {"response_complete": True, "final_response": text}
    full = f"{text.rstrip()} {extra}"
    return {
        "final_response": full,
        "response_complete": True,
        "response_truncated": False,
        "messages": [AIMessage(content=full)],
    }
