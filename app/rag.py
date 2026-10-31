"""RAG sobre três fontes: esquema das tabelas, glossário de negócio e exemplos pergunta -> SQL."""
import hashlib
import math
import re
import unicodedata

import yaml
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from app import config


class EmbeddingsLocais(Embeddings):
    """Embeddings simples por hashing de palavras e trigramas, para rodar sem API.

    Bom o suficiente para uma base pequena como esta. Em produção, troque por um modelo de
    embeddings de verdade via EMBEDDINGS_MODEL.
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim

    @staticmethod
    def _tokens(texto: str) -> list[str]:
        texto = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
        palavras = re.findall(r"[a-z0-9_]+", texto)
        grams = [f"#{p[i:i + 3]}" for p in palavras if len(p) > 3 for i in range(len(p) - 2)]
        return palavras + grams

    def _vetor(self, texto: str) -> list[float]:
        v = [0.0] * self.dim
        v[0] = 1e-6  # evita vetor zero (texto sem palavras), que quebra a similaridade de cosseno
        for t in self._tokens(texto):
            h = int(hashlib.md5(t.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if not t.startswith("#") else 0.5
        norma = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norma for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vetor(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vetor(text)


def criar_embeddings() -> Embeddings:
    if config.EMBEDDINGS_MODEL:
        from langchain.embeddings import init_embeddings
        return init_embeddings(config.EMBEDDINGS_MODEL)
    return EmbeddingsLocais()


def carregar_documentos() -> list[Document]:
    ler = lambda nome: yaml.safe_load((config.KNOWLEDGE_DIR / nome).read_text(encoding="utf-8"))
    docs = []
    for tabela, info in ler("schema.yaml").items():
        colunas = "\n".join(f"  - {c}: {d}" for c, d in info["colunas"].items())
        docs.append(Document(page_content=f"Tabela {tabela}: {info['descricao']}\nColunas:\n{colunas}",
                             metadata={"tipo": "esquema", "tabela": tabela}))
    for item in ler("glossario.yaml"):
        docs.append(Document(page_content=f"{item['termo']}: {item['regra']}", metadata={"tipo": "glossario"}))
    for item in ler("exemplos.yaml"):
        docs.append(Document(page_content=f"Pergunta: {item['pergunta']}\nSQL:\n{item['sql'].strip()}",
                             metadata={"tipo": "exemplo"}))
    return docs


class Recuperador:
    def __init__(self, embeddings: Embeddings | None = None, k_esquema: int = 3, k_glossario: int = 3,
                 k_exemplos: int = 2):
        self.store = InMemoryVectorStore(embeddings or criar_embeddings())
        self.store.add_documents(carregar_documentos())
        self.k = {"esquema": k_esquema, "glossario": k_glossario, "exemplo": k_exemplos}

    def buscar(self, pergunta: str) -> dict[str, list[Document]]:
        return {tipo: self.store.similarity_search(pergunta, k=k, filter=lambda d, t=tipo: d.metadata["tipo"] == t)
                for tipo, k in self.k.items()}

    def contexto(self, pergunta: str) -> tuple[str, list[str]]:
        """Devolve o contexto formatado pro prompt e a lista de tabelas recuperadas."""
        achados = self.buscar(pergunta)
        tabelas = [d.metadata["tabela"] for d in achados["esquema"]]
        partes = ["## Tabelas", *(d.page_content for d in achados["esquema"]),
                  "\n## Regras de negócio", *(f"- {d.page_content}" for d in achados["glossario"]),
                  "\n## Exemplos validados", *(d.page_content for d in achados["exemplo"])]
        return "\n".join(partes), tabelas
