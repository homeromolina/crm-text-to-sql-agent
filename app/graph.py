"""O agente como um grafo do LangGraph:

    START -> buscar_contexto -> gerar_sql -> validar -> [aprovar] -> executar -> explicar -> END
                                   ^            |                        |
                                   +--- erro ---+------------ erro ------+
    Violação de segurança ou tentativas esgotadas -> desistir -> END
"""
import re
from typing import Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app import config, db, guardrails, prompts
from app.rag import Recuperador


class Estado(TypedDict, total=False):
    pergunta: str
    contexto: str
    tabelas_recuperadas: list[str]
    sql: str
    erro: str | None
    bloqueado: bool
    tentativas: int
    resultado: dict | None
    resposta: str


def extrair_sql(texto: str) -> str:
    bloco = re.search(r"```(?:sql)?\s*(.*?)```", texto, re.S | re.I)
    return (bloco.group(1) if bloco else texto).strip()


def construir_grafo(llm: BaseChatModel | None = None, recuperador: Recuperador | None = None,
                    aprovacao_humana: bool = False, checkpointer=None):
    if llm is None:
        from app.llm import get_llm
        llm = get_llm()
    recuperador = recuperador or Recuperador()
    tabelas_banco = db.tabelas()
    gerador = prompts.GERAR_SQL | llm | StrOutputParser()
    explicador = prompts.EXPLICAR | llm | StrOutputParser()

    def buscar_contexto(estado: Estado) -> Estado:
        contexto, tabelas = recuperador.contexto(estado["pergunta"])
        return {"contexto": contexto, "tabelas_recuperadas": tabelas, "tentativas": 0, "erro": None,
                "bloqueado": False}

    def gerar_sql(estado: Estado) -> Estado:
        erro_anterior = (prompts.ERRO_ANTERIOR.format(sql=estado["sql"], erro=estado["erro"])
                         if estado.get("erro") else "")
        saida = gerador.invoke({"contexto": estado["contexto"], "pergunta": estado["pergunta"],
                                "erro_anterior": erro_anterior})
        return {"sql": extrair_sql(saida), "tentativas": estado.get("tentativas", 0) + 1, "erro": None}

    def validar(estado: Estado) -> Estado:
        try:
            return {"sql": guardrails.validar(estado["sql"], tabelas_banco)}
        except guardrails.SQLBloqueado as e:
            return {"erro": str(e), "bloqueado": True}
        except guardrails.SQLInvalido as e:
            return {"erro": str(e)}

    def aprovar(estado: Estado) -> Estado:
        # pausa o grafo (o estado fica salvo no checkpoint) até um humano responder
        decisao = interrupt({"sql": estado["sql"], "mensagem": "Aprovar a execução deste SQL? (s/n)"})
        if str(decisao).strip().lower() not in {"s", "sim", "y", "yes"}:
            return {"erro": "Execução recusada pelo revisor.", "bloqueado": True}
        return {}

    def executar(estado: Estado) -> Estado:
        try:
            return {"resultado": db.executar(estado["sql"]), "erro": None}
        except Exception as e:  # erro do banco volta pro gerador como feedback
            return {"erro": f"{type(e).__name__}: {e}", "resultado": None}

    def explicar(estado: Estado) -> Estado:
        r = estado["resultado"]
        linhas = "\n".join(str(l) for l in r["linhas"][:50]) or "(nenhuma linha)"
        aviso = f"\n(Resultado truncado em {len(r['linhas'])} linhas.)" if r["truncado"] else ""
        resposta = explicador.invoke({"pergunta": estado["pergunta"], "sql": estado["sql"],
                                      "colunas": ", ".join(r["colunas"]), "linhas": linhas,
                                      "aviso_truncado": aviso})
        return {"resposta": resposta}

    def desistir(estado: Estado) -> Estado:
        if estado.get("bloqueado"):
            return {"resposta": f"Não posso executar isso: {estado['erro']}"}
        return {"resposta": f"Não consegui montar uma consulta válida depois de {estado['tentativas']} "
                            f"tentativas. Último erro: {estado['erro']}"}

    def deu_erro(estado: Estado) -> Literal["sim", "nao", "desistir"]:
        if not estado.get("erro"):
            return "nao"
        if estado.get("bloqueado") or estado["tentativas"] >= config.MAX_TENTATIVAS:
            return "desistir"
        return "sim"

    g = StateGraph(Estado)
    g.add_node("buscar_contexto", buscar_contexto)
    g.add_node("gerar_sql", gerar_sql)
    g.add_node("validar", validar)
    g.add_node("executar", executar)
    g.add_node("explicar", explicar)
    g.add_node("desistir", desistir)

    g.add_edge(START, "buscar_contexto")
    g.add_edge("buscar_contexto", "gerar_sql")
    g.add_edge("gerar_sql", "validar")
    depois_de_validar = "aprovar" if aprovacao_humana else "executar"
    g.add_conditional_edges("validar", deu_erro,
                            {"sim": "gerar_sql", "nao": depois_de_validar, "desistir": "desistir"})
    if aprovacao_humana:
        g.add_node("aprovar", aprovar)
        g.add_conditional_edges("aprovar", deu_erro, {"nao": "executar", "sim": "desistir", "desistir": "desistir"})
    g.add_conditional_edges("executar", deu_erro, {"sim": "gerar_sql", "nao": "explicar", "desistir": "desistir"})
    g.add_edge("explicar", END)
    g.add_edge("desistir", END)

    if aprovacao_humana and checkpointer is None:
        checkpointer = InMemorySaver()  # interrupt precisa de checkpoint para retomar
    return g.compile(checkpointer=checkpointer)
