"""A mesma consulta exposta como ferramenta (tool calling), para usar com agentes."""
from langchain_core.tools import tool

from app import db, guardrails


@tool
def run_sql(query: str) -> str:
    """Executa um SELECT no banco do CRM e devolve as linhas. Só leitura."""
    try:
        seguro = guardrails.validar(query, db.tabelas())
        r = db.executar(seguro)
    except Exception as e:
        return f"ERRO: {e}"
    return f"colunas: {r['colunas']}\n" + "\n".join(str(l) for l in r["linhas"])
