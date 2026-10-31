"""O exemplo de chain do vídeo (prompt | llm | parser), respondendo dúvidas sobre o glossário do CRM.

    python exemplos/rag_chain.py "O que conta como cliente ativo?"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.llm import get_llm
from app.rag import Recuperador

llm = get_llm()  # trocar de provedor = mudar LLM_MODEL
prompt = ChatPromptTemplate.from_template(
    "Use o contexto:\n{contexto}\n\nPergunta: {pergunta}")

chain = prompt | llm | StrOutputParser()

q = sys.argv[1] if len(sys.argv) > 1 else "O que conta como cliente ativo?"
trechos, _ = Recuperador().contexto(q)
print(chain.invoke({"contexto": trechos, "pergunta": q}))
