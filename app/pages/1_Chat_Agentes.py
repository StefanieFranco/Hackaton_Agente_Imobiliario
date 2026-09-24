"""Chat multiagente com histórico (uma conversa por lead)."""

from __future__ import annotations

import html
import importlib
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
from src.graph.workflow import run_agent
from src.services.reengagement import run_reengagement

st.set_page_config(page_title="Chat Agentes", layout="wide")
init_db()

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
    .hist-active { border-left: 3px solid #7c3aed; padding-left: 0.4rem; }
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


def _parse_identity(text: str) -> tuple[str, str] | None:
    import re

    match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if not match:
        return None
    email = match.group(0).lower()
    nome = text.replace(match.group(0), " ")
    nome = re.sub(r"(?i)\b(meu nome é|meu nome e|me chamo|eu sou|sou o|sou a|email|e-mail|nome)\b", " ", nome)
    nome = re.sub(r"[,:;|/]+", " ", nome)
    nome = " ".join(nome.split())
    if len(nome) < 2:
        return None
    return nome, email


def _open_chat(conversation_id: str, lead_id: str) -> None:
    st.session_state.conversation_id = conversation_id
    st.session_state.active_lead_id = lead_id


def _answer_with_agent(question: str, lead_id: str | None, model_name: str) -> str:
    try:
        result = run_agent(question, lead_id=lead_id, model_name=model_name)
        st.session_state.last_result = result
        return result.get("final_response") or "Sem resposta."
    except Exception as exc:  # noqa: BLE001
        st.session_state.last_result = {"error": str(exc)}
        return f"Erro ao executar grafo: {exc}"


col_chat, col_hist = st.columns([2.4, 1], gap="large")

with col_hist:
    st.markdown("### Conversas")
    search = st.text_input("Buscar", placeholder="Nome do lead", label_visibility="collapsed")
    if st.button("Novo atendimento", use_container_width=True):
        opened = repo.start_attendance(ASK_IDENTITY)
        st.session_state.conversation_id = opened["conversation_id"]
        st.session_state.active_lead_id = opened["lead_id"]
        st.session_state.last_result = {}
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

with col_chat:
    if not st.session_state.conversation_id:
        st.markdown('<div class="chat-head">Atendimento</div>', unsafe_allow_html=True)
        st.caption("A conversa começa aqui, como no WhatsApp. O agente pede nome e e-mail antes de responder.")
        prompt = st.chat_input("Escreva uma mensagem...")
        if prompt:
            opened = repo.start_attendance("")
            _open_chat(opened["conversation_id"], opened["lead_id"])
            repo.add_chat_message(opened["conversation_id"], "user", prompt)
            identity = _parse_identity(prompt)
            if identity:
                saved = repo.identify_conversation(opened["conversation_id"], identity[0], identity[1])
                _open_chat(saved["conversation_id"], saved["lead_id"])
                repo.add_chat_message(
                    saved["conversation_id"],
                    "assistant",
                    f"Obrigado, {saved['nome']}. Como posso ajudar?",
                )
            else:
                repo.set_pending_question(opened["conversation_id"], prompt)
                repo.add_chat_message(opened["conversation_id"], "assistant", ASK_IDENTITY)
            st.rerun()
    else:
        title = active["nome"] if active else "Conversa"
        identified = bool(active and active.get("identified"))
        st.markdown(f'<div class="chat-head">{html.escape(title)}</div>', unsafe_allow_html=True)
        if identified and active:
            st.markdown(f'<div class="chat-sub">{html.escape(active["email"])}</div>', unsafe_allow_html=True)
        elif active:
            st.markdown('<div class="chat-sub">Aguardando nome e e-mail</div>', unsafe_allow_html=True)

        messages = repo.list_chat_messages(st.session_state.conversation_id)
        last_day = None
        for msg in messages:
            day = msg["created_at"].strftime("%d/%m/%Y") if msg["created_at"] else ""
            if day != last_day:
                st.markdown(f'<div class="day-sep">{day}</div>', unsafe_allow_html=True)
                last_day = day
            role = "user" if msg["role"] == "user" else "assistant"
            clock = msg["created_at"].strftime("%H:%M") if msg["created_at"] else ""
            body = html.escape(msg["content"] or "")
            st.markdown(
                f'<div class="bubble {role}">{body}<div class="bubble-time">{clock}</div></div>',
                unsafe_allow_html=True,
            )

        prompt = st.chat_input("Escreva uma mensagem...")
        if prompt:
            repo.add_chat_message(st.session_state.conversation_id, "user", prompt)
            if not identified:
                identity = _parse_identity(prompt)
                if not identity:
                    if "@" in prompt:
                        reply = "Recebi o e-mail. Pode me dizer também o seu nome?"
                    else:
                        repo.set_pending_question(st.session_state.conversation_id, prompt)
                        reply = ASK_IDENTITY
                    repo.add_chat_message(st.session_state.conversation_id, "assistant", reply)
                else:
                    saved = repo.identify_conversation(
                        st.session_state.conversation_id, identity[0], identity[1]
                    )
                    _open_chat(saved["conversation_id"], saved["lead_id"])
                    pending = repo.take_pending_question(saved["conversation_id"])
                    if pending:
                        with st.spinner("Agentes em execução... a primeira resposta do Llama pode levar cerca de 1 minuto."):
                            answer = _answer_with_agent(pending, saved["lead_id"], model)
                        repo.add_chat_message(saved["conversation_id"], "assistant", answer)
                    else:
                        repo.add_chat_message(
                            saved["conversation_id"],
                            "assistant",
                            f"Obrigado, {saved['nome']}. Como posso ajudar?",
                        )
            else:
                with st.spinner("Agentes em execução... a primeira resposta do Llama pode levar cerca de 1 minuto."):
                    answer = _answer_with_agent(prompt, st.session_state.active_lead_id, model)
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
