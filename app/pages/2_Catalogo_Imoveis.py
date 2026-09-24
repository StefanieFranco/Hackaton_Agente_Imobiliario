"""Catálogo de imóveis."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import repository as repo
from src.db.models import init_db

st.set_page_config(page_title="Catálogo", layout="wide")
init_db()

st.title("Catálogo de Imóveis")

c1, c2, c3, c4 = st.columns(4)
with c1:
    segmento = st.selectbox("Segmento", ["Todos", "residencial", "empresarial"])
with c2:
    tipo = st.text_input("Tipo (opcional)", "")
with c3:
    bairro = st.text_input("Bairro (opcional)", "")
with c4:
    preco_max = st.number_input("Preço máximo", min_value=0, value=0, step=50000)

props = repo.list_properties(
    segmento=None if segmento == "Todos" else segmento,
    tipo=tipo or None,
    bairro=bairro or None,
    preco_max=preco_max or None,
    limit=100,
)

st.caption(f"{len(props)} imóveis encontrados")

cols = st.columns(3)
for i, p in enumerate(props):
    d = repo.property_to_dict(p)
    with cols[i % 3]:
        images = d.get("image_urls") or []
        if images:
            st.image(images[0], use_container_width=True)
        st.subheader(d["titulo"])
        st.write(f"**{d['id']}** · {d['bairro']} · {d['segmento']}")
        st.write(f"R$ {d['preco']:,.0f} · {d['area_m2']} m²")
        if d.get("quartos"):
            st.write(f"{d['quartos']} quarto(s)")
        if st.button("Ver detalhes", key=f"btn_{d['id']}"):
            st.session_state["selected_property_id"] = d["id"]
            st.switch_page("pages/3_Detalhe_Imovel.py")
