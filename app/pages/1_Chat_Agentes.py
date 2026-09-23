"""Chat multiagente."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OLLAMA_MODEL, REENGAGEMENT_DAYS
from src.db import repository as repo
from src.db.models import init_db
from src.graph.workflow import run_agent
from src.services.reengagement import run_reengagement

st.set_page_config(page_title="Chat Agentes", layout="wide")
init_db()

st.title("Chat — Agentes Imobiliários")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = {}

with st.sidebar:
    st.header("Configuração")
    model = st.selectbox("Modelo Ollama", [OLLAMA_MODEL, "llama3.2:3b", "llama3.1:8b"], index=0)
    leads = repo.list_leads()
    lead_options = {f"{l.id} — {l.nome} ({l.status})": l.id for l in leads}
    lead_label = st.selectbox("Lead vinculado", ["(nenhum)"] + list(lead_options.keys()))
    lead_id = None if lead_label == "(nenhum)" else lead_options[lead_label]

    if st.button("Verificar leads inativos (reengajamento)"):
        with st.spinner(f"Buscando leads sem interação há {REENGAGEMENT_DAYS}+ dias..."):
            results = run_reengagement(model=model)
        if not results:
            st.success("Nenhum lead elegível para reengajamento.")
        else:
            st.warning(f"{len(results)} mensagem(ns) gerada(s):")
            for r in results:
                st.write(f"**{r['nome']}** (`{r['lead_id']}`)")
                st.write(r["mensagem"])

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Pergunte sobre imóveis, financiamento, jurídico, visitas...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Agentes em execução..."):
            try:
                result = run_agent(prompt, lead_id=lead_id, model_name=model)
                st.session_state.last_result = result
                answer = result.get("final_response") or "Sem resposta."
            except Exception as exc:  # noqa: BLE001
                answer = f"Erro ao executar grafo: {exc}"
                st.session_state.last_result = {"error": str(exc)}
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})

result = st.session_state.last_result or {}
with st.expander("Debug — intenção e agentes", expanded=False):
    st.write("Intent:", result.get("intent"))
    st.write("Rota:", result.get("route"))
    st.json(result.get("agent_outputs") or {})

with st.expander("Documentos RAG recuperados"):
    st.json(result.get("retrieved_docs") or [])

with st.expander("Imóveis encontrados"):
    st.json(result.get("properties_found") or [])

with st.expander("Agendamento / e-mail"):
    st.json(result.get("schedule_draft") or {})
