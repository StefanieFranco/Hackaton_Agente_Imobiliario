"""CRM de leads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import repository as repo
from src.db.models import init_db
from src.tools.lead_crm import set_chat_finalizado

st.set_page_config(page_title="Leads CRM", layout="wide")
init_db()

st.title("Leads — CRM")

sellers = {s.id: s.nome for s in repo.list_sellers()}
status_filter = st.selectbox(
    "Filtrar status",
    ["Todos", "novo", "interessado", "negociacao", "comprado", "finalizado"],
)
leads = repo.list_leads(status=None if status_filter == "Todos" else status_filter)

rows = []
for l in leads:
    rows.append(
        {
            "id": l.id,
            "nome": l.nome,
            "email": l.email,
            "telefone": l.telefone,
            "origem": l.origem,
            "status": l.status,
            "chat_finalizado": l.chat_finalizado,
            "vendedor": sellers.get(l.seller_id or "", l.seller_id),
            "preferencias": l.preferencias_resumo,
            "ultima_interacao": l.last_interaction_at,
        }
    )

st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.subheader("Detalhe / ações")
ids = [l.id for l in leads]
if not ids:
    st.warning("Nenhum lead. Rode o seed.")
    st.stop()

sel = st.selectbox("Lead", ids)
lead = repo.get_lead(sel)
if lead:
    st.write(f"**{lead.nome}** · origem `{lead.origem}` · status `{lead.status}`")
    st.write(lead.preferencias_resumo)
    st.json(json.loads(lead.ultimas_buscas or "[]"))

    c1, c2, c3 = st.columns(3)
    with c1:
        new_status = st.selectbox(
            "Atualizar status",
            ["novo", "interessado", "negociacao", "comprado", "finalizado"],
            index=["novo", "interessado", "negociacao", "comprado", "finalizado"].index(lead.status)
            if lead.status in ["novo", "interessado", "negociacao", "comprado", "finalizado"]
            else 0,
        )
        if st.button("Salvar status"):
            repo.update_lead(lead.id, status=new_status, touch_interaction=True)
            st.success("Status atualizado")
            st.rerun()
    with c2:
        if st.button("Marcar chat como finalizado"):
            set_chat_finalizado(lead.id, True)
            st.success("Chat finalizado (não reengajar)")
            st.rerun()
    with c3:
        if st.button("Reabrir chat"):
            repo.update_lead(lead.id, chat_finalizado=False, status="interessado", touch_interaction=True)
            st.success("Chat reaberto")
            st.rerun()
