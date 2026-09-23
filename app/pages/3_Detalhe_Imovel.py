"""Detalhe do imóvel."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import repository as repo
from src.db.models import init_db

st.set_page_config(page_title="Detalhe Imóvel", layout="wide")
init_db()

st.title("Detalhe do Imóvel")

all_ids = [p.id for p in repo.list_properties(limit=100)]
default = st.session_state.get("selected_property_id") or (all_ids[0] if all_ids else "")
prop_id = st.selectbox("Selecione o imóvel", all_ids, index=all_ids.index(default) if default in all_ids else 0)

p = repo.get_property(prop_id)
if not p:
    st.error("Imóvel não encontrado. Rode `python scripts/seed_and_ingest.py`.")
    st.stop()

d = repo.property_to_dict(p)
st.header(d["titulo"])
st.write(f"`{d['id']}` · **{d['segmento']}** · {d['tipo']} · {d['bairro']}, {d['cidade']}")

images = d.get("image_urls") or []
if images:
    tabs = st.tabs([f"Foto {i+1}" for i in range(len(images))])
    for tab, url in zip(tabs, images):
        with tab:
            st.image(url, use_container_width=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Preço", f"R$ {d['preco']:,.0f}")
c2.metric("Área", f"{d['area_m2']} m²")
c3.metric("Quartos", d.get("quartos") or "—")
c4.metric("Vagas", d.get("vagas") or "—")

st.subheader("Descrição")
st.write(d["descricao"])
st.write("**Comodidades:**", ", ".join(d.get("amenities") or []))

col_a, col_b = st.columns(2)
with col_a:
    if st.button("Falar no chat sobre este imóvel"):
        st.session_state.setdefault("messages", [])
        st.session_state["messages"].append(
            {
                "role": "user",
                "content": f"Quero saber mais sobre o imóvel {d['id']} em {d['bairro']}.",
            }
        )
        st.switch_page("pages/1_Chat_Agentes.py")
with col_b:
    st.info("Para agendar visita, use o Chat com um lead selecionado e peça: "
            f"`Agendar visita no imóvel {d['id']}`.")
