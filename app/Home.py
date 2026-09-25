"""Home — apresentação promocional do software."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHOTS = ROOT / "assets" / "screenshots"

st.set_page_config(
    page_title="Imobiliária — atendimento",
    page_icon="🏠",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.6rem; max-width: 1120px; }
    [data-testid="stImage"] img {
        border-radius: 18px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
    }
    .kicker {
        color: #c4b5fd;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 0.78rem;
        margin-bottom: 0.4rem;
    }
    .lead { font-size: 1.12rem; line-height: 1.55; color: #d1d5db; }
    .pill, .channel {
        background: #1c1f2a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 0.95rem 1rem;
    }
    .pill { min-height: 92px; }
    .pill strong { display: block; margin-bottom: 0.2rem; color: #f3f4f6; }
    .shot-title { font-weight: 700; font-size: 1.05rem; margin: 0.15rem 0 0.15rem 0; color: #f3f4f6; }
    .channel { min-height: 132px; }
    .channel h3 { margin: 0 0 0.35rem 0; font-size: 1rem; color: #f3f4f6; }
    .channel p { margin: 0; color: #d1d5db; font-size: 0.92rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1.05, 1], gap="large")
with left:
    st.markdown('<p class="kicker">Atendimento imobiliário</p>', unsafe_allow_html=True)
    st.title("Do primeiro oi até a visita marcada")
    st.markdown(
        '<p class="lead">Converse com o cliente, mostre o imóvel, guarde o contato '
        "e acompanhe o que a equipe precisa fazer em seguida. Tudo no mesmo lugar, "
        "no canal em que a pessoa chegou.</p>",
        unsafe_allow_html=True,
    )
    a, b = st.columns(2)
    with a:
        st.markdown(
            '<div class="pill"><strong>Conversa contínua</strong>Um histórico por cliente, como numa conversa de aplicativo.</div>',
            unsafe_allow_html=True,
        )
    with b:
        st.markdown(
            '<div class="pill"><strong>Imóvel na hora</strong>Casas, apartamentos, salas e galpões com foto, preço e quartos.</div>',
            unsafe_allow_html=True,
        )
    st.write("")
    c, d = st.columns(2)
    with c:
        st.markdown(
            '<div class="pill"><strong>Visita na agenda</strong>O horário fica no calendário e o convite sai por e-mail.</div>',
            unsafe_allow_html=True,
        )
    with d:
        st.markdown(
            '<div class="pill"><strong>Time no mesmo ritmo</strong>Origem, estágio do lead e bairros mais pedidos, lado a lado.</div>',
            unsafe_allow_html=True,
        )

with right:
    chat = SHOTS / "02_chat_agentes.png"
    if chat.exists():
        st.image(str(chat), use_container_width=True)
        st.caption("Atendimento em andamento, com o histórico ao lado.")

st.write("")
st.subheader("O software em ação")
st.markdown(
    "Cada tela abaixo é o próprio sistema: a conversa, o catálogo, a ficha, a carteira de clientes, a agenda e o panorama do período."
)

shots = [
    ("03_catalogo.png", "Mostre o imóvel certo", "Filtre por tipo, bairro e preço e abra as opções com foto."),
    ("04_detalhe_imovel.png", "Abra a ficha", "Fotos, localização e características para apresentar ao cliente."),
    ("05_leads_crm.png", "Saiba quem entrou", "Nome, contato, origem e em que ponto da compra a pessoa está."),
    ("06_calendario.png", "Organize as visitas", "O mês da equipe, com filtro por vendedor."),
]
if (SHOTS / "07_relatorios.png").exists():
    shots.append(
        (
            "07_relatorios.png",
            "Veja onde insistir",
            "O período mostra o funil e os bairros que mais geram procura.",
        )
    )

for i in range(0, len(shots), 2):
    cols = st.columns(2, gap="large")
    for col, (filename, title, text) in zip(cols, shots[i : i + 2]):
        path = SHOTS / filename
        with col:
            if path.exists():
                st.image(str(path), use_container_width=True)
            st.markdown(f'<p class="shot-title">{title}</p>', unsafe_allow_html=True)
            st.caption(text)

st.write("")
st.subheader("O cliente chega por onde já está")
st.markdown(
    "Site, aplicativo, WhatsApp ou portal. Na demonstração, a origem é escolhida no atendimento "
    "e passa a aparecer na carteira de clientes."
)
channels = [
    ("Site", "Quem preenche o contato no site entra na mesma conversa."),
    ("App", "O pedido feito no aplicativo segue o mesmo atendimento."),
    ("WhatsApp", "A mensagem vira conversa. Nome e e-mail são pedidos ali mesmo."),
    ("QuintoAndar", "O lead do portal chega identificado e segue para a visita."),
    ("ZAP", "O interesse no anúncio abre o mesmo fluxo de busca e agenda."),
    ("Coelho da Fonseca", "O atendimento de alto padrão usa a mesma carteira e a mesma agenda."),
]
row1, row2 = channels[:3], channels[3:]
for group in (row1, row2):
    cols = st.columns(3, gap="medium")
    for col, (title, text) in zip(cols, group):
        with col:
            st.markdown(
                f'<div class="channel"><h3>{title}</h3><p>{text}</p></div>',
                unsafe_allow_html=True,
            )
    st.write("")

st.caption("O detalhe de funcionamento, benefícios operacionais e crescimento está no notebook de pitch técnico.")
