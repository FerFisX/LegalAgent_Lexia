"""
Prefect DAG: Pipeline completo de ingesta de la Gaceta Oficial de Bolivia.

Flujo principal (corre cada 24h):
  1. Scraper → detecta documentos nuevos/modificados
  2. Extractor PDF → extrae texto (PyMuPDF + OCR)
  3. Parser → estructura artículos
  4. Chunker → divide en unidades indexables
  5. Embeddings → genera vectores BGE-M3
  6. ChromaDB → indexa vectores
  7. Neo4j → actualiza grafo de relaciones

Trigger manual disponible para forzar actualización.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from loguru import logger
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta

from data_engineering.scraper.gaceta_scraper import run_scraper_and_download
from data_engineering.extraction.pdf_extractor import extract_pdf
from data_engineering.parsing.law_parser import parse_law
from data_engineering.chunking.chunker import chunk_law
from data_engineering.embeddings.chromadb_store import upsert_chunks, delete_doc_chunks
from data_engineering.graph.neo4j_builder import (
    init_schema,
    seed_base_data,
    build_graph_from_laws,
    upsert_law,
)


PROCESSED_PATH = Path("data/processed")
PROCESSED_PATH.mkdir(parents=True, exist_ok=True)


# ── Tasks de Prefect ──────────────────────────────────────────────────────────

@task(
    name="scrape-gaceta",
    retries=2,
    retry_delay_seconds=60,
    description="Scrapea Gaceta Oficial y detecta documentos nuevos/modificados",
)
async def task_scrape(sections: list[str] = None, max_pages: int = 5) -> list[dict]:
    pf_logger = get_run_logger()
    pf_logger.info("Iniciando scraper de Gaceta Oficial de Bolivia...")

    results = await run_scraper_and_download(
        sections=sections,
        max_pages=max_pages,
        delay_seconds=2.0,
    )
    pf_logger.info(f"Documentos detectados: {len(results)}")
    return results


@task(
    name="extract-pdf",
    retries=1,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=24),
    description="Extrae texto de un PDF (PyMuPDF + OCR fallback)",
)
def task_extract(doc_meta: dict) -> dict | None:
    pf_logger = get_run_logger()

    pdf_path = doc_meta.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        pf_logger.warning(f"PDF no encontrado: {pdf_path}")
        return None

    extracted = extract_pdf(pdf_path, doc_id=doc_meta["doc_id"])
    if not extracted.success:
        pf_logger.error(f"Extracción fallida: {doc_meta['doc_id']}")
        return None

    pf_logger.info(f"Extraído: {doc_meta['doc_id']} ({len(extracted.full_text)} chars)")
    return {
        "doc_meta": doc_meta,
        "full_text": extracted.full_text,
        "total_pages": extracted.total_pages,
        "method": extracted.extraction_method,
    }


@task(
    name="parse-law",
    description="Parsea artículos, detecta referencias cruzadas y derogaciones",
)
def task_parse(extracted: dict) -> dict | None:
    if not extracted:
        return None

    pf_logger = get_run_logger()
    meta = extracted["doc_meta"]

    parsed = parse_law(
        full_text=extracted["full_text"],
        doc_id=meta["doc_id"],
        tipo=meta.get("tipo", "ley"),
        numero=meta.get("numero", ""),
        titulo=meta.get("titulo", ""),
        fecha_publicacion=meta.get("fecha", ""),
        areas=meta.get("areas", []),
    )

    pf_logger.info(f"Parseado: {meta['doc_id']} | {parsed.total_articles} artículos")

    # Guardar JSON procesado en disco
    output_path = PROCESSED_PATH / f"{meta['doc_id']}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed.to_dict(), f, ensure_ascii=False, indent=2)

    return parsed


@task(
    name="index-document",
    retries=2,
    description="Genera chunks, embeddings y actualiza ChromaDB + Neo4j",
)
def task_index(parsed_law) -> bool:
    if not parsed_law:
        return False

    pf_logger = get_run_logger()

    # Eliminar versión anterior si existe (actualización)
    delete_doc_chunks(parsed_law.doc_id)

    # Chunking
    chunks = chunk_law(parsed_law)
    if not chunks:
        pf_logger.warning(f"Sin chunks para: {parsed_law.doc_id}")
        return False

    # ChromaDB: vectores
    indexed = upsert_chunks(chunks)
    pf_logger.info(f"ChromaDB: {indexed} chunks indexados")

    # Neo4j: grafo
    from data_engineering.graph.neo4j_builder import _get_driver
    driver = _get_driver()
    with driver.session() as session:
        upsert_law(parsed_law, session)
    driver.close()
    pf_logger.info(f"Neo4j: grafo actualizado para {parsed_law.doc_id}")

    return True


# ── Flow principal ────────────────────────────────────────────────────────────

@flow(
    name="lexia-gaceta-pipeline",
    description="Pipeline ETL completo: Gaceta Oficial → Graph RAG",
    version="1.0.0",
)
async def gaceta_pipeline(
    sections: list[str] = None,
    max_pages: int = 5,
    force_all: bool = False,
) -> dict:
    """
    Pipeline completo de ingesta.

    Args:
        sections: Secciones a scrapear (None = todas).
        max_pages: Páginas por sección.
        force_all: Si True, reprocesa aunque no haya cambios.

    Returns:
        Resumen de la ejecución.
    """
    pf_logger = get_run_logger()
    pf_logger.info("=== LEXIA PIPELINE INICIADO ===")
    start = datetime.utcnow()

    # 1. Scraping
    scraped_docs = await task_scrape(sections=sections, max_pages=max_pages)

    if not scraped_docs and not force_all:
        pf_logger.info("No hay documentos nuevos. Pipeline finalizado.")
        return {"status": "no_changes", "processed": 0}

    # 2-3-4: Extracción, Parsing e Indexación por documento
    processed = 0
    failed = 0

    for doc_meta in scraped_docs:
        try:
            extracted = task_extract(doc_meta)
            parsed = task_parse(extracted)
            success = task_index(parsed)

            if success:
                processed += 1
            else:
                failed += 1
        except Exception as e:
            pf_logger.error(f"Error procesando {doc_meta.get('doc_id')}: {e}")
            failed += 1

    elapsed = (datetime.utcnow() - start).total_seconds()

    summary = {
        "status": "completed",
        "processed": processed,
        "failed": failed,
        "elapsed_seconds": elapsed,
        "timestamp": start.isoformat(),
    }

    pf_logger.info(f"=== PIPELINE FINALIZADO: {processed} docs | {failed} errores | {elapsed:.1f}s ===")
    return summary


# ── Flow de inicialización (correr una sola vez) ──────────────────────────────

@flow(name="lexia-init", description="Inicializa esquema Neo4j y datos base")
def init_pipeline() -> None:
    """Inicialización del sistema. Correr solo la primera vez."""
    pf_logger = get_run_logger()

    pf_logger.info("Inicializando esquema Neo4j...")
    init_schema()

    pf_logger.info("Insertando datos base (áreas, procesos, abogados)...")
    seed_base_data()

    pf_logger.info("Sistema inicializado correctamente.")


# ── Entry points ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    command = sys.argv[1] if len(sys.argv) > 1 else "pipeline"

    if command == "init":
        init_pipeline()
    elif command == "pipeline":
        asyncio.run(gaceta_pipeline(max_pages=3))
    else:
        print("Uso: python flows.py [init|pipeline]")
