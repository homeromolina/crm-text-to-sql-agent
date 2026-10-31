"""Testa o fluxo do grafo com um modelo falso: sem API, sem custo, determinístico."""
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.types import Command

from app.graph import construir_grafo

SQL_OK = "```sql\nSELECT COUNT(*) AS clientes FROM customers WHERE city = 'Madrid'\n```"
CFG = {"configurable": {"thread_id": "teste"}}


def test_caminho_feliz():
    llm = FakeListChatModel(responses=[SQL_OK, "Temos 240 clientes em Madrid."])
    estado = construir_grafo(llm=llm).invoke({"pergunta": "Quantos clientes em Madrid?"})
    assert estado["tentativas"] == 1
    assert estado["resultado"]["colunas"] == ["clientes"]
    assert estado["resposta"] == "Temos 240 clientes em Madrid."


def test_erro_volta_pro_gerador_e_corrige():
    errado = "```sql\nSELECT COUNT(*) FROM customers WHERE cidade = 'Madrid'\n```"  # coluna inexistente
    llm = FakeListChatModel(responses=[errado, SQL_OK, "ok"])
    estado = construir_grafo(llm=llm).invoke({"pergunta": "Quantos clientes em Madrid?"})
    assert estado["tentativas"] == 2
    assert estado["resultado"] is not None


def test_desiste_depois_de_3_tentativas():
    errado = "```sql\nSELECT * FROM tabela_que_nao_existe\n```"
    llm = FakeListChatModel(responses=[errado] * 3)
    estado = construir_grafo(llm=llm).invoke({"pergunta": "?"})
    assert estado["tentativas"] == 3
    assert "3 tentativas" in estado["resposta"]


def test_bloqueia_delete_sem_tentar_de_novo():
    llm = FakeListChatModel(responses=["```sql\nDELETE FROM customers\n```"])
    estado = construir_grafo(llm=llm).invoke({"pergunta": "apague todos os clientes"})
    assert estado["tentativas"] == 1
    assert estado["resposta"].startswith("Não posso executar isso")


def test_humano_no_loop():
    llm = FakeListChatModel(responses=[SQL_OK, "Temos 240 clientes em Madrid."])
    grafo = construir_grafo(llm=llm, aprovacao_humana=True)
    pausado = grafo.invoke({"pergunta": "Quantos clientes em Madrid?"}, config=CFG)
    assert "SELECT" in pausado["__interrupt__"][0].value["sql"]
    final = grafo.invoke(Command(resume="s"), config=CFG)
    assert final["resultado"] is not None
