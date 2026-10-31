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
| Observabilidade com Langfuse | [`app/observability.py`](app/observability.py) |
| Métricas: execution accuracy, SQL válido, recall de tabelas, p95 | [`eval/run_eval.py`](eval/run_eval.py), [`eval/dataset.yaml`](eval/dataset.yaml) |

## Como rodar

Precisa de Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # coloque sua chave do provedor do modelo
python data/seed.py           # cria data/crm.db com dados fictícios
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
LLM_MODEL=anthropic:claude-sonnet-5-5   # pip install langchain-anthropic
LLM_MODEL=openai:gpt-5                  # pip install langchain-openai
LLM_MODEL=ollama:qwen3                  # pip install langchain-ollama (local)
```

## Langfuse

Crie um projeto no [Langfuse](https://langfuse.com) (cloud ou self-hosted) e preencha `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` e `LANGFUSE_BASE_URL` no `.env`. A partir daí cada pergunta vira um trace com cada nó do grafo, os prompts, o tempo e os tokens, e o `eval` grava as notas `execution_accuracy`, `sql_valido` e `recall_tabelas` em cada trace. Sem as chaves, tudo funciona igual, só sem os traces.

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
