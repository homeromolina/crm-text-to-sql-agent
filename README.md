# Assistente Text-to-SQL com RAG para o time de CRM

Código do vídeo **"AI Engineer na prática: LangChain, LangGraph, Langfuse e Text-to-SQL com RAG"** do [@eurodata.es](https://www.instagram.com/eurodata.es).

O time de CRM pergunta em português ("Quantos clientes de Madrid compraram mais de 2 vezes nos últimos 90 dias?"), o agente busca o contexto certo, gera o SQL, valida, executa com segurança e responde em português.

```
START → buscar_contexto → gerar_sql → validar → [aprovar] → executar → explicar → END
                              ↑            │                     │
                              └── erro ────┴──────── erro ───────┘   (máx. 3 tentativas)
        SQL perigoso ou tentativas esgotadas → desistir → END
```

## O que tem aqui

| Parte do vídeo | Onde está |
|---|---|
| RAG com esquema, glossário e exemplos | [`app/rag.py`](app/rag.py), [`knowledge/`](knowledge) |
| Chain do LangChain (`prompt \| llm \| parser`) | [`app/graph.py`](app/graph.py), [`exemplos/rag_chain.py`](exemplos/rag_chain.py) |
| Tool calling (`@tool run_sql`) | [`app/tools.py`](app/tools.py), [`exemplos/tool_calling.py`](exemplos/tool_calling.py) |
| Grafo do LangGraph com loop de correção | [`app/graph.py`](app/graph.py) |
| Humano no loop e checkpoints | `--aprovar` no CLI (`interrupt` + `InMemorySaver`) |
| Guardrails: só leitura, bloqueio de DELETE/UPDATE, limite de linhas e tempo, máscara de dados pessoais | [`app/guardrails.py`](app/guardrails.py), [`app/db.py`](app/db.py) |
| Observabilidade com Langfuse (self-hosted) | [`app/observability.py`](app/observability.py), [`docker-compose.yml`](docker-compose.yml) |
| Métricas: execution accuracy, SQL válido, recall de tabelas, p95 | [`eval/run_eval.py`](eval/run_eval.py), [`eval/dataset.yaml`](eval/dataset.yaml) |

## 100% open source

Por padrão tudo roda na sua máquina, sem conta e sem chave de API:

| Peça | O que usa | Licença |
|---|---|---|
| Modelo | `qwen2.5:7b` no [Ollama](https://ollama.com) | Apache-2.0 |
| Orquestração | LangChain + LangGraph | MIT |
| Observabilidade | [Langfuse](https://langfuse.com) self-hosted (`docker-compose.yml`) | MIT |
| Embeddings | locais (hashing), ou `ollama:nomic-embed-text` | — / Apache-2.0 |
| Banco | SQLite | domínio público |

Por que Langfuse e não LangSmith: o LangSmith é uma plataforma fechada (só o SDK é aberto) e rodar ele no seu servidor exige o plano Enterprise. O Langfuse é MIT e sobe com um `docker compose`.

## Como rodar

Precisa de Python 3.11+, [Ollama](https://ollama.com) e Docker.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # já vem configurado pro modo local
python data/seed.py           # cria data/crm.db com dados fictícios

ollama pull qwen2.5:7b        # o modelo (uns 4,7 GB)
docker compose up -d          # Langfuse em http://localhost:3000 (login e chaves no .env)
```

Perguntar:

```bash
python -m app.cli "Quantos clientes ativos temos em Madrid?" --sql
python -m app.cli --aprovar   # modo interativo, pede sua aprovação antes de executar cada SQL
```

Avaliar (rode a cada mudança de prompt, modelo ou RAG antes de subir):

```bash
python -m eval.run_eval
```

Testes (usam um modelo falso, não gastam nada):

```bash
pytest
```

## Trocar de modelo

Tudo passa por `init_chat_model`, então trocar é uma linha no `.env`:

```bash
LLM_MODEL=ollama:qwen2.5:7b             # padrão, local e aberto
LLM_MODEL=ollama:qwen3                  # outro modelo aberto do Ollama
LLM_MODEL=anthropic:claude-sonnet-5-5   # API fechada: pip install langchain-anthropic
LLM_MODEL=openai:gpt-5                  # API fechada: pip install langchain-openai
```

## Langfuse

O `docker compose up -d` sobe o Langfuse local (web, worker, Postgres, ClickHouse, Redis e MinIO) e já cria a organização, o projeto e as chaves do `.env`. Entre em http://localhost:3000 com o e-mail e a senha de `LANGFUSE_INIT_USER_*`. A partir daí cada pergunta vira um trace com cada nó do grafo, os prompts, o tempo e os tokens, e o `eval` grava as notas `execution_accuracy`, `sql_valido` e `recall_tabelas` em cada trace. Sem as chaves, tudo funciona igual, só sem os traces.

As senhas do `.env.example` e do `docker-compose.yml` são para uso local. Se for expor o Langfuse fora da sua máquina, troque todas as marcadas com `CHANGEME`. Para desligar: `docker compose down` (os dados ficam nos volumes).

## Adaptar pro seu banco

1. Troque `app/db.py` pela conexão do seu banco, **com um usuário só de leitura**.
2. Descreva suas tabelas em `knowledge/schema.yaml` e as regras do negócio em `knowledge/glossario.yaml`.
3. Coloque perguntas reais com o SQL validado em `knowledge/exemplos.yaml` (few-shot) e em `eval/dataset.yaml` (avaliação), sem repetir as mesmas.
4. Ajuste o dialeto no prompt (`app/prompts.py`) e no `sqlglot` (`read="sqlite"` em `app/guardrails.py`).
5. Com muitas tabelas, troque os embeddings locais por um modelo de verdade (`EMBEDDINGS_MODEL`) e o `InMemoryVectorStore` por um banco vetorial (pgvector, Qdrant...).

## Observações

- Os dados de `data/crm.db` são fictícios e gerados com semente fixa.
- O banco do exemplo é SQLite, então o SQL usa `date('now', '-90 days')` em vez do `INTERVAL '90 days'` do Postgres mostrado no vídeo.
- Os embeddings locais (hashing) existem só pra rodar sem API. Para produção, use um modelo de embeddings.
- Os guardrails são uma camada a mais, não substituem permissões no banco. Use sempre um usuário só de leitura.
