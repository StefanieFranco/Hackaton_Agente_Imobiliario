"""Agendamento de visitas/consultas."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from src.db import repository as repo
from src.services.email_ics import send_appointment_email


def schedule_visit_or_consult(
    *,
    lead_id: str,
    seller_id: str,
    inicio_iso: str,
    tipo: str = "visita",
    property_id: str | None = None,
    duracao_minutos: int = 60,
    notas: str = "",
    send_email: bool = True,
) -> dict[str, Any]:
    inicio = datetime.fromisoformat(inicio_iso)
    fim = inicio + timedelta(minutes=duracao_minutos)
    titulo = f"{tipo.title()} — lead {lead_id}"
    if property_id:
        titulo += f" | imóvel {property_id}"

    appt_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
    appt = repo.create_appointment(
        appointment_id=appt_id,
        lead_id=lead_id,
        seller_id=seller_id,
        property_id=property_id,
        tipo=tipo,
        titulo=titulo,
        inicio=inicio,
        fim=fim,
        notas=notas,
    )

    email_result = None
    if send_email:
        email_result = send_appointment_email(appt.id)
        if email_result.get("ok"):
            repo.mark_appointment_email_sent(appt.id)

    return {
        "ok": True,
        "appointment_id": appt.id,
        "titulo": appt.titulo,
        "inicio": appt.inicio.isoformat(),
        "fim": appt.fim.isoformat(),
        "email": email_result,
    }


def appointments_as_calendar_events(
    seller_id: str | None = None,
) -> list[dict[str, Any]]:
    """Formato compatível com streamlit-calendar."""
    color_by_status = {
        "agendado": "#3b82f6",
        "realizado": "#22c55e",
        "no_show": "#ef4444",
        "cancelado": "#9ca3af",
    }
    events = []
    for a in repo.list_appointments(seller_id=seller_id):
        events.append(
            {
                "id": a.id,
                "title": f"{a.titulo} ({a.status})",
                "start": a.inicio.isoformat(),
                "end": a.fim.isoformat(),
                "backgroundColor": color_by_status.get(a.status, "#3b82f6"),
                "borderColor": color_by_status.get(a.status, "#3b82f6"),
            }
        )
    return events
