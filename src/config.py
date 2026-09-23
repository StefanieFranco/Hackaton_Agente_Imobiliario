"""Configuração central do projeto (variáveis de ambiente)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _path(env_key: str, default: str) -> Path:
    value = os.getenv(env_key, default)
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))

REENGAGEMENT_DAYS = int(os.getenv("REENGAGEMENT_DAYS", "3"))

EMAIL_MODE = os.getenv("EMAIL_MODE", "mock").lower()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "imobiliaria@exemplo.com")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

DATA_DIR = _path("DATA_DIR", "data")
CHROMA_DIR = _path("CHROMA_DIR", "data/chroma")
DB_PATH = _path("DB_PATH", "data/app.db")
OUTBOX_DIR = _path("OUTBOX_DIR", "data/outbox")
SEEDS_DIR = ROOT_DIR / "src" / "seeds"

CHROMA_COLLECTION = "imobiliario_rag"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
