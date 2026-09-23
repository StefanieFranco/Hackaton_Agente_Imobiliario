"""Envio de e-mail com anexo ICS (mock ou SMTP)."""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from icalendar import Calendar, Event

from src.config import (
    EMAIL_MODE,
    OUTBOX_DIR,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
    ensure_data_dirs,
)
from src.db.models import get_session


def build_ics(
    *,
    uid: str,
    titulo: str,
    descricao: str,
    inicio: datetime,
    fim: datetime,
    organizador_email: str,
    participante_email: str,
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Imobiliaria Demo FIAP//PT-BR")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")

    event = Event()
    event.add("uid", uid)
    event.add("summary", titulo)
    event.add("description", descricao)
    event.add("dtstart", inicio)
    event.add("dtend", fim)
    event.add("dtstamp", datetime.utcnow())
    event.add("organizer", f"mailto:{organizador_email}")
    event.add("attendee", f"mailto:{participante_email}")
    cal.add_component(event)
    return cal.to_ical()


def send_appointment_email(appointment_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    session = get_session()
    try:
        from src.db.models import Appointment, Lead, Seller

        appt = session.get(Appointment, appointment_id)
        if not appt:
            return {"ok": False, "erro": "Agendamento não encontrado"}
        lead = session.get(Lead, appt.lead_id)
        seller = session.get(Seller, appt.seller_id)
        if not lead or not seller:
            return {"ok": False, "erro": "Lead ou vendedor ausente"}

        descricao = (
            f"{appt.titulo}\n"
            f"Tipo: {appt.tipo}\n"
            f"Vendedor: {seller.nome} ({seller.email})\n"
            f"Lead: {lead.nome}\n"
            f"Notas: {appt.notas}"
        )
        ics_bytes = build_ics(
            uid=f"{appt.id}@imobdemo.local",
            titulo=appt.titulo,
            descricao=descricao,
            inicio=appt.inicio,
            fim=appt.fim,
            organizador_email=seller.email,
            participante_email=lead.email,
        )

        subject = f"[Imobiliária Demo] {appt.titulo}"
        body = (
            f"Olá {lead.nome},\n\n"
            f"Seu {appt.tipo} foi agendado com {seller.nome}.\n"
            f"Início: {appt.inicio.strftime('%d/%m/%Y %H:%M')}\n"
            f"Fim: {appt.fim.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Segue anexo .ics para adicionar ao seu calendário.\n\n"
            f"Atenciosamente,\nImobiliária Demo FIAP"
        )

        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = lead.email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        ics_part = MIMEApplication(ics_bytes, Name=f"{appt.id}.ics")
        ics_part["Content-Disposition"] = f'attachment; filename="{appt.id}.ics"'
        msg.attach(ics_part)

        if EMAIL_MODE == "smtp":
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                if SMTP_USE_TLS:
                    server.starttls()
                if SMTP_USER:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM, [lead.email], msg.as_string())
            return {"ok": True, "mode": "smtp", "to": lead.email}

        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        eml_path = OUTBOX_DIR / f"{appt.id}.eml"
        ics_path = OUTBOX_DIR / f"{appt.id}.ics"
        eml_path.write_text(msg.as_string(), encoding="utf-8")
        ics_path.write_bytes(ics_bytes)
        return {
            "ok": True,
            "mode": "mock",
            "to": lead.email,
            "eml": str(eml_path),
            "ics": str(ics_path),
        }
    finally:
        session.close()
