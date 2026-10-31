"""Acesso ao banco: conexão só de leitura, limite de tempo, limite de linhas e máscara de dados pessoais."""
import re
import sqlite3
import time
from pathlib import Path

from app import config

COLUNAS_PESSOAIS = {"email", "phone"}
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def conectar(db_path: Path | None = None) -> sqlite3.Connection:
    """Abre o SQLite em modo read-only: mesmo que um DELETE passasse, o banco recusaria."""
    path = db_path or config.DB_PATH
    if not Path(path).exists():
        raise FileNotFoundError(f"Banco não encontrado em {path}. Rode: python data/seed.py")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def mascarar(valor, coluna: str):
    if coluna.lower() in COLUNAS_PESSOAIS and valor is not None:
        texto = str(valor)
        return texto[:2] + "***" if len(texto) > 2 else "***"
    if isinstance(valor, str):
        return RE_EMAIL.sub("***@***", valor)
    return valor


def executar(sql: str, max_linhas: int | None = None, timeout: float | None = None,
             db_path: Path | None = None) -> dict:
    max_linhas = max_linhas or config.MAX_LINHAS
    timeout = timeout or config.TIMEOUT_SEGUNDOS
    con = conectar(db_path)
    limite = time.monotonic() + timeout
    # o SQLite chama este handler periodicamente; retornar 1 aborta a consulta
    con.set_progress_handler(lambda: 1 if time.monotonic() > limite else 0, 10_000)
    try:
        cur = con.execute(sql)
        colunas = [d[0] for d in cur.description or []]
        linhas = cur.fetchmany(max_linhas + 1)
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e):
            raise TimeoutError(f"Consulta passou de {timeout}s e foi cancelada") from e
        raise
    finally:
        con.close()
    truncado = len(linhas) > max_linhas
    linhas = [tuple(mascarar(v, c) for v, c in zip(l, colunas)) for l in linhas[:max_linhas]]
    return {"colunas": colunas, "linhas": linhas, "truncado": truncado}


def tabelas(db_path: Path | None = None) -> set[str]:
    con = conectar(db_path)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
