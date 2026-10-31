"""Uso:
    python -m app.cli "Quantos clientes ativos temos em Madrid?"
    python -m app.cli --aprovar          # modo interativo com aprovação humana do SQL
"""
import argparse
import uuid

from langgraph.types import Command

from app import observability
from app.graph import construir_grafo


def perguntar(grafo, pergunta: str, aprovar: bool, mostrar_sql: bool) -> None:
    config = {"callbacks": observability.callbacks(), "configurable": {"thread_id": str(uuid.uuid4())}}
    estado = grafo.invoke({"pergunta": pergunta}, config=config)
    while aprovar and "__interrupt__" in estado:
        pedido = estado["__interrupt__"][0].value
        print(f"\nSQL proposto:\n{pedido['sql']}")
        estado = grafo.invoke(Command(resume=input(pedido["mensagem"] + " ")), config=config)
    if mostrar_sql and estado.get("sql"):
        print(f"\n[SQL, tentativa {estado.get('tentativas')}]\n{estado['sql']}")
    print(f"\n{estado['resposta']}\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Assistente text-to-SQL do time de CRM")
    p.add_argument("pergunta", nargs="?", help="pergunta em linguagem natural (sem ela, abre o modo interativo)")
    p.add_argument("--aprovar", action="store_true", help="pede aprovação humana antes de executar o SQL")
    p.add_argument("--sql", action="store_true", help="mostra o SQL gerado")
    args = p.parse_args()

    grafo = construir_grafo(aprovacao_humana=args.aprovar)
    try:
        if args.pergunta:
            perguntar(grafo, args.pergunta, args.aprovar, args.sql)
            return
        print("Pergunte sobre os dados do CRM (Ctrl+C para sair).")
        while True:
            pergunta = input("> ").strip()
            if pergunta:
                perguntar(grafo, pergunta, args.aprovar, args.sql)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        if (lf := observability.cliente()) is not None:
            lf.flush()


if __name__ == "__main__":
    main()
