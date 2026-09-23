# Hackaton Agente Imobiliário — Projeto Final FIAP

Sistema **multiagente** de imobiliária com **LangGraph + LangChain**, **RAG (ChromaDB)**, **Llama 3.1 8B via Ollama** (origem Hugging Face: [`meta-llama/Meta-Llama-3.1-8B-Instruct`](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)), interface **Streamlit** e notebook de entrega.

## Funcionalidades

- Chat multiagente: Supervisor, Busca, Avaliação, Jurídico, Financiamento, Consultor de Vendas, CRM, Síntese
- RAG seedado (mercado, jurídico, financiamento e fichas de imóveis)
- **100 imóveis fictícios**: 50 residenciais + 50 empresariais, com imagens fake
- CRM de leads: origem (Google, QuintoAndar, ZAP…), preferências e resumo de buscas
- Reengajamento automático de leads inativos (chat não finalizado)
- Agenda de visitas/consultas + calendário + e-mail com arquivo `.ics` (mock ou SMTP)
- Relatórios dia/semana/mês e por vendedor (funil + narrativa LLM)

## Pré-requisitos

1. Python 3.11+
2. [Ollama](https://ollama.com/) instalado e rodando

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

## Setup

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env

python scripts/seed_and_ingest.py
streamlit run app/Home.py
```

## Estrutura

```
app/                  # Streamlit (Home + páginas)
src/
  graph/              # LangGraph (agentes)
  rag/                # Chroma ingest/retriever
  db/                 # SQLite SQLAlchemy
  tools/              # busca, financiamento, CRM, agenda
  services/           # e-mail/ICS, reengajamento, relatórios
  seeds/              # JSON gerados + generate_seeds.py
notebooks/            # relatorio_final.ipynb
scripts/              # seed_and_ingest.py
```

## Modelo LLM

| Escolha | Detalhe |
|---------|---------|
| Padrão | `llama3.1:8b` ← HF `Meta-Llama-3.1-8B-Instruct` |
| Fallback | `llama3.2:3b` (máquinas mais leves) |
| Embeddings | `nomic-embed-text` |

## E-mail

- `EMAIL_MODE=mock` (padrão): grava `.eml` e `.ics` em `data/outbox/`
- `EMAIL_MODE=smtp`: usa `SMTP_*` do `.env`

## Relatório acadêmico

Abra `notebooks/relatorio_final.ipynb` e execute as células (com seeds já carregados). Inclua prints da UI em `assets/screenshots/`.

## Observação

Todos os dados são **fictícios** (seeds), para fins acadêmicos. Não há integração real com QuintoAndar, ZAP ou Google Ads.

Sem Ollama, o sistema ainda sobe: busca no catálogo, CRM, agenda, e-mail mock e RAG por **fallback textual**. Com Ollama + embeddings, o RAG usa Chroma com `nomic-embed-text` e as respostas passam pelo Llama.
