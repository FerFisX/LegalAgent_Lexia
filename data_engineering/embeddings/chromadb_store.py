"""
Almacén vectorial usando LanceDB.
Reemplaza ChromaDB — misma interfaz, sin necesidad de compilación en Windows.

LanceDB almacena los vectores en disco localmente (data/lancedb/).
"""

import os
from pathlib import Path

import lancedb
import pyarrow as pa
from loguru import logger

from data_engineering.chunking.chunker import LegalChunk
from data_engineering.embeddings.embedding_engine import embed_chunks, embed_query


# ── Configuración ─────────────────────────────────────────────────────────────
LANCEDB_PATH = "data/lancedb"
TABLE_NAME = os.getenv("CHROMA_COLLECTION", "lexia_legal_docs")  # mismo env var
EMBEDDING_DIMS = 1024


# ── Schema de la tabla ────────────────────────────────────────────────────────

def _get_schema() -> pa.Schema:
    return pa.schema([
        pa.field("chunk_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIMS)),
        pa.field("doc_id", pa.string()),
        pa.field("tipo", pa.string()),
        pa.field("numero_doc", pa.string()),
        pa.field("titulo_doc", pa.string()),
        pa.field("fecha_publicacion", pa.string()),
        pa.field("article_number", pa.int32()),
        pa.field("chapter", pa.string()),
        pa.field("title_section", pa.string()),
        pa.field("areas", pa.string()),
        pa.field("cross_references", pa.string()),
        pa.field("is_derogated", pa.bool_()),
        pa.field("chunk_index", pa.int32()),
        pa.field("total_chunks_in_article", pa.int32()),
    ])


def _get_table() -> lancedb.table.Table:
    """Obtiene o crea la tabla en LanceDB."""
    Path(LANCEDB_PATH).mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(LANCEDB_PATH)

    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    else:
        return db.create_table(TABLE_NAME, schema=_get_schema())


# ── Operaciones CRUD ──────────────────────────────────────────────────────────

def upsert_chunks(chunks: list[LegalChunk]) -> int:
    """
    Inserta o actualiza chunks en LanceDB con sus embeddings.
    """
    if not chunks:
        logger.warning("No hay chunks para indexar.")
        return 0

    table = _get_table()

    # Generar embeddings
    chunk_embeddings = embed_chunks(chunks)

    # Preparar registros
    records = []
    for chunk, embedding in chunk_embeddings:
        meta = chunk.to_metadata()
        records.append({
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "vector": embedding,
            "doc_id": meta["doc_id"],
            "tipo": meta["tipo"],
            "numero_doc": meta["numero_doc"],
            "titulo_doc": meta["titulo_doc"],
            "fecha_publicacion": meta["fecha_publicacion"],
            "article_number": int(meta["article_number"]),
            "chapter": meta["chapter"],
            "title_section": meta["title_section"],
            "areas": meta["areas"],
            "cross_references": meta["cross_references"],
            "is_derogated": bool(meta["is_derogated"]),
            "chunk_index": int(meta["chunk_index"]),
            "total_chunks_in_article": int(meta["total_chunks_in_article"]),
        })

    # Eliminar registros anteriores del mismo doc para upsert limpio
    if records:
        doc_ids = list({r["doc_id"] for r in records})
        try:
            for doc_id in doc_ids:
                table.delete(f"doc_id = '{doc_id}'")
        except Exception:
            pass  # tabla vacía, no hay nada que borrar

    table.add(records)
    logger.success(f"LanceDB: {len(records)} chunks indexados en '{TABLE_NAME}'")
    return len(records)


def delete_doc_chunks(doc_id: str) -> None:
    """Elimina todos los chunks de un documento."""
    try:
        table = _get_table()
        table.delete(f"doc_id = '{doc_id}'")
        logger.info(f"Eliminados chunks de: {doc_id}")
    except Exception as e:
        logger.debug(f"No se pudo eliminar chunks de {doc_id}: {e}")


def search(
    query: str,
    n_results: int = 10,
    filter_areas: list[str] = None,
    filter_tipo: str = None,
    exclude_derogated: bool = True,
) -> list[dict]:
    """
    Búsqueda semántica en LanceDB.
    """
    table = _get_table()
    query_embedding = embed_query(query)

    # Búsqueda vectorial
    search_query = table.search(query_embedding).limit(n_results * 2)

    results_df = search_query.to_pandas()

    if results_df.empty:
        return []

    # Filtros en pandas (más simple que SQL en LanceDB)
    if exclude_derogated:
        results_df = results_df[results_df["is_derogated"] == False]

    if filter_tipo:
        results_df = results_df[results_df["tipo"] == filter_tipo]

    if filter_areas:
        mask = results_df["areas"].apply(
            lambda a: any(area in a for area in filter_areas)
        )
        results_df = results_df[mask]

    results_df = results_df.head(n_results)

    formatted = []
    for _, row in results_df.iterrows():
        formatted.append({
            "chunk_id": row["chunk_id"],
            "text": row["text"],
            "metadata": {
                "doc_id": row["doc_id"],
                "tipo": row["tipo"],
                "titulo_doc": row["titulo_doc"],
                "article_number": row["article_number"],
                "chapter": row["chapter"],
                "areas": row["areas"],
                "is_derogated": row["is_derogated"],
            },
            "distance": float(row.get("_distance", 0)),
            "similarity": 1 - float(row.get("_distance", 0)),
        })

    logger.debug(f"LanceDB search: {len(formatted)} resultados para '{query[:50]}'")
    return formatted


def get_collection_stats() -> dict:
    """Estadísticas de la tabla."""
    table = _get_table()
    return {
        "table": TABLE_NAME,
        "total_chunks": table.count_rows(),
        "path": LANCEDB_PATH,
    }
