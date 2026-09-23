"""Home — Agente Imobiliário Multiagente FIAP."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OLLAMA_MODEL, ensure_data_dirs
from src.db.models import init_db

st.set_page_config(
    page_title="Imobiliária Multiagente FIAP",
    page_icon="🏠",
    layout="wide",
)

ensure_data_dirs()
init_db()

st.title("Imobiliária Multiagente — Projeto FIAP")
st.markdown(
    """
Sistema acadêmico com **LangGraph/LangChain**, **RAG (Chroma)** e **Llama 3.1 8B via Ollama**
(origem Hugging Face: `meta-llama/Meta-Llama-3.1-8B-Instruct`).

### Navegue pelas páginas
1. **Chat Agentes** — conversa multiagente  
2. **Catálogo** — 100 imóveis fictícios (50 residenciais + 50 empresariais)  
3. **Detalhe do Imóvel** — ficha e imagens  
4. **Leads CRM** — origem, preferências e funil  
5. **Calendário** — visitas e consultas  
6. **Relatórios** — visão gerencial com narrativa  

### Setup rápido
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
python scripts/seed_and_ingest.py
streamlit run app/Home.py
```
"""
)

st.info(f"Modelo padrão configurado: `{OLLAMA_MODEL}`")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Imóveis seed", "100")
with col2:
    st.metric("Agentes", "8+")
with col3:
    st.metric("Vetores", "ChromaDB")
