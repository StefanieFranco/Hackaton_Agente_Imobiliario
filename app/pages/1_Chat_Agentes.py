"""Chat multiagente com histórico (uma conversa por lead)."""

from __future__ import annotations

import html
import importlib
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OLLAMA_MODEL, REENGAGEMENT_DAYS
import src.db.models as db_models
import src.db.repository as repo

importlib.reload(db_models)
importlib.reload(repo)
from src.db.models import init_db
import src.graph.nodes as graph_nodes
import src.graph.workflow as graph_workflow
import src.tools.scheduling as scheduling_mod

importlib.reload(scheduling_mod)
importlib.reload(graph_nodes)
importlib.reload(graph_workflow)
from src.graph.workflow import run_agent
from src.services.reengagement import run_reengagement

st.set_page_config(page_title="Chat Agentes", layout="wide")
init_db()

ORIGENS = {
    "Site": "site",
    "App": "app",
    "WhatsApp": "whatsapp",
    "QuintoAndar": "quinto_andar",
    "ZAP": "zap",
    "Coelho da Fonseca": "coelho_da_fonseca",
}

st.markdown(
    """
    <style>
    .chat-head { font-size: 1.35rem; font-weight: 700; margin-bottom: 0.2rem; }
    .chat-sub { color: #9ca3af; font-size: 0.85rem; margin-bottom: 0.8rem; }
    .day-sep { text-align: center; color: #9ca3af; font-size: 0.75rem; margin: 0.8rem 0; }
    .bubble { max-width: 78%; padding: 0.65rem 0.9rem; border-radius: 16px;
              margin: 0.35rem 0; line-height: 1.4; white-space: pre-wrap; }
    .bubble.user { margin-left: auto; background: #7c3aed; color: white; border-bottom-right-radius: 4px; }
    .bubble.assistant { margin-right: auto; background: #2a2a2e; color: #f3f4f6; border-bottom-left-radius: 4px; }
    .bubble-time { font-size: 0.7rem; opacity: 0.75; margin-top: 0.25rem; }
    .bubble a { color: #ddd6fe; }
    .st-key-ask_bubble {
        background: #2a2a2e;
        border-radius: 16px;
        border-bottom-left-radius: 4px;
        padding: 0.35rem 0.75rem 0.75rem;
        max-width: 78%;
        margin-right: auto;
    }
    .st-key-ask_bubble .bubble.assistant {
        background: transparent;
        margin: 0;
        padding: 0.45rem 0.1rem 0.35rem;
        max-width: 100%;
    }
    .st-key-ask_bubble button {
        border-radius: 999px;
        border: 1px solid #6d5efc;
        background: #3a3a42;
        color: #f3f4f6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "active_lead_id" not in st.session_state:
    st.session_state.active_lead_id = None
if "last_result" not in st.session_state:
    st.session_state.last_result = {}

active = None
if st.session_state.conversation_id:
    for item in repo.list_conversation_menu():
        if item["conversation_id"] == st.session_state.conversation_id:
            active = item
            break

with st.sidebar:
    st.header("Atendimento")
    if active:
        st.markdown(f"**{active['nome']}**")
        st.caption(active["email"] or "sem e-mail")
    else:
        st.caption("A conversa começa com o pedido de nome e e-mail.")
    model = st.selectbox("Modelo Ollama", [OLLAMA_MODEL, "llama3.2:3b", "llama3.1:8b"], index=0)
    origem_labels = list(ORIGENS)
    origem_codes = list(ORIGENS.values())
    atual = (active or {}).get("origem") or "site"
    if atual not in origem_codes:
        origem_labels = [atual.replace("_", " ").title()] + origem_labels
        origem_codes = [atual] + origem_codes
    origem_idx = origem_codes.index(atual)
    origem_label = st.selectbox("Origem do atendimento", origem_labels, index=origem_idx)
    origem = dict(zip(origem_labels, origem_codes))[origem_label]
    if active and active.get("origem") != origem:
        repo.set_lead_origem(active["lead_id"], origem)
        st.rerun()
    if st.button("Verificar leads inativos"):
        with st.spinner(f"Leads sem interação há {REENGAGEMENT_DAYS}+ dias..."):
            results = run_reengagement(model=model)
        if not results:
            st.success("Nenhum lead elegível.")
        else:
            for r in results:
                st.write(f"**{r['nome']}**")
                st.write(r["mensagem"])

ASK_IDENTITY = (
    "Olá! Antes de responder, preciso registrar o atendimento. "
    "Qual é o seu nome e o seu e-mail?"
)


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_NOT_A_NAME = {
    "oi", "olá", "ola", "ok", "sim", "não", "nao", "bom", "dia", "tarde", "noite", "obrigado", "obrigada",
}


def _extract_email(text: str) -> str | None:
    match = _EMAIL_RE.search(text or "")
    return match.group(0).lower() if match else None


def _looks_like_question(text: str) -> bool:
    low = text.lower()
    if "?" in text or len(text.split()) > 5:
        return True
    return any(
        re.search(rf"\b{re.escape(word)}\b", low)
        for word in (
            "quero", "preciso", "buscar", "busco", "agendar", "visita",
            "imóvel", "imovel", "apartamento", "casa", "comprar", "alugar",
            "financiamento", "pagamento", "contrato",
        )
    )


def _extract_name(text: str) -> str | None:
    email = _extract_email(text)
    nome = text or ""
    if email:
        nome = nome.replace(email, " ")
    nome = re.sub(r"(?i)\b(meu nome é|meu nome e|me chamo|eu sou|sou o|sou a|email|e-mail|nome)\b", " ", nome)
    nome = re.sub(r"[,:;|/]+", " ", nome)
    nome = " ".join(nome.split())
    if len(nome) < 2 or _looks_like_question(nome):
        return None
    words = [word for word in nome.split() if word.lower() not in _NOT_A_NAME]
    if not words:
        return None
    return " ".join(words)


def _identity_so_far(messages: list[dict]) -> tuple[str | None, str | None]:
    nome = None
    email = None
    for item in messages:
        if item.get("role") != "user":
            continue
        content = item.get("content") or ""
        found_email = _extract_email(content)
        found_name = _extract_name(content)
        if found_email:
            email = found_email
        if found_name:
            nome = found_name
    return nome, email


def _continue_identity(conversation_id: str, prompt: str, model_name: str) -> None:
    nome, email = _identity_so_far(repo.list_chat_messages(conversation_id))
    if nome and email:
        saved = repo.identify_conversation(conversation_id, nome, email)
        _open_chat(saved["conversation_id"], saved["lead_id"])
        repo.take_pending_question(saved["conversation_id"])
        repo.add_chat_message(
            saved["conversation_id"],
            "assistant",
            _after_identity_message(saved["nome"], bool(saved.get("returning"))),
        )
        return
    if _extract_email(prompt) is None and _extract_name(prompt) is None:
        repo.set_pending_question(conversation_id, prompt)
    if nome:
        reply = f"{nome}, qual é o seu e-mail?"
    elif email:
        reply = "Recebi o e-mail. Qual é o seu nome?"
    else:
        reply = ASK_IDENTITY
    repo.add_chat_message(conversation_id, "assistant", reply)


def _open_chat(conversation_id: str, lead_id: str) -> None:
    st.session_state.conversation_id = conversation_id
    st.session_state.active_lead_id = lead_id


def _bubble_body(content: str) -> str:
    escaped = html.escape(content or "")
    return re.sub(
        r"(/Calendario\?visita=APT-[A-Z0-9]+)",
        r'<a href="\1">abrir o calendário</a>',
        escaped,
    )


def _after_identity_message(nome: str, returning: bool) -> str:
    if returning:
        return f"Olá, {nome}.\nQuer continuar de onde parou?"
    return (
        f"Olá, {nome}. Obrigado pelo contato.\n"
        "Eu sou o Imobi, assistente imobiliário.\n"
        "O que você quer fazer: buscar um imóvel residencial ou comercial?"
    )


def _brl(value: float) -> str:
    formatted = f"{value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _parse_budget(text: str) -> tuple[float | None, float | None]:
    low = (text or "").lower().replace("r$", " ")
    above = any(word in low for word in ("acima", "mais de", "a partir"))
    match = re.search(r"(\d+(?:[.\s]\d{3})+|\d+(?:,\d+)?)\s*(milh\w*|mil)?", low)
    if not match:
        return None, None
    raw = match.group(1).replace(" ", "")
    if raw.count(".") > 1 or re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        number = float(raw.replace(".", "").replace(",", "."))
    elif "," in raw:
        number = float(raw.replace(".", "").replace(",", "."))
    else:
        number = float(raw)
    unit = match.group(2) or ""
    if unit.startswith("milh"):
        number *= 1_000_000
    elif unit == "mil":
        number *= 1_000
    if above:
        return number, None
    return None, number


def _clean_place(text: str) -> str:
    place = re.sub(r"(?i)^(em|no|na|nos|nas|no bairro|na cidade|bairro)\s+", "", (text or "").strip())
    return place.split(",")[0].strip(" .")


def _chosen_segment(messages: list[dict]) -> str | None:
    segment = None
    for item in messages:
        if item.get("role") != "user":
            continue
        low = (item.get("content") or "").lower()
        if "comercial" in low:
            segment = "empresarial"
        elif "residencial" in low:
            segment = "residencial"
    return segment


def _chosen_place(messages: list[dict]) -> str | None:
    waiting = False
    place = None
    for item in messages:
        content = item.get("content") or ""
        if item.get("role") == "assistant" and "em qual local" in content.lower():
            waiting = True
            continue
        if waiting and item.get("role") == "user":
            place = _clean_place(content)
            waiting = False
    return place


def _search_offer(messages: list[dict], budget_text: str) -> str:
    from src.tools.property_search import search_properties

    segment = _chosen_segment(messages)
    place = _chosen_place(messages)
    preco_min, preco_max = _parse_budget(budget_text)
    if preco_min is None and preco_max is None:
        return "Não entendi a faixa de valor. Pode dizer, por exemplo, até 500 mil ou até 1 milhão?"
    label = "comercial" if segment == "empresarial" else "residencial"
    props = search_properties(
        segmento=segment,
        bairro=place or None,
        preco_min=preco_min,
        preco_max=preco_max,
        limit=5,
    )
    faixa = f"a partir de {_brl(preco_min)}" if preco_min else f"até {_brl(preco_max or 0)}"
    local = f" em {place}" if place else ""
    if not props:
        return (
            f"Não encontrei imóveis {label}{local}, {faixa}. "
            "Quer tentar outro local ou outra faixa de valor?"
        )
    lines = [f"Encontrei estes imóveis {label}{local}, {faixa}:", ""]
    for item in props:
        quartos = item.get("quartos")
        quartos_txt = ""
        if quartos:
            quartos_txt = f" — {quartos} quarto" if int(quartos) == 1 else f" — {quartos} quartos"
        lines.append(
            f"- {item['id']} — {item['titulo']} — {item['bairro']} — {_brl(float(item['preco']))}{quartos_txt}"
        )
    lines.append("")
    lines.append("Quer detalhes de algum ou prefere agendar uma visita?")
    return "\n".join(lines)


def _is_yes(text: str) -> bool:
    low = re.sub(r"[^a-záàãéíóúâêôç\s]", "", (text or "").lower()).strip()
    return low in {"sim", "pode", "pode sim", "quero", "ok", "claro", "isso", "pode buscar", "faz a busca", "pode fazer"}


def _history_budget(messages: list[dict]) -> tuple[float | None, float | None]:
    found_min, found_max = None, None
    for item in messages:
        if item.get("role") != "user":
            continue
        preco_min, preco_max = _parse_budget(item.get("content") or "")
        if preco_min is not None or preco_max is not None:
            found_min, found_max = preco_min, preco_max
    return found_min, found_max


def _execute_saved_search(messages: list[dict], broader: bool = False) -> str:
    from src.tools.property_search import search_properties

    segment = _chosen_segment(messages) or "residencial"
    place = None if broader else _chosen_place(messages)
    preco_min, preco_max = _history_budget(messages)
    if broader and not search_properties(
        segmento=segment, bairro=place, preco_min=preco_min, preco_max=preco_max, limit=1
    ):
        place = None
    props = search_properties(
        segmento=segment,
        bairro=place or None,
        preco_min=preco_min,
        preco_max=preco_max,
        limit=5,
    )
    if not props and (place or preco_max is not None or preco_min is not None):
        props = search_properties(segmento=segment, limit=5)
        place = None
        preco_min = preco_max = None
    label = "comerciais" if segment == "empresarial" else "residenciais"
    local = f" em {place}" if place else ""
    if preco_max is not None:
        faixa = f" até {_brl(preco_max)}"
    elif preco_min is not None:
        faixa = f" a partir de {_brl(preco_min)}"
    else:
        faixa = ""
    if not props:
        return f"A busca no catálogo não encontrou imóveis {label}{local}{faixa}."
    lines = [f"Busca feita no catálogo. Estes são imóveis {label}{local}{faixa}:", ""]
    for item in props:
        quartos = item.get("quartos")
        quartos_txt = ""
        if quartos:
            quartos_txt = f" — {quartos} quarto" if int(quartos) == 1 else f" — {quartos} quartos"
        lines.append(
            f"- {item['id']} — {item['titulo']} — {item['bairro']} — {_brl(float(item['preco']))}{quartos_txt}"
        )
    return "\n".join(lines)


def _guided_reply(messages: list[dict], prompt: str) -> str | None:
    last = ""
    for item in reversed(messages):
        if item.get("role") == "assistant":
            last = item.get("content") or ""
            break
    low = last.lower()
    answer = (prompt or "").lower()
    if _is_yes(prompt) and any(
        word in low for word in ("busca mais ampla", "não encontrei", "nao encontrei", "não tenho", "banco de dados", "posso sugerir uma busca")
    ):
        return _execute_saved_search(messages, broader=True)
    if "residencial ou comercial" in low or answer in {"quero começar um assunto novo.", "quero comecar um assunto novo."}:
        if "comercial" in answer:
            return "Perfeito, imóvel comercial. Em qual local você procura? Pode ser o bairro ou a cidade."
        if "residencial" in answer:
            return "Perfeito, imóvel residencial. Em qual local você procura? Pode ser o bairro ou a cidade."
        if answer.strip() in {"quero começar um assunto novo.", "quero comecar um assunto novo."}:
            return "O que você quer fazer: buscar um imóvel residencial ou comercial?"
        if "residencial ou comercial" in low:
            return "Você prefere buscar um imóvel residencial ou comercial?"
    if "em qual local" in low:
        place = _clean_place(prompt)
        if len(place) < 2:
            return "Em qual local você procura? Pode ser o bairro ou a cidade."
        return f"Anotado, {place}. Qual faixa de valor você tem em mente?"
    if "faixa de valor" in low:
        return _search_offer(messages, prompt)
    return None


def _question_options(content: str) -> list[tuple[str, str]]:
    text = content or ""
    low = text.lower()
    if "residencial ou comercial" in low or "prefere buscar um imóvel residencial" in low:
        return [
            ("Residencial", "Quero buscar um imóvel residencial."),
            ("Comercial", "Quero buscar um imóvel comercial."),
        ]
    if "faixa de valor" in low:
        return [
            ("Até 500 mil", "Até 500 mil."),
            ("Até 1 milhão", "Até 1 milhão."),
            ("Até 2 milhões", "Até 2 milhões."),
            ("Acima de 2 milhões", "Acima de 2 milhões."),
        ]
    if "à procura de um imóvel" in low or "a procura de um imóvel" in low:
        return [
            ("Procurar um imóvel", "Estou à procura de um imóvel."),
            ("Agendar uma visita", "Quero agendar uma visita."),
        ]
    if "continuar de onde parou" in low:
        return [
            ("Continuar de onde parei", "Quero continuar de onde parei."),
            ("Começar um assunto novo", "Quero começar um assunto novo."),
        ]
    if "qual método de pagamento" in low or "qual metodo de pagamento" in low:
        return [
            ("À vista", "Quero pagar à vista na contratação."),
            ("Financiamento", "Quero financiar na contratação."),
            ("Cartão de crédito", "Quero pagar com cartão de crédito na contratação."),
        ]
    if "escolha um dia" in low or "escolha um horário" in low:
        options = []
        for line in text.splitlines():
            match = re.match(r"\s*(\d+)\.\s+(.+)", line)
            if match:
                options.append((match.group(2).strip(), match.group(1)))
        return options
    if "iniciar a contratação" in low and "parecidos" in low:
        codes = re.findall(r"(?:RES|COM)-\d{3}", text.upper())
        code = codes[-1] if codes else ""
        alvo = f" do imóvel {code}" if code else ""
        parecido = f" do {code}" if code else ""
        return [
            ("Iniciar contratação", f"Quero iniciar a contratação{alvo}."),
            (
                "Ver imóveis parecidos",
                f"Buscar outros imóveis do mesmo tipo, faixa de preço e localização{parecido}.",
            ),
        ]
    return []


def _recent_turns(conversation_id: str, current: str) -> list[dict[str, str]]:
    messages = repo.list_chat_messages(conversation_id)
    if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == current:
        messages = messages[:-1]
    tail = messages[-3:]
    return [{"role": item["role"], "content": item["content"]} for item in tail]


def _answer_with_agent(question: str, lead_id: str | None, model_name: str, conversation_id: str | None = None) -> str:
    history = _recent_turns(conversation_id, question) if conversation_id else []
    try:
        result = run_agent(
            question,
            lead_id=lead_id,
            model_name=model_name,
            chat_history=history,
            schedule_draft=st.session_state.get("schedule_draft"),
        )
        st.session_state.last_result = result
        st.session_state["schedule_draft"] = result.get("schedule_draft")
        return result.get("final_response") or "Sem resposta."
    except Exception as exc:  # noqa: BLE001
        st.session_state.last_result = {"error": str(exc)}
        return f"Erro ao executar grafo: {exc}"


col_chat, col_hist = st.columns([2.4, 1], gap="large")

with col_hist:
    st.markdown("### Conversas")
    search = st.text_input("Buscar", placeholder="Nome do lead", label_visibility="collapsed")
    if st.button("Novo atendimento", use_container_width=True):
        opened = repo.start_attendance(ASK_IDENTITY, origem=origem)
        st.session_state.conversation_id = opened["conversation_id"]
        st.session_state.active_lead_id = opened["lead_id"]
        st.session_state.last_result = {}
        st.session_state["schedule_draft"] = None
        st.rerun()
    menu = repo.list_conversation_menu(search or None)
    if not menu:
        st.caption("Nenhuma conversa ainda.")
    for item in menu:
        selected = item["conversation_id"] == st.session_state.conversation_id
        label = f"{item['nome']}\n{item['preview']}"
        if st.button(label, key=f"conv_{item['conversation_id']}", use_container_width=True, type="primary" if selected else "secondary"):
            st.session_state.conversation_id = item["conversation_id"]
            st.session_state.active_lead_id = item["lead_id"]
            st.rerun()
        when = item["updated_at"].strftime("%d/%m %H:%M") if item.get("updated_at") else ""
        st.caption(when)

outgoing = (st.session_state.pop("chat_outgoing", None) or "").strip()

with col_chat:
    if not st.session_state.conversation_id:
        st.markdown('<div class="chat-head">Atendimento</div>', unsafe_allow_html=True)
        st.caption("A conversa começa aqui, como no WhatsApp. O agente pede nome e e-mail antes de responder.")
        typed = st.chat_input("Escreva uma mensagem...")
        prompt = outgoing or typed
        if prompt:
            opened = repo.start_attendance("", origem=origem)
            _open_chat(opened["conversation_id"], opened["lead_id"])
            repo.add_chat_message(opened["conversation_id"], "user", prompt)
            _continue_identity(opened["conversation_id"], prompt, model)
            st.rerun()
    else:
        title = active["nome"] if active else "Conversa"
        identified = bool(active and active.get("identified"))
        st.markdown(f'<div class="chat-head">{html.escape(title)}</div>', unsafe_allow_html=True)
        if identified and active:
            st.markdown(f'<div class="chat-sub">{html.escape(active["email"])}</div>', unsafe_allow_html=True)
        elif active:
            partial_name, partial_email = _identity_so_far(repo.list_chat_messages(st.session_state.conversation_id))
            if partial_name and not partial_email:
                waiting = "Aguardando e-mail"
            elif partial_email and not partial_name:
                waiting = "Aguardando nome"
            else:
                waiting = "Aguardando nome e e-mail"
            st.markdown(f'<div class="chat-sub">{waiting}</div>', unsafe_allow_html=True)

        messages = repo.list_chat_messages(st.session_state.conversation_id)
        last_day = None
        last_index = len(messages) - 1
        for index, msg in enumerate(messages):
            day = msg["created_at"].strftime("%d/%m/%Y") if msg["created_at"] else ""
            if day != last_day:
                st.markdown(f'<div class="day-sep">{day}</div>', unsafe_allow_html=True)
                last_day = day
            role = "user" if msg["role"] == "user" else "assistant"
            clock = msg["created_at"].strftime("%H:%M") if msg["created_at"] else ""
            body = _bubble_body(msg["content"] or "")
            options = _question_options(msg["content"] or "") if role == "assistant" and index == last_index else []
            if options:
                with st.container(key="ask_bubble"):
                    st.markdown(
                        f'<div class="bubble assistant">{body}<div class="bubble-time">{clock}</div></div>',
                        unsafe_allow_html=True,
                    )
                    chips = st.columns(len(options))
                    for chip, (label, payload) in zip(chips, options):
                        if chip.button(label, key=f"opt_{index}_{payload}", width="stretch"):
                            st.session_state["chat_outgoing"] = payload
                            st.rerun()
            else:
                st.markdown(
                    f'<div class="bubble {role}">{body}<div class="bubble-time">{clock}</div></div>',
                    unsafe_allow_html=True,
                )

        typed = st.chat_input("Escreva uma mensagem...")
        prompt = outgoing or typed
        if prompt:
            repo.add_chat_message(st.session_state.conversation_id, "user", prompt)
            if not identified:
                _continue_identity(st.session_state.conversation_id, prompt, model)
            else:
                guided = _guided_reply(repo.list_chat_messages(st.session_state.conversation_id), prompt)
                if guided:
                    repo.add_chat_message(st.session_state.conversation_id, "assistant", guided)
                    st.rerun()
                with st.spinner("Agentes em execução... a primeira resposta do Llama pode levar cerca de 1 minuto."):
                    answer = _answer_with_agent(
                        prompt, st.session_state.active_lead_id, model, st.session_state.conversation_id
                    )
                repo.add_chat_message(st.session_state.conversation_id, "assistant", answer)
            st.rerun()

result = st.session_state.last_result or {}
with st.expander("Debug — intenção, RAG e imóveis"):
    st.text(f"Intent: {result.get('intent')}")
    st.text(f"Rota: {result.get('route')}")
    st.json(result.get("agent_outputs") or {})
    st.json(result.get("retrieved_docs") or [])
    st.json(result.get("properties_found") or [])
    st.json(result.get("schedule_draft") or {})
