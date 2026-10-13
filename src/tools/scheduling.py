"""Agendamento de visitas/consultas."""

from __future__ import annotations

import re
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


VISIT_TIMES = ("10:00", "14:00", "16:00")
_WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def upcoming_visit_dates(n: int = 3, today: datetime | None = None) -> list[datetime]:
    """Próximos dias úteis, a partir de amanhã, sem domingo."""
    start = (today or datetime.now()).date() + timedelta(days=1)
    found: list[datetime] = []
    day = start
    while len(found) < n:
        if day.weekday() != 6:
            found.append(datetime.combine(day, datetime.min.time()))
        day += timedelta(days=1)
    return found


def _choice_index(text: str) -> int | None:
    q = text.lower()
    numbered = re.search(r"\b([123])\b", q)
    if numbered and not re.search(r"\d{1,2}/\d{1,2}", q) and not re.search(r"\d{1,2}\s*h", q):
        return int(numbered.group(1)) - 1
    if re.search(r"\bprimeir[ao]\b", q):
        return 0
    if re.search(r"\bterceir[ao]\b", q):
        return 2
    return None


def match_visit_date(text: str, dates: list[str]) -> str | None:
    q = text.lower()
    parsed = [datetime.fromisoformat(item).date() for item in dates]
    for day in parsed:
        if day.strftime("%d/%m/%Y") in q or day.strftime("%d/%m") in q:
            return day.isoformat()
        if _WEEKDAYS[day.weekday()] in q:
            return day.isoformat()
    index = _choice_index(q)
    if index is not None and index < len(parsed):
        return parsed[index].isoformat()
    return None


def match_visit_time(text: str, times: tuple[str, ...] = VISIT_TIMES) -> str | None:
    q = text.lower().replace(".", ":")
    for slot in times:
        hour = int(slot.split(":")[0])
        if slot in q or f"{hour}h" in q or f"{hour:02d}h" in q or f"{hour}:00" in q:
            return slot
    index = _choice_index(text)
    if index is not None and index < len(times):
        return times[index]
    return None


def format_date_offer(dates: list[str], seller_name: str, property_id: str | None) -> str:
    lines = [f"A visita será com {seller_name}."]
    if property_id:
        lines.append(f"Escolha um dia para o imóvel {property_id}:")
    else:
        lines.append("Escolha um dia para a visita:")
    for i, iso in enumerate(dates, 1):
        day = datetime.fromisoformat(iso).date()
        lines.append(f"{i}. {_WEEKDAYS[day.weekday()]}, {day.strftime('%d/%m/%Y')}")
    lines.append("Responda com o número ou a data.")
    return "\n".join(lines)


def format_time_offer(day_iso: str, seller_name: str) -> str:
    day = datetime.fromisoformat(day_iso).date()
    lines = [
        f"Com {seller_name}, em {day.strftime('%d/%m/%Y')}, escolha um horário:",
    ]
    for i, slot in enumerate(VISIT_TIMES, 1):
        lines.append(f"{i}. {slot}")
    lines.append("Responda com o número ou o horário.")
    return "\n".join(lines)


def format_visit_confirmation(
    *,
    seller_name: str,
    property_id: str | None,
    inicio: datetime,
    appointment_id: str,
) -> str:
    place = f" no imóvel {property_id}" if property_id else ""
    return (
        f"Visita marcada com {seller_name}{place}.\n"
        f"{inicio.strftime('%d/%m/%Y')} às {inicio.strftime('%H:%M')}.\n"
        "O convite foi enviado para o seu e-mail.\n"
        f"Abrir no calendário: /Calendario?visita={appointment_id}."
    )


def _asks_attendant(text: str) -> bool:
    q = text.lower()
    return any(w in q for w in ("atendente", "vendedor", "corretor", "com quem", "com qual"))


def _starts_booking(text: str) -> bool:
    q = text.lower()
    return any(w in q for w in ("agendar", "marcar visita", "marcar uma visita", "quero visitar"))


def advance_visit_plan(
    query: str,
    draft: dict[str, Any] | None,
    *,
    seller_id: str,
    seller_name: str,
    property_id: str | None,
    latest: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Conduz a escolha de dia e horário. Só devolve dados de gravação no último passo."""
    current = dict(draft or {})
    found = re.search(r"(RES|COM)-\d{3}", query.upper())
    if found:
        property_id = found.group(0)

    picked_time = match_visit_time(query)
    picked_date = match_visit_date(query, current.get("dates") or [])
    if _starts_booking(query) and not (current.get("step") == "time" and picked_time):
        dates = [item.date().isoformat() for item in upcoming_visit_dates()]
        nxt = {
            "step": "date",
            "property_id": property_id,
            "seller_id": seller_id,
            "seller_name": seller_name,
            "dates": dates,
            "date": None,
            "times": list(VISIT_TIMES),
        }
        return format_date_offer(dates, seller_name, property_id), nxt, None

    if _asks_attendant(query) and not picked_date and not picked_time:
        if current.get("step") == "time" and current.get("date"):
            text = f"Você encontra {seller_name} na visita.\n" + format_time_offer(current["date"], seller_name)
            return text, current, None
        if current.get("step") == "date" and current.get("dates"):
            text = f"Você encontra {seller_name} na visita.\n" + format_date_offer(
                current["dates"], seller_name, current.get("property_id")
            )
            return text, current, None
        if latest:
            text = (
                f"Você encontra {latest['seller_name']} na visita.\n"
                f"{latest['when']}.\n"
                f"Abrir no calendário: /Calendario?visita={latest['appointment_id']}."
            )
            return text, current or None, None
        dates = [item.date().isoformat() for item in upcoming_visit_dates()]
        nxt = {
            "step": "date",
            "property_id": property_id,
            "seller_id": seller_id,
            "seller_name": seller_name,
            "dates": dates,
            "date": None,
            "times": list(VISIT_TIMES),
        }
        return f"Você encontra {seller_name} na visita.\n" + format_date_offer(dates, seller_name, property_id), nxt, None

    if current.get("step") == "time":
        if not picked_time:
            text = "Não identifiquei o horário.\n" + format_time_offer(current["date"], seller_name)
            return text, current, None
        inicio = datetime.fromisoformat(current["date"]).replace(
            hour=int(picked_time.split(":")[0]), minute=0, second=0, microsecond=0
        )
        booking = {
            "inicio_iso": inicio.isoformat(),
            "property_id": current.get("property_id") or property_id,
            "seller_id": current.get("seller_id") or seller_id,
            "seller_name": current.get("seller_name") or seller_name,
            "tipo": "visita",
        }
        return "", None, booking

    if current.get("step") == "date":
        if not picked_date:
            text = "Não identifiquei o dia.\n" + format_date_offer(
                current.get("dates") or [], seller_name, current.get("property_id")
            )
            return text, current, None
        current["date"] = picked_date
        current["step"] = "time"
        current["seller_name"] = seller_name
        return format_time_offer(picked_date, seller_name), current, None

    dates = [item.date().isoformat() for item in upcoming_visit_dates()]
    nxt = {
        "step": "date",
        "property_id": property_id,
        "seller_id": seller_id,
        "seller_name": seller_name,
        "dates": dates,
        "date": None,
        "times": list(VISIT_TIMES),
    }
    return format_date_offer(dates, seller_name, property_id), nxt, None


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
