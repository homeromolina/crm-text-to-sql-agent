import pytest

from app.guardrails import SQLBloqueado, SQLInvalido, validar

TABELAS = {"customers", "orders", "products", "interactions"}


@pytest.mark.parametrize("sql", [
    "DELETE FROM customers",
    "UPDATE orders SET amount = 0",
    "DROP TABLE customers",
    "SELECT 1; DELETE FROM customers",
    "INSERT INTO products VALUES (99, 'x', 'y', 1)",
])
def test_bloqueia_escrita(sql):
    with pytest.raises(SQLBloqueado):
        validar(sql, TABELAS)


def test_tabela_inexistente_vira_erro_corrigivel():
    with pytest.raises(SQLInvalido, match="clientes"):
        validar("SELECT * FROM clientes", TABELAS)


def test_adiciona_e_reduz_limit():
    assert "LIMIT 200" in validar("SELECT * FROM customers", TABELAS, max_linhas=200)
    assert "LIMIT 200" in validar("SELECT * FROM customers LIMIT 5000", TABELAS, max_linhas=200)
    assert "LIMIT 5" in validar("SELECT * FROM customers LIMIT 5", TABELAS, max_linhas=200)


def test_permite_cte():
    sql = "WITH t AS (SELECT customer_id FROM orders) SELECT COUNT(*) FROM t"
    assert validar(sql, TABELAS).startswith("WITH")
