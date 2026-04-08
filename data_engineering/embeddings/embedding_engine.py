"""
Motor de embeddings usando BGE-M3 (BAAI/bge-m3).

BGE-M3 es completamente local, gratuito, multilingüe (soporta español),
y genera embeddings densos de 1024 dimensiones.

Diseño LLM-agnóstico: este módulo es independiente del LLM usado
en el agente conversacional. Si mañana cambia de Gemini a GPT-4 o Llama,
este módulo no se toca.
"""

import os
from functools import lru_cache
from typing import List

from loguru import logger
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from data_engineering.chunking.chunker import LegalChunk


# ── Configuración ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")  # "cuda" si hay GPU
BATCH_SIZE = 32          # chunks por batch para no saturar memoria
EMBEDDING_DIMS = 1024    # dimensiones de BGE-M3


# ── Singleton del modelo ──────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """
    Carga el modelo BGE-M3 una sola vez (singleton).
    La primera vez descarga ~2GB desde HuggingFace.
    """
    logger.info(f"Cargando modelo de embeddings: {EMBEDDING_MODEL} en {EMBEDDING_DEVICE}")
    model = SentenceTransformer(EMBEDDING_MODEL, device=EMBEDDING_DEVICE)
    logger.success(f"Modelo cargado. Dimensiones: {EMBEDDING_DIMS}")
    return model


# ── Funciones de embedding ────────────────────────────────────────────────────

def embed_texts(texts: list[str], show_progress: bool = True) -> list[list[float]]:
    """
    Genera embeddings para una lista de textos.

    Args:
        texts: Lista de strings a vectorizar.
        show_progress: Mostrar barra de progreso.

    Returns:
        Lista de vectores float de 1024 dimensiones.
    """
    if not texts:
        return []

    model = _get_model()

    # BGE-M3 recomienda este prefijo para queries de recuperación
    # Para documentos (indexación) no se usa prefijo
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=show_progress,
        normalize_embeddings=True,   # normalizar para cosine similarity
        convert_to_numpy=True,
    )

    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """
    Genera embedding para una consulta del usuario.
    BGE-M3 usa prefijo especial para queries de búsqueda.

    Args:
        query: Pregunta o descripción del problema legal del usuario.

    Returns:
        Vector de 1024 dimensiones.
    """
    model = _get_model()

    # Prefijo recomendado por BGE-M3 para queries
    query_with_prefix = f"Represent this sentence for searching relevant passages: {query}"

    embedding = model.encode(
        [query_with_prefix],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embedding[0].tolist()


def embed_chunks(
    chunks: list[LegalChunk],
    show_progress: bool = True,
) -> list[tuple[LegalChunk, list[float]]]:
    """
    Genera embeddings para una lista de LegalChunks.

    Args:
        chunks: Lista de chunks a vectorizar.
        show_progress: Mostrar progreso.

    Returns:
        Lista de (chunk, embedding) pares.
    """
    if not chunks:
        return []

    logger.info(f"Generando embeddings para {len(chunks)} chunks...")

    texts = [chunk.text for chunk in chunks]
    embeddings = embed_texts(texts, show_progress=show_progress)

    result = list(zip(chunks, embeddings))
    logger.success(f"Embeddings generados: {len(result)} vectores de {EMBEDDING_DIMS} dims")
    return result
