"""Tool calling: o modelo decide chamar run_sql e com quais argumentos.

    python exemplos/tool_calling.py "Quantos pedidos cancelados existem?"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import get_llm
from app.rag import Recuperador
from app.tools import run_sql

pergunta = sys.argv[1] if len(sys.argv) > 1 else "Quantos pedidos cancelados existem?"
contexto, _ = Recuperador().contexto(pergunta)
llm = get_llm().bind_tools([run_sql])

mensagens = [SystemMessage(f"Banco SQLite do CRM. Use a ferramenta run_sql.\n{contexto}"),
             HumanMessage(pergunta)]
for _ in range(4):  # poucas voltas: chamar ferramenta -> ler resultado -> responder
    resposta = llm.invoke(mensagens)
    mensagens.append(resposta)
    if not resposta.tool_calls:
        break
    for chamada in resposta.tool_calls:
        print(f"-> {chamada['name']}({chamada['args']})")
        mensagens.append(run_sql.invoke(chamada))
print(resposta.text)
