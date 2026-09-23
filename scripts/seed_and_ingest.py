"""Carrega seeds JSON no SQLite e indexa documentos no Chroma (RAG)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import SEEDS_DIR, ensure_data_dirs
from src.db.models import Appointment, Lead, Property, Seller, get_session, init_db
from src.rag.ingest import ingest_all_documents


def _load(name: str):
    path = SEEDS_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def seed_sqlite() -> None:
    ensure_data_dirs()
    init_db()
    session = get_session()
    try:
        # limpa tabelas na ordem de FK
        for model in (Appointment, Lead, Property, Seller):
            session.query(model).delete()
        session.commit()

        for s in _load("sellers.json"):
            session.add(Seller(**s))
        session.commit()

        props = _load("properties_residential.json") + _load("properties_commercial.json")
        for p in props:
            session.add(
                Property(
                    id=p["id"],
                    titulo=p["titulo"],
                    segmento=p["segmento"],
                    tipo=p["tipo"],
                    bairro=p["bairro"],
                    cidade=p["cidade"],
                    preco=p["preco"],
                    area_m2=p["area_m2"],
                    quartos=p.get("quartos"),
                    vagas=p.get("vagas"),
                    salas=p.get("salas"),
                    descricao=p["descricao"],
                    amenities=json.dumps(p.get("amenities", []), ensure_ascii=False),
                    image_urls=json.dumps(p.get("image_urls", []), ensure_ascii=False),
                    lat=p.get("lat"),
                    lng=p.get("lng"),
                    ativo=True,
                )
            )
        session.commit()

        for lead in _load("leads.json"):
            session.add(
                Lead(
                    id=lead["id"],
                    nome=lead["nome"],
                    email=lead["email"],
                    telefone=lead["telefone"],
                    origem=lead["origem"],
                    status=lead["status"],
                    chat_finalizado=lead.get("chat_finalizado", False),
                    preferencias_resumo=lead.get("preferencias_resumo", ""),
                    ultimas_buscas=json.dumps(lead.get("ultimas_buscas", []), ensure_ascii=False),
                    seller_id=lead.get("seller_id"),
                    created_at=_parse_dt(lead.get("created_at")) or datetime.utcnow(),
                    last_interaction_at=_parse_dt(lead.get("last_interaction_at")) or datetime.utcnow(),
                    last_contact_at=_parse_dt(lead.get("last_contact_at")),
                )
            )
        session.commit()

        for apt in _load("appointments.json"):
            session.add(
                Appointment(
                    id=apt["id"],
                    lead_id=apt["lead_id"],
                    seller_id=apt["seller_id"],
                    property_id=apt.get("property_id"),
                    tipo=apt["tipo"],
                    titulo=apt["titulo"],
                    inicio=_parse_dt(apt["inicio"]),
                    fim=_parse_dt(apt["fim"]),
                    status=apt.get("status", "agendado"),
                    notas=apt.get("notas", ""),
                    email_enviado=apt.get("email_enviado", False),
                )
            )
        session.commit()
        print(f"SQLite seed OK: {len(props)} imóveis, leads e agendamentos.")
    finally:
        session.close()


def main() -> None:
    # garante JSON atualizados
    from src.seeds.generate_seeds import main as gen

    gen()
    seed_sqlite()
    print("Indexando RAG no Chroma (requer Ollama com nomic-embed-text)...")
    try:
        n = ingest_all_documents()
        print(f"Chroma OK: {n} chunks indexados.")
    except Exception as exc:  # noqa: BLE001
        print(f"AVISO: falha ao indexar Chroma (Ollama offline?): {exc}")
        print("Rode novamente após `ollama pull nomic-embed-text`.")


if __name__ == "__main__":
    main()
