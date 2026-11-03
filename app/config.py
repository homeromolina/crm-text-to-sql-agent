"""Configuração central, lida de variáveis de ambiente (ou de um arquivo .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DB_PATH = Path(os.getenv("CRM_DB_PATH", RAIZ / "data" / "crm.db"))
KNOWLEDGE_DIR = RAIZ / "knowledge"

# Padrão: modelo aberto rodando local no Ollama. Qualquer provedor do init_chat_model funciona ("anthropic:...", "openai:...").
LLM_MODEL = os.getenv("LLM_MODEL", "ollama:qwen2.5:7b")
# Vazio = embeddings locais (sem API). Ex.: "openai:text-embedding-3-small"
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "")

MAX_TENTATIVAS = int(os.getenv("MAX_TENTATIVAS", "3"))
MAX_LINHAS = int(os.getenv("MAX_LINHAS", "200"))
TIMEOUT_SEGUNDOS = float(os.getenv("TIMEOUT_SEGUNDOS", "5"))
