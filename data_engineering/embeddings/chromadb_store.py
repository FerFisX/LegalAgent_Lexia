"""
Almacén vectorial en ChromaDB para los chunks legales.
Gestiona inserción, actualización y búsqueda semántica.
"""

import os
from loguru import logger

import chromadb
from chromadb.config import Settings

from data_engineering.chunking.chunker import LegalChunk
from data_engineering.embeddings.embedding_engine import embed_chunks, embed_query


# ── Configuración ─────────────────────────────────────────────────────────────
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "lexia_legal_docs")

# Para desarrollo local usamos persistencia en disco (sin servidor)
CHROMA_LOCAL_PATH = "data/chroma_db"


# ── Cliente ChromaDB ──────────────────────────────────────────────────────────

def _get_client() -> chromadb.ClientAPI:
    """
    Retorna cliente ChromaDB.
    En desarrollo: persistencia local en disco.
    En producción: HttpClient apuntando al contenedor.
    """
    env = os.getenv("ENV", "development")

    if env == "production":
        return chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(anonymized_telemetry=False),
        )
    else:
        # Desarrollo: base vectorial local en disco
        return chromadb.PersistentClient(
            path=CHROMA_LOCAL_PATH,
            settings=Settings(anonymized_telemetry=False),
        )


def _get_collection() -> chromadb.Collection:
    """Obtiene o crea la colección principal de documentos legales."""
    client = _get_client()
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},  # similitud coseno
    )
    return collection


# ── Operaciones CRUD ──────────────────────────────────────────────────────────

def upsert_chunks(chunks: list[LegalChunk]) -> int:
    """
    Inserta o actualiza chunks en ChromaDB con sus embeddings.
    Usa upsert para que sea idempotente (re-ejecutable sin duplicados).

    Args:
        chunks: Lista de LegalChunk a indexar.

    Returns:
        Cantidad de chunks indexados.
    """
    if not chunks:
        logger.warning("No hay chunks para indexar.")
        return 0

    collection = _get_collection()

    # Generar embeddings
    chunk_embeddings = embed_chunks(chunks)

    # Preparar datos para ChromaDB
    ids = [chunk.chunk_id for chunk, _ in chunk_embeddings]
    embeddings = [emb for _, emb in chunk_embeddings]
    documents = [chunk.text for chunk, _ in chunk_embeddings]
    metadatas = [chunk.to_metadata() for chunk, _ in chunk_embeddings]

    # Upsert en batches de 100 (límite recomendado por ChromaDB)
    batch_size = 100
    total = 0

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_embs = embeddings[i:i + batch_size]
        batch_docs = documents[i:i + batch_size]
        batch_metas = metadatas[i:i + batch_size]

        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embs,
            documents=batch_docs,
            metadatas=batch_metas,
        )
        total += len(batch_ids)
        logger.debug(f"Indexados {total}/{len(ids)} chunks")

    logger.success(f"ChromaDB: {total} chunks indexados en '{CHROMA_COLLECTION}'")
    return total


def delete_doc_chunks(doc_id: str) -> None:
    """
    Elimina todos los chunks de un documento específico.
    Útil cuando una ley es actualizada o derogada.
    """
    collection = _get_collection()

    # Buscar todos los chunks del documento
    results = collection.get(where={"doc_id": doc_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        logger.info(f"Eliminados {len(results['ids'])} chunks de: {doc_id}")
    else:
        logger.debug(f"No se encontraron chunks para eliminar: {doc_id}")


def search(
    query: str,
    n_results: int = 10,
    filter_areas: list[str] = None,
    filter_tipo: str = None,
    exclude_derogated: bool = True,
) -> list[dict]:
    """
    Búsqueda semántica en ChromaDB.

    Args:
        query: Consulta en lenguaje natural del usuario.
        n_results: Número de resultados a retornar.
        filter_areas: Filtrar por áreas legales (ej: ["penal", "civil"]).
        filter_tipo: Filtrar por tipo de documento (ej: "ley").
        exclude_derogated: Excluir artículos derogados.

    Returns:
        Lista de dicts con texto, metadata y distancia.
    """
    collection = _get_collection()
    query_embedding = embed_query(query)

    # Construir filtros where de ChromaDB
    where_conditions = []

    if exclude_derogated:
        where_conditions.append({"is_derogated": False})

    if filter_tipo:
        where_conditions.append({"tipo": filter_tipo})

    if filter_areas:
        # ChromaDB no soporta OR en listas directamente,
        # filtramos por la primera área (refinamos en reranker)
        where_conditions.append({"areas": {"$contains": filter_areas[0]}})

    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # Formatear resultados
    formatted = []
    for i in range(len(results["ids"][0])):
        formatted.append({
            "chunk_id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
            "similarity": 1 - results["distances"][0][i],  # cosine similarity
        })

    logger.debug(f"ChromaDB search: {len(formatted)} resultados para '{query[:50]}...'")
    return formatted


def get_collection_stats() -> dict:
    """Retorna estadísticas de la colección."""
    collection = _get_collection()
    count = collection.count()
    return {
        "collection": CHROMA_COLLECTION,
        "total_chunks": count,
    }
