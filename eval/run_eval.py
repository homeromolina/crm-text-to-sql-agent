"""Avaliação offline do agente. Rode a cada mudança de prompt, modelo ou RAG antes de subir.

    python -m eval.run_eval

Métricas:
  - execution_accuracy: o resultado do SQL gerado bate com o do SQL de referência
  - sql_valido: o agente chegou num SQL que passou na validação e rodou
  - corrigido_na_retentativa: precisou de mais de uma tentativa e acertou
  - recall_tabelas: o RAG recuperou todas as tabelas que a referência usa
  - latência p50 / p95 e tentativas médias
Com o Langfuse configurado, cada pergunta vira um trace com essas notas (scores).
"""
import argparse
import json
import statistics
import time
import uuid
from contextlib import nullcontext
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

from app import db, guardrails, observability
from app.graph import construir_grafo

PASTA = Path(__file__).parent


def normalizar(resultado: dict) -> list[tuple]:
    """Compara só os valores, sem nome de coluna nem ordem das linhas."""
    arred = lambda v: round(v, 2) if isinstance(v, float) else v
    return sorted((tuple(arred(v) for v in l) for l in resultado["linhas"]), key=repr)


def tabelas_do_sql(sql: str) -> set[str]:
    arvore = sqlglot.parse_one(sql, read="sqlite")
    ctes = {c.alias_or_name for c in arvore.find_all(exp.CTE)}
    return {t.name for t in arvore.find_all(exp.Table)} - ctes


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p * (len(ordenados) - 1)))]


def avaliar(grafo, itens: list[dict]) -> dict:
    lf = observability.cliente()
    linhas = []
    for i, item in enumerate(itens, 1):
        esperado = normalizar(db.executar(guardrails.validar(item["sql"], db.tabelas())))
        span = lf.start_as_current_observation(name="eval-text-to-sql", input=item["pergunta"]) if lf else nullcontext()
        with span:
            inicio = time.perf_counter()
            estado = grafo.invoke({"pergunta": item["pergunta"]},
                                  config={"callbacks": observability.callbacks(),
                                          "configurable": {"thread_id": str(uuid.uuid4())}})
            latencia = time.perf_counter() - inicio
            valido = estado.get("resultado") is not None
            acertou = valido and normalizar(estado["resultado"]) == esperado
            recall = tabelas_do_sql(item["sql"]) <= set(estado.get("tabelas_recuperadas", []))
            if lf:
                lf.score_current_trace(name="execution_accuracy", value=float(acertou))
                lf.score_current_trace(name="sql_valido", value=float(valido))
                lf.score_current_trace(name="recall_tabelas", value=float(recall))
        linhas.append({"pergunta": item["pergunta"], "acertou": acertou, "valido": valido,
                       "tentativas": estado.get("tentativas", 0), "recall_tabelas": recall,
                       "latencia_s": round(latencia, 2), "sql": estado.get("sql")})
        print(f"[{i:>2}/{len(itens)}] {'✅' if acertou else '❌'} {item['pergunta']}")
    if lf:
        lf.flush()

    n = len(linhas)
    lat = [l["latencia_s"] for l in linhas]
    retentativas = [l for l in linhas if l["tentativas"] > 1]
    return {
        "itens": n,
        "execution_accuracy": sum(l["acertou"] for l in linhas) / n,
        "sql_valido": sum(l["valido"] for l in linhas) / n,
        "corrigido_na_retentativa": (sum(l["acertou"] for l in retentativas) / len(retentativas)
                                     if retentativas else None),
        "recall_tabelas": sum(l["recall_tabelas"] for l in linhas) / n,
        "tentativas_medias": statistics.mean(l["tentativas"] for l in linhas),
        "latencia_p50_s": percentil(lat, 0.5),
        "latencia_p95_s": percentil(lat, 0.95),
        "detalhes": linhas,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=PASTA / "dataset.yaml", type=Path)
    p.add_argument("--saida", default=PASTA / "resultado.json", type=Path)
    args = p.parse_args()

    itens = yaml.safe_load(args.dataset.read_text(encoding="utf-8"))
    relatorio = avaliar(construir_grafo(), itens)
    args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    resumo = {k: v for k, v in relatorio.items() if k != "detalhes"}
    print("\n" + "\n".join(f"{k:>26}: {v:.2f}" if isinstance(v, float) else f"{k:>26}: {v}"
                           for k, v in resumo.items()))
    print(f"\nRelatório completo em {args.saida}")


if __name__ == "__main__":
    main()
