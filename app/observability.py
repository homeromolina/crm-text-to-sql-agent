"""Langfuse: cada execução do grafo vira um trace com os nós, prompts, tempos e tokens.

Fica desligado se as chaves não estiverem configuradas, então o projeto roda sem conta.
"""
import os


def langfuse_ativo() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def callbacks() -> list:
    if not langfuse_ativo():
        return []
    from langfuse.langchain import CallbackHandler
    return [CallbackHandler()]


def cliente():
    """Cliente do Langfuse para scores e flush, ou None se estiver desligado."""
    if not langfuse_ativo():
        return None
    from langfuse import get_client
    return get_client()
