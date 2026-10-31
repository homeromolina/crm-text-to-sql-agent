"""Um único ponto de criação do modelo: trocar de provedor é mudar uma variável de ambiente."""
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app import config


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    return init_chat_model(config.LLM_MODEL, temperature=0)
