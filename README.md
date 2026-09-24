# Hackaton Agente Imobiliário — Projeto Final FIAP

Sistema **multiagente** de imobiliária com **LangGraph + LangChain**, **RAG (ChromaDB)**, **Llama 3.1 8B via Ollama** (origem Hugging Face: [`meta-llama/Meta-Llama-3.1-8B-Instruct`](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)), interface **Streamlit** e notebook de entrega.

## Funcionalidades

- Chat multiagente: Supervisor, Busca, Avaliação, Jurídico, Financiamento, Consultor de Vendas, CRM, Síntese
- **Hybrid RAG** (BM25 + vetorial Chroma + Reciprocal Rank Fusion), com filtros de bairro, preço e quartos
- **100 imóveis fictícios**: 50 residenciais + 50 empresariais, com imagens fake
- CRM de leads: origem (Google, QuintoAndar, ZAP…), preferências e resumo de buscas
- Reengajamento automático de leads inativos (chat não finalizado)
- Agenda de visitas/consultas + calendário + e-mail com arquivo `.ics` (mock ou SMTP)
- Relatórios dia/semana/mês e por vendedor (funil + narrativa LLM)

## Instalar e executar (Windows)

O app usa **Ollama** como servidor local do LLM. O modelo de chat é o **Llama 3.1 8B Instruct**, o mesmo card do Hugging Face [`meta-llama/Meta-Llama-3.1-8B-Instruct`](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct). Os embeddings do RAG são o `nomic-embed-text` (não é Llama).

### 1. Pré-requisitos

- Python 3.11 ou superior
- [Ollama para Windows](https://ollama.com/download) instalado (ele sobe o serviço em `http://localhost:11434`)
- Conta no [Hugging Face](https://huggingface.co/) (só no caminho B, abaixo)
- Cerca de 6–8 GB livres em disco para o modelo quantizado (Q4)

Abra um PowerShell na pasta do projeto:

```powershell
cd "C:\Users\stefa\Documents\Cursos\FIAP Pós\Hackaton_Agente_Imobiliario"
```

### 2. Baixar o Llama 3.1 do Hugging Face e registrar no Ollama

O repositório oficial da Meta é **gated** (precisa aceitar a licença). Para este projeto, baixe o GGUF quantizado (Q4_K_M), que o Ollama consegue carregar.

1. No Hugging Face, aceite a licença em [meta-llama/Meta-Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct) se for usar o repositório oficial.
2. Crie um token em [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (permissão de leitura).
3. No PowerShell do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -U huggingface_hub

# login (cole o token quando pedir)
hf auth login

# GGUF Q4 do Llama 3.1 8B Instruct (baseado no card oficial da Meta)
New-Item -ItemType Directory -Force -Path models | Out-Null
hf download bartowski/Meta-Llama-3.1-8B-Instruct-GGUF `
  Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf `
  --local-dir models
```

4. Crie o modelo no Ollama a partir do arquivo baixado. Salve este conteúdo em `Modelfile` na raiz do projeto (já versionado) e rode:

```powershell
ollama create llama3.1-hf -f Modelfile
ollama pull nomic-embed-text
ollama list
```

`ollama list` deve mostrar `llama3.1-hf` e `nomic-embed-text`.

**Atalho sem Hugging Face:** se preferir o pacote oficial do Ollama (mesma família Llama 3.1 8B), use `ollama pull llama3.1:8b` e deixe `OLLAMA_MODEL=llama3.1:8b` no `.env`.

### 3. Ambiente Python e dados

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Confira no `.env`:

```env
OLLAMA_MODEL=llama3.1-hf
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
EMAIL_MODE=mock
```

Se usou o atalho `ollama pull llama3.1:8b`, troque `OLLAMA_MODEL` para `llama3.1:8b`.

Carregue seeds (100 imóveis, leads, agenda) e indexe o RAG no Chroma:

```powershell
python scripts/seed_and_ingest.py
```

A indexação chama o Ollama para gerar embeddings. Se aparecer aviso de conexão, confira se o app Ollama está aberto e se `nomic-embed-text` foi baixado, e rode o script de novo.

### 4. Subir o app

```powershell
streamlit run app/Home.py
```

O navegador abre em `http://localhost:8501`. Páginas: Chat, Catálogo, Detalhe do imóvel, Leads, Calendário e Relatórios.

### 5. Notebook de entrega

Com o venv ativo e os seeds carregados:

```powershell
jupyter notebook notebooks/relatorio_final.ipynb
```

### Problemas comuns

| Sintoma | O que fazer |
|---------|-------------|
| `ollama` não é reconhecido | Feche e abra o terminal depois de instalar o Ollama, ou reinicie o Windows |
| `Failed to connect to Ollama` | Abra o aplicativo Ollama e aguarde o ícone na bandeja |
| Modelo não encontrado | `ollama list` e alinhe o nome com `OLLAMA_MODEL` no `.env` |
| RAG sem vetores | Rode de novo `python scripts/seed_and_ingest.py` com o Ollama no ar |
| Hugging Face 401/403 | `hf auth login` com token válido; no repo oficial, aceite a licença Llama |

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
| Padrão (HF) | `llama3.1-hf` ← GGUF de `Meta-Llama-3.1-8B-Instruct` |
| Atalho Ollama | `llama3.1:8b` (`ollama pull`) |
| Fallback leve | `llama3.2:3b` |
| Embeddings | `nomic-embed-text` |

## E-mail

- `EMAIL_MODE=mock` (padrão): grava `.eml` e `.ics` em `data/outbox/`
- `EMAIL_MODE=smtp`: usa `SMTP_*` do `.env`

## Relatório acadêmico

Abra `notebooks/relatorio_final.ipynb` e execute as células (com seeds já carregados). Inclua prints da UI em `assets/screenshots/`.

## Observação

Todos os dados são **fictícios** (seeds), para fins acadêmicos. Não há integração real com QuintoAndar, ZAP ou Google Ads.

Sem Ollama, o sistema ainda sobe: busca no catálogo, CRM, agenda, e-mail mock e braço **BM25** do hybrid search. Com Ollama + embeddings, o hybrid funde BM25 + Chroma (`nomic-embed-text`) via RRF, e as respostas passam pelo Llama.

### Hybrid search (resumo)

| Braço | Forte em |
|-------|----------|
| BM25 | Bairro, “3 quartos”, códigos `RES-001` |
| Vetorial | Semântica (“família”, “perto do metrô”) |
| Filtros | `bairro`, `preco_min/max`, `quartos_min/max`, `segmento`, `tipo` |
| Fusão | Reciprocal Rank Fusion (RRF) |
