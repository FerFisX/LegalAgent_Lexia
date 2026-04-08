"""
Retriever híbrido: ChromaDB (semántico) + Neo4j (grafo) + CrossEncoder (re-ranking).

Flujo:
  1. ChromaDB → top-K artículos semánticamente similares
  2. Neo4j → expande con artículos relacionados (2 hops)
  3. CrossEncoder → re-rankea todo el contexto combinado
  4. Retorna contexto enriquecido listo para el LLM
"""

from dataclasses import dataclass
from functools import lru_cache

from loguru import logger
from sentence_transformers import CrossEncoder

from data_engineering.embeddings.chromadb_store import search as chroma_search
from data_engineering.graph.neo4j_builder import (
    expand_context,
    get_processes_for_areas,
    get_lawyers_for_areas,
)


# ── Configuración ─────────────────────────────────────────────────────────────
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_K_CHROMA = 15       # resultados iniciales de ChromaDB
TOP_K_FINAL = 8         # resultados finales tras re-ranking
GRAPH_HOPS = 2          # profundidad de expansión en Neo4j


# ── CrossEncoder (re-ranker) ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    """Carga el CrossEncoder una sola vez (singleton)."""
    logger.info(f"Cargando re-ranker: {RERANKER_MODEL}")
    return CrossEncoder(RERANKER_MODEL)


# ── Modelos de datos ──────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """Resultado completo del retriever híbrido."""
    query: str
    semantic_chunks: list[dict]     # chunks de ChromaDB
    graph_articles: list[dict]      # artículos expandidos por Neo4j
    reranked_context: list[dict]    # contexto final re-rankeado
    processes: list[dict]           # procesos legales recomendados
    lawyers: list[dict]             # abogados recomendados
    detected_areas: list[str]       # áreas legales detectadas

    def build_context_string(self) -> str:
        """
        Construye el string de contexto para pasar al LLM.
        Incluye artículos re-rankeados, procesos y referencias.
        """
        parts = []

        if self.reranked_context:
            parts.append("## Artículos Legales Relevantes (Legislación Boliviana)\n")
            for i, item in enumerate(self.reranked_context, 1):
                meta = item.get("metadata", {})
                parts.append(
                    f"**[{i}] {meta.get('titulo_doc', 'N/A')} - "
                    f"Artículo {meta.get('article_number', '?')}**\n"
                    f"{item['text']}\n"
                )

        if self.processes:
            parts.append("\n## Procesos Legales Aplicables\n")
            for proc in self.processes:
                parts.append(
                    f"**{proc['nombre']}** ({proc['institucion']})\n"
                    f"Pasos: {proc['pasos']}\n"
                    f"Documentos: {proc['documentos']}\n"
                )

        return "\n".join(parts)


# ── Detección de áreas desde la query ────────────────────────────────────────

AREA_KEYWORDS = {
    "penal": ["robo", "hurto", "delito", "crimen", "asalto", "violación", "homicidio",
              "lesiones", "amenaza", "extorsión", "fraude", "estafa", "penal"],
    "civil": ["contrato", "deuda", "propiedad", "herencia", "sucesión", "daño civil",
              "indemnización", "arrendamiento", "alquiler"],
    "laboral": ["despido", "salario", "empleador", "trabajador", "trabajo", "horas extra",
                "beneficios sociales", "aguinaldo", "contrato laboral"],
    "tránsito": ["accidente", "vehículo", "atropello", "choque", "colisión", "conductor",
                 "tránsito", "seguro", "soat"],
    "familiar": ["divorcio", "separación", "tuición", "pensión", "matrimonio", "hijo",
                 "custodia", "alimentos"],
    "tributario": ["impuesto", "iva", "renta", "sin", "aduana", "multa tributaria"],
    "administrativo": ["gobierno", "municipio", "permiso", "licencia", "concesión",
                       "sanción administrativa"],
    "comercial": ["empresa", "sociedad", "quiebra", "comercio", "proveedor", "factura"],
}


def detect_areas_from_query(query: str) -> list[str]:
    """Detecta áreas legales relevantes en la consulta del usuario."""
    query_lower = query.lower()
    detected = [
        area
        for area, keywords in AREA_KEYWORDS.items()
        if any(kw in query_lower for kw in keywords)
    ]
    return detected or ["civil"]  # default a civil si no detecta nada


# ── Retriever principal ───────────────────────────────────────────────────────

def retrieve(
    query: str,
    ciudad: str = None,
    top_k_final: int = TOP_K_FINAL,
) -> RetrievalResult:
    """
    Retrieval híbrido completo para una consulta legal.

    Args:
        query: Descripción del problema legal en lenguaje natural.
        ciudad: Ciudad del usuario para filtrar abogados.
        top_k_final: Número de chunks finales tras re-ranking.

    Returns:
        RetrievalResult con todo el contexto enriquecido.
    """
    logger.info(f"Retrieval híbrido: '{query[:60]}...'")

    # ── PASO 1: Detectar áreas legales ────────────────────────────────────────
    areas = detect_areas_from_query(query)
    logger.debug(f"Áreas detectadas: {areas}")

    # ── PASO 2: ChromaDB - búsqueda semántica ─────────────────────────────────
    semantic_results = chroma_search(
        query=query,
        n_results=TOP_K_CHROMA,
        filter_areas=areas if areas else None,
        exclude_derogated=True,
    )
    logger.debug(f"ChromaDB: {len(semantic_results)} resultados")

    # ── PASO 3: Neo4j - expansión por grafo ───────────────────────────────────
    chunk_ids = [r["chunk_id"] for r in semantic_results]
    graph_articles = expand_context(chunk_ids, hops=GRAPH_HOPS)
    logger.debug(f"Neo4j expandió a {len(graph_articles)} artículos")

    # Convertir artículos del grafo al mismo formato que ChromaDB
    graph_as_chunks = [
        {
            "chunk_id": art["articulo_id"],
            "text": art["texto"],
            "metadata": {
                "article_number": art["numero"],
                "doc_id": art["doc_id"],
                "chapter": art.get("capitulo", ""),
            },
            "distance": 0.5,  # distancia neutra para artículos expandidos
            "similarity": 0.5,
            "source": "graph",
        }
        for art in graph_articles
        if art.get("texto")
    ]

    # Marcar fuente de los resultados semánticos
    for r in semantic_results:
        r["source"] = "semantic"

    # Combinar ambas fuentes
    combined = semantic_results + graph_as_chunks

    # ── PASO 4: Re-ranking con CrossEncoder ───────────────────────────────────
    if combined:
        reranker = _get_reranker()
        pairs = [(query, item["text"]) for item in combined]
        scores = reranker.predict(pairs)

        for item, score in zip(combined, scores):
            item["rerank_score"] = float(score)

        # Ordenar por score del re-ranker y tomar top-K
        reranked = sorted(combined, key=lambda x: x["rerank_score"], reverse=True)
        reranked = reranked[:top_k_final]
    else:
        reranked = []

    logger.debug(f"Re-ranking: {len(reranked)} chunks finales")

    # ── PASO 5: Procesos y abogados desde Neo4j ───────────────────────────────
    processes = get_processes_for_areas(areas)
    lawyers = get_lawyers_for_areas(areas, ciudad=ciudad)

    result = RetrievalResult(
        query=query,
        semantic_chunks=semantic_results,
        graph_articles=graph_articles,
        reranked_context=reranked,
        processes=processes,
        lawyers=lawyers,
        detected_areas=areas,
    )

    logger.success(
        f"Retrieval completo: {len(reranked)} chunks | "
        f"{len(processes)} procesos | {len(lawyers)} abogados"
    )
    return result
