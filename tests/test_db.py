import pytest

from app import db


def test_mascara_dados_pessoais():
    r = db.executar("SELECT email, phone, city FROM customers LIMIT 3")
    for email, phone, city in r["linhas"]:
        assert "***" in email and "***" in phone and city


def test_conexao_somente_leitura():
    with pytest.raises(Exception, match="readonly"):
        db.executar("DELETE FROM customers")


def test_limite_de_linhas():
    r = db.executar("SELECT id FROM customers", max_linhas=10)
    assert len(r["linhas"]) == 10 and r["truncado"]
