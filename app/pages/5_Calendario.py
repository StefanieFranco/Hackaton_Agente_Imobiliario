"""Calendário de agendamentos."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from streamlit_calendar import calendar

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import repository as repo
from src.db.models import init_db
from src.tools.scheduling import appointments_as_calendar_events, schedule_visit_or_consult

st.set_page_config(page_title="Calendário", layout="wide")
init_db()

st.title("Calendário de Visitas e Consultas")

sellers = repo.list_sellers()
seller_map = {f"{s.nome} ({s.id})": s.id for s in sellers}
seller_label = st.selectbox("Filtrar vendedor", ["Todos"] + list(seller_map.keys()))
seller_id = None if seller_label == "Todos" else seller_map[seller_label]

events = appointments_as_calendar_events(seller_id=seller_id)
calendar_options = {
    "initialView": "dayGridMonth",
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,listWeek",
    },
    "locale": "pt-br",
}
calendar(events=events, options=calendar_options, key="cal")

st.subheader("Novo agendamento")
leads = repo.list_leads()
lead_map = {f"{l.nome} ({l.id})": l.id for l in leads}
with st.form("novo_agendamento"):
    lead_l = st.selectbox("Lead", list(lead_map.keys()))
    seller_l = st.selectbox("Vendedor", list(seller_map.keys()))
    tipo = st.selectbox("Tipo", ["visita", "consulta"])
    prop_id = st.text_input("ID do imóvel (opcional)", "")
    data = st.date_input("Data", value=datetime.now().date() + timedelta(days=1))
    hora = st.time_input("Hora", value=datetime.strptime("10:00", "%H:%M").time())
    enviar = st.form_submit_button("Agendar e enviar e-mail/ICS")
    if enviar:
        inicio = datetime.combine(data, hora)
        result = schedule_visit_or_consult(
            lead_id=lead_map[lead_l],
            seller_id=seller_map[seller_l],
            inicio_iso=inicio.isoformat(),
            tipo=tipo,
            property_id=prop_id or None,
            send_email=True,
        )
        st.success(f"Criado {result['appointment_id']}")
        st.json(result.get("email"))
        st.rerun()
