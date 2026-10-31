from app.rag import Recuperador


def test_recupera_regra_e_tabela_certas():
    contexto, tabelas = Recuperador().contexto("Quantos clientes ativos temos em Madrid?")
    assert "cliente ativo" in contexto
    assert {"customers", "orders"} <= set(tabelas)


def test_nps_recupera_interactions():
    _, tabelas = Recuperador().contexto("Qual o NPS médio por canal?")
    assert tabelas[0] == "interactions"
