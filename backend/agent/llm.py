"""
Cliente LLM — Gemini 2.5 Flash via LangChain.
Diseño LLM-agnóstico: para cambiar de LLM solo se toca este archivo.
"""

from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.core.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    """Retorna instancia singleton del LLM."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,       # bajo para respuestas legales precisas
        max_tokens=8192,
    )
