"""Repositório de acesso aos dados (SQLite)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import REENGAGEMENT_DAYS
from src.db.models import (
    Appointment,
    ChatMessage,
    Conversation,
    Interaction,
    Lead,
    Property,
    Seller,
    get_session,
)


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _from_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default if default is not None else []


# --- Properties ---


def list_properties(
    session: Session | None = None,
    segmento: str | None = None,
    tipo: str | None = None,
    bairro: str | None = None,
    preco_min: float | None = None,
    preco_max: float | None = None,
    quartos_min: int | None = None,
    quartos_max: int | None = None,
    limit: int = 50,
) -> list[Property]:
    own = session is None
    session = session or get_session()
    try:
        q = select(Property).where(Property.ativo.is_(True))
        if segmento:
            q = q.where(Property.segmento == segmento)
        if tipo:
            q = q.where(Property.tipo == tipo)
        if bairro:
            q = q.where(Property.bairro.ilike(f"%{bairro}%"))
        if preco_min is not None:
            q = q.where(Property.preco >= preco_min)
        if preco_max is not None:
            q = q.where(Property.preco <= preco_max)
        if quartos_min is not None:
            q = q.where(Property.quartos >= quartos_min)
        if quartos_max is not None:
            q = q.where(Property.quartos <= quartos_max)
        q = q.order_by(Property.preco).limit(limit)
        return list(session.scalars(q).all())
    finally:
        if own:
            session.close()


def get_property(property_id: str, session: Session | None = None) -> Property | None:
    own = session is None
    session = session or get_session()
    try:
        return session.get(Property, property_id)
    finally:
        if own:
            session.close()


def property_to_dict(p: Property) -> dict[str, Any]:
    return {
        "id": p.id,
        "titulo": p.titulo,
        "segmento": p.segmento,
        "tipo": p.tipo,
        "bairro": p.bairro,
        "cidade": p.cidade,
        "preco": p.preco,
        "area_m2": p.area_m2,
        "quartos": p.quartos,
        "vagas": p.vagas,
        "salas": p.salas,
        "descricao": p.descricao,
        "amenities": _from_json(p.amenities, []),
        "image_urls": _from_json(p.image_urls, []),
        "lat": p.lat,
        "lng": p.lng,
    }


# --- Sellers / Leads ---


def list_sellers(session: Session | None = None) -> list[Seller]:
    own = session is None
    session = session or get_session()
    try:
        return list(session.scalars(select(Seller).order_by(Seller.nome)).all())
    finally:
        if own:
            session.close()


def list_leads(
    session: Session | None = None,
    status: str | None = None,
    seller_id: str | None = None,
) -> list[Lead]:
    own = session is None
    session = session or get_session()
    try:
        q = select(Lead).order_by(Lead.last_interaction_at.desc())
        if status:
            q = q.where(Lead.status == status)
        if seller_id:
            q = q.where(Lead.seller_id == seller_id)
        return list(session.scalars(q).all())
    finally:
        if own:
            session.close()


def get_lead(lead_id: str, session: Session | None = None) -> Lead | None:
    own = session is None
    session = session or get_session()
    try:
        return session.get(Lead, lead_id)
    finally:
        if own:
            session.close()


def update_lead(
    lead_id: str,
    *,
    status: str | None = None,
    chat_finalizado: bool | None = None,
    preferencias_resumo: str | None = None,
    ultimas_buscas: list | dict | None = None,
    touch_interaction: bool = False,
    session: Session | None = None,
) -> Lead | None:
    own = session is None
    session = session or get_session()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return None
        if status is not None:
            lead.status = status
        if chat_finalizado is not None:
            lead.chat_finalizado = chat_finalizado
        if preferencias_resumo is not None:
            lead.preferencias_resumo = preferencias_resumo
        if ultimas_buscas is not None:
            lead.ultimas_buscas = _to_json(ultimas_buscas)
        if touch_interaction:
            lead.last_interaction_at = datetime.utcnow()
        session.commit()
        session.refresh(lead)
        return lead
    finally:
        if own:
            session.close()


def append_search_preference(
    lead_id: str,
    busca: dict[str, Any],
    session: Session | None = None,
) -> None:
    own = session is None
    session = session or get_session()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return
        history = _from_json(lead.ultimas_buscas, [])
        if not isinstance(history, list):
            history = []
        busca = {**busca, "em": datetime.utcnow().isoformat()}
        history.insert(0, busca)
        lead.ultimas_buscas = _to_json(history[:10])
        # resumo simples
        bairros = [h.get("bairro") for h in history if h.get("bairro")]
        segmentos = [h.get("segmento") for h in history if h.get("segmento")]
        lead.preferencias_resumo = (
            f"Bairros recentes: {', '.join(list(dict.fromkeys(bairros))[:5]) or 'n/d'}. "
            f"Segmentos: {', '.join(list(dict.fromkeys(segmentos))[:3]) or 'n/d'}."
        )
        lead.last_interaction_at = datetime.utcnow()
        if lead.status == "novo":
            lead.status = "interessado"
        session.commit()
    finally:
        if own:
            session.close()


def add_interaction(
    lead_id: str,
    tipo: str,
    conteudo: str,
    agente: str | None = None,
    session: Session | None = None,
) -> Interaction:
    own = session is None
    session = session or get_session()
    try:
        interaction = Interaction(
            lead_id=lead_id,
            tipo=tipo,
            conteudo=conteudo,
            agente=agente,
        )
        session.add(interaction)
        lead = session.get(Lead, lead_id)
        if lead:
            lead.last_interaction_at = datetime.utcnow()
            if tipo == "reengajamento":
                lead.last_contact_at = datetime.utcnow()
        session.commit()
        session.refresh(interaction)
        return interaction
    finally:
        if own:
            session.close()


def inactive_leads_for_reengagement(
    days: int | None = None,
    session: Session | None = None,
) -> list[Lead]:
    own = session is None
    session = session or get_session()
    days = days if days is not None else REENGAGEMENT_DAYS
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        q = (
            select(Lead)
            .where(Lead.chat_finalizado.is_(False))
            .where(Lead.status != "finalizado")
            .where(Lead.last_interaction_at < cutoff)
        )
        return list(session.scalars(q).all())
    finally:
        if own:
            session.close()


# --- Appointments ---


def list_appointments(
    session: Session | None = None,
    seller_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Appointment]:
    own = session is None
    session = session or get_session()
    try:
        q = select(Appointment).order_by(Appointment.inicio)
        if seller_id:
            q = q.where(Appointment.seller_id == seller_id)
        if start:
            q = q.where(Appointment.inicio >= start)
        if end:
            q = q.where(Appointment.inicio <= end)
        return list(session.scalars(q).all())
    finally:
        if own:
            session.close()


def create_appointment(
    *,
    appointment_id: str,
    lead_id: str,
    seller_id: str,
    property_id: str | None,
    tipo: str,
    titulo: str,
    inicio: datetime,
    fim: datetime,
    notas: str = "",
    session: Session | None = None,
) -> Appointment:
    own = session is None
    session = session or get_session()
    try:
        appt = Appointment(
            id=appointment_id,
            lead_id=lead_id,
            seller_id=seller_id,
            property_id=property_id,
            tipo=tipo,
            titulo=titulo,
            inicio=inicio,
            fim=fim,
            notas=notas,
            status="agendado",
        )
        session.add(appt)
        session.commit()
        session.refresh(appt)
        return appt
    finally:
        if own:
            session.close()


def mark_appointment_email_sent(appointment_id: str, session: Session | None = None) -> None:
    own = session is None
    session = session or get_session()
    try:
        appt = session.get(Appointment, appointment_id)
        if appt:
            appt.email_enviado = True
            session.commit()
    finally:
        if own:
            session.close()


# --- Reports ---


def funnel_counts(
    session: Session | None = None,
    seller_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, int]:
    own = session is None
    session = session or get_session()
    try:
        statuses = ["novo", "interessado", "negociacao", "comprado", "finalizado"]
        result: dict[str, int] = {}
        for st in statuses:
            q = select(func.count()).select_from(Lead).where(Lead.status == st)
            if seller_id:
                q = q.where(Lead.seller_id == seller_id)
            if start:
                q = q.where(Lead.created_at >= start)
            if end:
                q = q.where(Lead.created_at <= end)
            result[st] = int(session.scalar(q) or 0)
        result["total"] = sum(result.values())
        return result
    finally:
        if own:
            session.close()


def appointment_stats(
    session: Session | None = None,
    seller_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, int]:
    own = session is None
    session = session or get_session()
    try:
        out: dict[str, int] = {}
        for st in ["agendado", "realizado", "no_show", "cancelado"]:
            q = select(func.count()).select_from(Appointment).where(Appointment.status == st)
            if seller_id:
                q = q.where(Appointment.seller_id == seller_id)
            if start:
                q = q.where(Appointment.inicio >= start)
            if end:
                q = q.where(Appointment.inicio <= end)
            out[st] = int(session.scalar(q) or 0)
        return out
    finally:
        if own:
            session.close()


def top_bairros_buscados(session: Session | None = None, limit: int = 5) -> list[tuple[str, int]]:
    own = session is None
    session = session or get_session()
    try:
        counts: dict[str, int] = {}
        for lead in session.scalars(select(Lead)).all():
            for item in _from_json(lead.ultimas_buscas, []):
                b = item.get("bairro")
                if b:
                    counts[b] = counts.get(b, 0) + 1
        return sorted(counts.items(), key=lambda x: -x[1])[:limit]
    finally:
        if own:
            session.close()


def start_attendance(opening_message: str) -> dict[str, Any]:
    """Abre um atendimento sem formulário. O agente pede nome e e-mail na conversa."""
    import uuid

    session = get_session()
    try:
        seller = session.scalars(select(Seller).order_by(Seller.id)).first()
        lead_id = f"LEAD-{uuid.uuid4().hex[:6].upper()}"
        lead = Lead(
            id=lead_id,
            nome="Visitante",
            email=f"pendente-{lead_id.lower()}@pendente.local",
            telefone="",
            origem="direto",
            status="novo",
            chat_finalizado=False,
            preferencias_resumo="",
            ultimas_buscas="[]",
            seller_id=seller.id if seller else None,
            created_at=datetime.utcnow(),
            last_interaction_at=datetime.utcnow(),
        )
        conv = Conversation(
            id=f"CONV-{lead_id}",
            lead_id=lead_id,
            title="Novo atendimento",
            pending_question="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(lead)
        session.add(conv)
        session.flush()
        if opening_message.strip():
            session.add(
                ChatMessage(
                    conversation_id=conv.id,
                    role="assistant",
                    content=opening_message,
                    created_at=datetime.utcnow(),
                )
            )
        session.commit()
        return {
            "lead_id": lead.id,
            "conversation_id": conv.id,
            "nome": lead.nome,
            "email": lead.email,
            "identified": False,
        }
    finally:
        session.close()


def lead_is_identified(email: str | None) -> bool:
    if not email:
        return False
    return not email.lower().endswith("@pendente.local")


def set_pending_question(conversation_id: str, question: str) -> None:
    session = get_session()
    try:
        conv = session.get(Conversation, conversation_id)
        if conv and question.strip() and not (conv.pending_question or "").strip():
            conv.pending_question = question.strip()
            session.commit()
    finally:
        session.close()


def take_pending_question(conversation_id: str) -> str:
    session = get_session()
    try:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            return ""
        question = conv.pending_question or ""
        conv.pending_question = ""
        session.commit()
        return question
    finally:
        session.close()


def identify_conversation(conversation_id: str, nome: str, email: str) -> dict[str, Any]:
    """Grava nome e e-mail no lead. Se o e-mail já existir, une na conversa daquele lead."""
    session = get_session()
    try:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("Conversa não encontrada")
        lead = session.get(Lead, conv.lead_id)
        email_norm = email.strip().lower()
        nome = nome.strip()
        other = session.scalars(
            select(Lead).where(func.lower(Lead.email) == email_norm, Lead.id != lead.id)
        ).first()
        if other:
            other_conv = session.scalars(
                select(Conversation).where(Conversation.lead_id == other.id)
            ).first()
            if other_conv is None:
                other_conv = Conversation(
                    id=f"CONV-{other.id}",
                    lead_id=other.id,
                    title=f"Atendimento — {nome or other.nome}",
                    pending_question=conv.pending_question or "",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(other_conv)
                session.flush()
            elif conv.pending_question and not other_conv.pending_question:
                other_conv.pending_question = conv.pending_question
            for msg in session.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv.id)):
                msg.conversation_id = other_conv.id
            other.nome = nome or other.nome
            other.last_interaction_at = datetime.utcnow()
            other_conv.updated_at = datetime.utcnow()
            other_conv.title = f"Atendimento — {other.nome}"
            session.delete(conv)
            session.delete(lead)
            session.commit()
            return {
                "lead_id": other.id,
                "conversation_id": other_conv.id,
                "nome": other.nome,
                "email": other.email,
                "identified": True,
            }

        lead.nome = nome
        lead.email = email_norm
        lead.last_interaction_at = datetime.utcnow()
        conv.title = f"Atendimento — {nome}"
        conv.updated_at = datetime.utcnow()
        session.commit()
        return {
            "lead_id": lead.id,
            "conversation_id": conv.id,
            "nome": lead.nome,
            "email": lead.email,
            "identified": True,
        }
    finally:
        session.close()


def get_or_create_lead_conversation(nome: str, email: str) -> dict[str, Any]:
    """Reabre o lead pelo e-mail ou cria um novo. Sempre devolve a única conversa."""
    import uuid

    nome = nome.strip()
    email_norm = email.strip().lower()
    session = get_session()
    try:
        lead = session.scalars(select(Lead).where(func.lower(Lead.email) == email_norm)).first()
        if lead is None:
            seller = session.scalars(select(Seller).order_by(Seller.id)).first()
            lead = Lead(
                id=f"LEAD-{uuid.uuid4().hex[:6].upper()}",
                nome=nome,
                email=email_norm,
                telefone="",
                origem="direto",
                status="novo",
                chat_finalizado=False,
                preferencias_resumo="",
                ultimas_buscas="[]",
                seller_id=seller.id if seller else None,
                created_at=datetime.utcnow(),
                last_interaction_at=datetime.utcnow(),
            )
            session.add(lead)
            session.flush()
        elif nome and lead.nome != nome:
            lead.nome = nome

        conv = session.scalars(select(Conversation).where(Conversation.lead_id == lead.id)).first()
        if conv is None:
            conv = Conversation(
                id=f"CONV-{lead.id}",
                lead_id=lead.id,
                title=f"Atendimento — {lead.nome}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(conv)
        session.commit()
        return {
            "lead_id": lead.id,
            "conversation_id": conv.id,
            "nome": lead.nome,
            "email": lead.email,
        }
    finally:
        session.close()


def list_conversation_menu(search: str | None = None) -> list[dict[str, Any]]:
    session = get_session()
    try:
        q = select(Conversation).order_by(Conversation.updated_at.desc())
        rows = []
        for conv in session.scalars(q).all():
            lead = session.get(Lead, conv.lead_id)
            nome = lead.nome if lead else conv.title
            email = lead.email if lead else ""
            identified = bool(email) and not email.lower().endswith("@pendente.local")
            if not identified:
                nome = "Novo atendimento"
                email = ""
            if search and search.lower() not in nome.lower() and search.lower() not in (conv.title or "").lower():
                continue
            last = session.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conv.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            ).first()
            preview = (last.content if last else "Sem mensagens")[:80]
            rows.append(
                {
                    "conversation_id": conv.id,
                    "lead_id": conv.lead_id,
                    "nome": nome,
                    "email": email,
                    "identified": identified,
                    "title": conv.title,
                    "preview": preview,
                    "updated_at": conv.updated_at,
                }
            )
        return rows
    finally:
        session.close()


def list_chat_messages(conversation_id: str) -> list[dict[str, Any]]:
    session = get_session()
    try:
        msgs = session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        ).all()
        return [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in msgs
        ]
    finally:
        session.close()


def add_chat_message(conversation_id: str, role: str, content: str) -> None:
    session = get_session()
    try:
        session.add(
            ChatMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
                created_at=datetime.utcnow(),
            )
        )
        conv = session.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = datetime.utcnow()
            if role == "user" and content:
                conv.title = content.strip()[:80]
            lead = session.get(Lead, conv.lead_id) if conv else None
            if lead:
                lead.last_interaction_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()


def origem_distribution(session: Session | None = None) -> dict[str, int]:
    own = session is None
    session = session or get_session()
    try:
        rows = session.execute(
            select(Lead.origem, func.count()).group_by(Lead.origem)
        ).all()
        return {str(o): int(c) for o, c in rows}
    finally:
        if own:
            session.close()
