"""Gera arquivos JSON de seed (imóveis, vendedores, leads, agenda, RAG)."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEEDS = ROOT
random.seed(42)

BAIRROS_SP = [
    "Moema", "Pinheiros", "Vila Mariana", "Brooklin", "Itaim Bibi",
    "Perdizes", "Santana", "Tatuapé", "Mooca", "Lapa",
    "Campo Belo", "Vila Olímpia", "Jardins", "Consolação", "Liberdade",
]
BAIRROS_ABC = ["Santo André Centro", "São Bernardo Centro", "São Caetano Centro", "Diadema Centro"]
CIDADES = {
    **{b: "São Paulo" for b in BAIRROS_SP},
    **{b: b.split()[0] + " " + b.split()[1] if " " in b else b for b in BAIRROS_ABC},
}
# fix ABC cities
CIDADES["Santo André Centro"] = "Santo André"
CIDADES["São Bernardo Centro"] = "São Bernardo do Campo"
CIDADES["São Caetano Centro"] = "São Caetano do Sul"
CIDADES["Diadema Centro"] = "Diadema"

ALL_BAIRROS = BAIRROS_SP + BAIRROS_ABC

RES_TIPOS = ["apartamento", "casa", "cobertura", "kitnet"]
COM_TIPOS = ["escritorio", "loja", "galpao", "sala_comercial"]

AMEN_RES = ["piscina", "academia", "portaria 24h", "churrasqueira", "playground", "varanda", "elevador"]
AMEN_COM = ["recepção", "ar-condicionado", "gerador", "estacionamento", "fibra ótica", "copa", "acesso 24h"]


PHOTOS = {
    "apartamento": [
        "photo-1522708323590-d24dbb6b0267",
        "photo-1502672260266-1c1ef2d93688",
        "photo-1560448204-e02f11c3d0e2",
        "photo-1493809842364-78817add7ffb",
        "photo-1560185007-cde436f6a4d0",
    ],
    "casa": [
        "photo-1564013799919-ab600027ffc6",
        "photo-1570129477492-45c003edd2be",
        "photo-1568605114967-8130f3a36994",
        "photo-1600596542815-ffad4c1539a9",
        "photo-1600585154340-be6161a56a0c",
    ],
    "cobertura": [
        "photo-1600607687939-ce8a6c25118c",
        "photo-1600566753190-17f0baa2a6c3",
        "photo-1600210492486-724fe5c67fb0",
        "photo-1600607687644-c7171b42498f",
        "photo-1600585154526-990dced4db0d",
    ],
    "kitnet": [
        "photo-1554995207-c18c203602cb",
        "photo-1536376072261-38c75010e6c9",
        "photo-1522771739844-6a9f6d5f14af",
        "photo-1505691938895-1758d7feb511",
        "photo-1616594039964-ae9021a400a0",
    ],
    "escritorio": [
        "photo-1497366216548-37526070297c",
        "photo-1497366811353-6870744d04b2",
        "photo-1524758631624-e2822e304c36",
        "photo-1497366754035-f200968a6e72",
        "photo-1604328698692-f76ea9498e76",
    ],
    "loja": [
        "photo-1441986300917-64674bd600d8",
        "photo-1604719312566-8912e9227c6a",
        "photo-1555529669-e69e7aa0ba9a",
        "photo-1528698827591-e19ccd7bc23d",
        "photo-1472851294608-062f824d29cc",
    ],
    "galpao": [
        "photo-1586528116311-ad8dd3c8310d",
        "photo-1553413077-190dd305871c",
        "photo-1565610222536-ef125c59da2e",
        "photo-1587293852726-70cdb56c2866",
        "photo-1504328345606-18bbc8c9d7d1",
    ],
    "sala_comercial": [
        "photo-1497366412874-3415097a27e7",
        "photo-1497366754035-f200968a6e72",
        "photo-1631679706909-1844bbd07221",
        "photo-1524758631624-e2822e304c36",
        "photo-1604328698692-f76ea9498e76",
    ],
}


def images_for(tipo: str, index: int, n: int = 3) -> list[str]:
    pool = PHOTOS.get(tipo, PHOTOS["apartamento"])
    urls = []
    for offset in range(n):
        photo = pool[(index + offset) % len(pool)]
        urls.append(
            f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=800&h=600&q=80"
        )
    return urls


def gen_residential(n: int = 50) -> list[dict]:
    items = []
    for i in range(1, n + 1):
        pid = f"RES-{i:03d}"
        tipo = RES_TIPOS[(i - 1) % len(RES_TIPOS)]
        bairro = ALL_BAIRROS[(i - 1) % len(ALL_BAIRROS)]
        cidade = CIDADES[bairro]
        quartos = 1 if tipo == "kitnet" else random.randint(2, 4)
        area = random.randint(28, 55) if tipo == "kitnet" else random.randint(55, 280)
        base = 280_000 if tipo == "kitnet" else 450_000
        preco = base + area * random.randint(4500, 12000) + quartos * 80_000
        if tipo == "cobertura":
            preco = int(preco * 1.45)
        if tipo == "casa":
            preco = int(preco * 1.15)
        items.append({
            "id": pid,
            "titulo": f"{tipo.replace('_', ' ').title()} em {bairro}",
            "segmento": "residencial",
            "tipo": tipo,
            "bairro": bairro,
            "cidade": cidade,
            "preco": float(preco),
            "area_m2": float(area),
            "quartos": quartos,
            "vagas": random.randint(0, 3),
            "salas": None,
            "descricao": (
                f"Imóvel residencial fictício ({tipo}) no bairro {bairro}, {cidade}. "
                f"Área de {area} m², {quartos} quarto(s). Ideal para famílias ou investidores. "
                f"Código {pid}."
            ),
            "amenities": random.sample(AMEN_RES, k=random.randint(3, 5)),
            "image_urls": images_for(tipo, i),
            "lat": -23.55 + random.uniform(-0.12, 0.12),
            "lng": -46.63 + random.uniform(-0.15, 0.15),
        })
    return items


def gen_commercial(n: int = 50) -> list[dict]:
    items = []
    for i in range(1, n + 1):
        pid = f"COM-{i:03d}"
        tipo = COM_TIPOS[(i - 1) % len(COM_TIPOS)]
        bairro = ALL_BAIRROS[(i * 3) % len(ALL_BAIRROS)]
        cidade = CIDADES[bairro]
        salas = random.randint(1, 8) if tipo in ("escritorio", "sala_comercial") else None
        area = {
            "escritorio": random.randint(40, 350),
            "loja": random.randint(30, 200),
            "galpao": random.randint(200, 2000),
            "sala_comercial": random.randint(25, 120),
        }[tipo]
        base = {"escritorio": 5000, "loja": 7000, "galpao": 2500, "sala_comercial": 6000}[tipo]
        preco = area * base * random.uniform(0.9, 1.4)
        if tipo == "galpao":
            preco = area * random.randint(1800, 3500)
        items.append({
            "id": pid,
            "titulo": f"{tipo.replace('_', ' ').title()} em {bairro}",
            "segmento": "empresarial",
            "tipo": tipo,
            "bairro": bairro,
            "cidade": cidade,
            "preco": float(round(preco, 2)),
            "area_m2": float(area),
            "quartos": None,
            "vagas": random.randint(0, 20),
            "salas": salas,
            "descricao": (
                f"Imóvel empresarial fictício ({tipo}) em {bairro}, {cidade}. "
                f"Área útil de {area} m². Excelente para operação comercial/industrial. "
                f"Código {pid}."
            ),
            "amenities": random.sample(AMEN_COM, k=random.randint(3, 5)),
            "image_urls": images_for(tipo, i),
            "lat": -23.55 + random.uniform(-0.12, 0.12),
            "lng": -46.63 + random.uniform(-0.15, 0.15),
        })
    return items


def gen_sellers() -> list[dict]:
    return [
        {"id": "SEL-001", "nome": "Ana Souza", "email": "ana.souza@imobdemo.com", "telefone": "(11) 90000-1001", "especialidade": "residencial"},
        {"id": "SEL-002", "nome": "Bruno Lima", "email": "bruno.lima@imobdemo.com", "telefone": "(11) 90000-1002", "especialidade": "empresarial"},
        {"id": "SEL-003", "nome": "Carla Mendes", "email": "carla.mendes@imobdemo.com", "telefone": "(11) 90000-1003", "especialidade": "geral"},
        {"id": "SEL-004", "nome": "Diego Alves", "email": "diego.alves@imobdemo.com", "telefone": "(11) 90000-1004", "especialidade": "residencial"},
        {"id": "SEL-005", "nome": "Elena Costa", "email": "elena.costa@imobdemo.com", "telefone": "(11) 90000-1005", "especialidade": "empresarial"},
    ]


def gen_leads() -> list[dict]:
    now = datetime.utcnow()
    origens = ["google", "quinto_andar", "zap", "indicacao", "direto"]
    statuses = ["novo", "interessado", "negociacao", "comprado", "finalizado", "interessado"]
    leads = []
    names = [
        ("João Silva", "joao.silva@email.com", "(11) 91111-0001"),
        ("Maria Oliveira", "maria.oliveira@email.com", "(11) 91111-0002"),
        ("Pedro Santos", "pedro.santos@email.com", "(11) 91111-0003"),
        ("Juliana Rocha", "juliana.rocha@email.com", "(11) 91111-0004"),
        ("Rafael Nunes", "rafael.nunes@email.com", "(11) 91111-0005"),
        ("Fernanda Dias", "fernanda.dias@email.com", "(11) 91111-0006"),
        ("Lucas Pereira", "lucas.pereira@email.com", "(11) 91111-0007"),
        ("Patricia Gomes", "patricia.gomes@email.com", "(11) 91111-0008"),
        ("André Barbosa", "andre.barbosa@email.com", "(11) 91111-0009"),
        ("Camila Freitas", "camila.freitas@email.com", "(11) 91111-0010"),
        ("Thiago Martins", "thiago.martins@email.com", "(11) 91111-0011"),
        ("Beatriz Ramos", "beatriz.ramos@email.com", "(11) 91111-0012"),
    ]
    for i, (nome, email, tel) in enumerate(names, start=1):
        lid = f"LEAD-{i:03d}"
        status = statuses[(i - 1) % len(statuses)]
        # leads 10-12: inativos para demo de reengajamento
        if i >= 10:
            last = now - timedelta(days=5 + i % 3)
            status = "interessado"
            chat_finalizado = False
        elif status == "finalizado":
            last = now - timedelta(days=1)
            chat_finalizado = True
        else:
            last = now - timedelta(hours=i * 3)
            chat_finalizado = False
        bairro = ALL_BAIRROS[i % len(ALL_BAIRROS)]
        seg = "residencial" if i % 2 else "empresarial"
        buscas = [
            {"bairro": bairro, "segmento": seg, "preco_max": 900000 + i * 50000, "em": (last - timedelta(days=1)).isoformat()},
            {"bairro": ALL_BAIRROS[(i + 2) % len(ALL_BAIRROS)], "segmento": seg, "preco_max": 1200000, "em": last.isoformat()},
        ]
        leads.append({
            "id": lid,
            "nome": nome,
            "email": email,
            "telefone": tel,
            "origem": origens[(i - 1) % len(origens)],
            "status": status,
            "chat_finalizado": chat_finalizado,
            "preferencias_resumo": f"Interesse em {seg} próximo a {bairro}.",
            "ultimas_buscas": buscas,
            "seller_id": f"SEL-{(i % 5) + 1:03d}",
            "created_at": (now - timedelta(days=20 - i)).isoformat(),
            "last_interaction_at": last.isoformat(),
            "last_contact_at": (last - timedelta(days=2)).isoformat() if i >= 10 else None,
        })
    return leads


def gen_appointments() -> list[dict]:
    now = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    items = []
    for i in range(1, 16):
        start = now + timedelta(days=(i % 14) - 3, hours=(i % 4))
        end = start + timedelta(hours=1)
        tipo = "visita" if i % 2 else "consulta"
        prop = f"RES-{(i % 50) + 1:03d}" if tipo == "visita" and i % 3 else (
            f"COM-{(i % 50) + 1:03d}" if tipo == "visita" else None
        )
        status = ["agendado", "realizado", "no_show", "agendado"][i % 4]
        items.append({
            "id": f"APT-{i:03d}",
            "lead_id": f"LEAD-{(i % 12) + 1:03d}",
            "seller_id": f"SEL-{(i % 5) + 1:03d}",
            "property_id": prop,
            "tipo": tipo,
            "titulo": f"{tipo.title()} #{i}",
            "inicio": start.isoformat(),
            "fim": end.isoformat(),
            "status": status,
            "notas": "Agendamento fictício para demonstração.",
            "email_enviado": status != "agendado",
        })
    return items


def gen_market_docs() -> list[dict]:
    docs = []
    for bairro in BAIRROS_SP[:10]:
        docs.append({
            "id": f"MKT-{bairro.replace(' ', '-')}",
            "tipo": "mercado",
            "titulo": f"Panorama de mercado — {bairro}",
            "conteudo": (
                f"O bairro {bairro} em São Paulo apresenta demanda estável por imóveis residenciais "
                f"de 2 e 3 dormitórios. Preços médios fictícios variam conforme proximidade ao metrô. "
                f"Para o segmento empresarial, salas comerciais de 40–80 m² têm boa liquidez. "
                f"Investidores devem observar vacância e ticket médio. Documento seed para RAG."
            ),
        })
    docs.append({
        "id": "MKT-ABC",
        "tipo": "mercado",
        "titulo": "Mercado ABC Paulista",
        "conteudo": (
            "A região do ABC concentra demanda por galpões logísticos e casas familiares. "
            "Valores fictícios por m² são tipicamente inferiores aos de Moema e Itaim. "
            "Útil para comparar residencial vs empresarial no RAG."
        ),
    })
    return docs


def gen_legal_docs() -> list[dict]:
    return [
        {
            "id": "LEG-001",
            "tipo": "juridico",
            "titulo": "Checklist documentação compra e venda",
            "conteudo": (
                "Documentos fictícios usuais: RG/CPF comprador e vendedor, matrícula atualizada, "
                "certidões negativas, IPTU quitado, declaração de quitação de condomínio. "
                "Escritura em cartório e registro na matrícula concluem a transferência."
            ),
        },
        {
            "id": "LEG-002",
            "tipo": "juridico",
            "titulo": "Cláusulas comuns de contrato de locação comercial",
            "conteudo": (
                "Contratos comerciais fictícios costumam prever prazo mínimo, reajuste anual, "
                "caição ou seguro-fiança, uso permitido do imóvel e responsabilidade por reformas. "
                "Rescisão antecipada pode gerar multa proporcional."
            ),
        },
        {
            "id": "LEG-003",
            "tipo": "juridico",
            "titulo": "FAQ ITBI e registro",
            "conteudo": (
                "ITBI é tributo municipal sobre transmissão onerosa. Alíquota fictícia típica "
                "em SP é discutida em percentuais locais. O registro no Cartório de Imóveis "
                "é o que transfere a propriedade perante terceiros."
            ),
        },
    ]


def gen_finance_rules() -> dict:
    return {
        "taxa_anual_percent": 10.5,
        "entrada_minima_percent": 20,
        "prazo_max_meses": 360,
        "prazo_opcoes": [120, 180, 240, 360],
        "sistema": "PRICE",
        "observacao": (
            "Regras fictícias para simulação acadêmica. Não representam oferta bancária real. "
            "Parcela estimada pelo sistema Price: PMT = PV * i*(1+i)^n / ((1+i)^n - 1)."
        ),
    }


def dump(name: str, data) -> None:
    path = SEEDS / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path.name} ({len(data) if hasattr(data, '__len__') else 'obj'})")


def main() -> None:
    dump("properties_residential.json", gen_residential(50))
    dump("properties_commercial.json", gen_commercial(50))
    dump("sellers.json", gen_sellers())
    dump("leads.json", gen_leads())
    dump("appointments.json", gen_appointments())
    dump("market_docs.json", gen_market_docs())
    dump("legal_docs.json", gen_legal_docs())
    dump("finance_rules.json", gen_finance_rules())


if __name__ == "__main__":
    main()
