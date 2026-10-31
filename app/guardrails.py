"""Validação do SQL gerado pelo modelo ANTES de ir pro banco. Nunca execute às cegas."""
import sqlglot
from sqlglot import exp

from app import config

PROIBIDOS = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
             exp.Command, exp.Merge, exp.TruncateTable, exp.Pragma, exp.Attach, exp.Detach)


class SQLInvalido(Exception):
    """Erro de sintaxe ou de referência: o gerador pode corrigir e tentar de novo."""


class SQLBloqueado(Exception):
    """Violação de segurança: não adianta tentar de novo, a pergunta é recusada."""


def validar(sql: str, tabelas_permitidas: set[str], max_linhas: int | None = None) -> str:
    max_linhas = max_linhas or config.MAX_LINHAS
    try:
        comandos = [c for c in sqlglot.parse(sql, read="sqlite") if c is not None]
    except sqlglot.errors.ParseError as e:
        raise SQLInvalido(f"Erro de sintaxe: {e}") from e
    if len(comandos) != 1:
        raise SQLBloqueado("Só é permitido um comando por consulta.")
    arvore = comandos[0]

    if any(isinstance(n, PROIBIDOS) for n in arvore.walk()):
        raise SQLBloqueado("Só consultas de leitura (SELECT) são permitidas.")
    if not isinstance(arvore, exp.Query):
        raise SQLBloqueado("Só consultas de leitura (SELECT) são permitidas.")

    ctes = {c.alias_or_name.lower() for c in arvore.find_all(exp.CTE)}
    usadas = {t.name.lower() for t in arvore.find_all(exp.Table)} - ctes
    desconhecidas = usadas - {t.lower() for t in tabelas_permitidas}
    if desconhecidas:
        raise SQLInvalido(f"Tabela(s) inexistente(s): {', '.join(sorted(desconhecidas))}. "
                          f"Disponíveis: {', '.join(sorted(tabelas_permitidas))}.")

    # limite de linhas: adiciona LIMIT se não houver, e reduz se for maior que o permitido
    limite = arvore.args.get("limit")
    valor = limite.expression if limite is not None else None
    if not (isinstance(valor, exp.Literal) and valor.is_int and int(valor.this) <= max_linhas):
        arvore = arvore.limit(max_linhas)
    return arvore.sql(dialect="sqlite")
