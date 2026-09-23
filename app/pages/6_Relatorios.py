"""Relatórios gerenciais."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OLLAMA_MODEL
from src.db import repository as repo
from src.db.models import init_db
from src.services.reports import build_report

st.set_page_config(page_title="Relatórios", layout="wide")
init_db()

st.title("Relatórios Gerenciais")

c1, c2, c3 = st.columns(3)
with c1:
    periodo = st.selectbox("Período", ["dia", "semana", "mes"], index=2)
with c2:
    sellers = repo.list_sellers()
    smap = {"Todos": None, **{f"{s.nome} ({s.id})": s.id for s in sellers}}
    seller_label = st.selectbox("Vendedor", list(smap.keys()))
with c3:
    model = st.selectbox("Modelo narrativa", [OLLAMA_MODEL, "llama3.2:3b"])

if st.button("Gerar relatório", type="primary"):
    with st.spinner("Calculando métricas e narrativa..."):
        report = build_report(
            periodo=periodo,
            seller_id=smap[seller_label],
            with_narrative=True,
            model=model,
        )
    st.session_state["last_report"] = report

report = st.session_state.get("last_report")
if not report:
    st.info("Clique em **Gerar relatório** para ver KPIs e textos explicativos.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Leads gerados (funil)", report["leads_gerados"])
m2.metric("Interessados", report["leads_interessados"])
m3.metric("Negociação (efetivar)", report["leads_negociacao"])
m4.metric("Comprados / pós-venda", report["leads_comprados_pos_venda"])

st.subheader("Conversões")
c1, c2, c3 = st.columns(3)
c1.metric("→ Interessado %", report["conv_interessado_pct"])
c2.metric("→ Negociação %", report["conv_negociacao_pct"])
c3.metric("→ Compra %", report["conv_compra_pct"])

st.subheader("Agendamentos no período")
st.json(report["agendamentos"])

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Origens dos leads")
    if report["origens"]:
        st.bar_chart(pd.Series(report["origens"]))
with col_b:
    st.subheader("Bairros mais buscados")
    if report["top_bairros"]:
        st.dataframe(pd.DataFrame(report["top_bairros"], columns=["bairro", "buscas"]))

st.subheader("Análise narrativa")
st.write(report.get("narrative") or "")
