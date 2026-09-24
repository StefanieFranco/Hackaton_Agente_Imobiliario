"""Schema SQLite (SQLAlchemy) para imóveis, leads, agenda e interações."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from src.config import DB_PATH, ensure_data_dirs


class Base(DeclarativeBase):
    pass


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    segmento: Mapped[str] = mapped_column(String(32))  # residencial | empresarial
    tipo: Mapped[str] = mapped_column(String(64))
    bairro: Mapped[str] = mapped_column(String(100))
    cidade: Mapped[str] = mapped_column(String(100))
    preco: Mapped[float] = mapped_column(Float)
    area_m2: Mapped[float] = mapped_column(Float)
    quartos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vagas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    descricao: Mapped[str] = mapped_column(Text)
    amenities: Mapped[str] = mapped_column(Text, default="")  # JSON string
    image_urls: Mapped[str] = mapped_column(Text, default="")  # JSON string
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    telefone: Mapped[str] = mapped_column(String(40))
    especialidade: Mapped[str] = mapped_column(String(64), default="geral")

    leads: Mapped[list["Lead"]] = relationship(back_populates="seller")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="seller")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    telefone: Mapped[str] = mapped_column(String(40))
    origem: Mapped[str] = mapped_column(String(40))  # google, quinto_andar, zap...
    status: Mapped[str] = mapped_column(String(32), default="novo")
    chat_finalizado: Mapped[bool] = mapped_column(Boolean, default=False)
    preferencias_resumo: Mapped[str] = mapped_column(Text, default="")
    ultimas_buscas: Mapped[str] = mapped_column(Text, default="")  # JSON
    seller_id: Mapped[str | None] = mapped_column(ForeignKey("sellers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    seller: Mapped[Seller | None] = relationship(back_populates="leads")
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="lead")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="lead")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="lead", uselist=False)


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    tipo: Mapped[str] = mapped_column(String(40))  # chat | reengajamento | email
    conteudo: Mapped[str] = mapped_column(Text)
    agente: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped[Lead] = relationship(back_populates="interactions")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    seller_id: Mapped[str] = mapped_column(ForeignKey("sellers.id"))
    property_id: Mapped[str | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(String(40))  # visita | consulta
    titulo: Mapped[str] = mapped_column(String(200))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fim: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="agendado")  # agendado|realizado|no_show|cancelado
    notas: Mapped[str] = mapped_column(Text, default="")
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False)

    lead: Mapped[Lead] = relationship(back_populates="appointments")
    seller: Mapped[Seller] = relationship(back_populates="appointments")


class Conversation(Base):
    """Uma conversa por lead."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), unique=True)
    title: Mapped[str] = mapped_column(String(200), default="Atendimento")
    pending_question: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped[Lead] = relationship(back_populates="conversation")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="conversation")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        ensure_data_dirs()
        _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session():
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "conversations" in tables:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(conversations)"))}
            if "pending_question" not in cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN pending_question TEXT DEFAULT ''"))
