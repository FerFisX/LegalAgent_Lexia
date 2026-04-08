"""
Chunker de documentos legales bolivianos.

Estrategia: el artículo es la unidad natural de chunk en leyes.
- Si el artículo cabe en el tamaño máximo → un chunk por artículo
- Si el artículo es muy largo → se subdivide con overlap
- Cada chunk lleva metadata completa para el retrieval
"""

from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from data_engineering.parsing.law_parser import ParsedLaw, LegalArticle


# ── Configuración ─────────────────────────────────────────────────────────────
CHUNK_SIZE = 512         # tokens aproximados (usamos chars como proxy: ~4 chars/token)
CHUNK_OVERLAP = 100      # overlap en tokens entre chunks del mismo artículo
CHARS_PER_TOKEN = 4      # aproximación para español

MAX_CHUNK_CHARS = CHUNK_SIZE * CHARS_PER_TOKEN        # ~2048 chars
OVERLAP_CHARS = CHUNK_OVERLAP * CHARS_PER_TOKEN       # ~400 chars


# ── Modelos de datos ──────────────────────────────────────────────────────────

@dataclass
class LegalChunk:
    """
    Unidad mínima de texto lista para generar embedding e indexar.
    Contiene toda la metadata necesaria para el retrieval y el grafo.
    """
    chunk_id: str                    # ej: "ley_1234_art_5_chunk_0"
    text: str                        # texto del chunk
    doc_id: str                      # ej: "ley_1234"
    tipo: str                        # ley / decreto_supremo / etc.
    numero_doc: str                  # número de ley/decreto
    titulo_doc: str                  # título del documento
    fecha_publicacion: str
    article_number: int
    chapter: str = ""
    title_section: str = ""
    areas: list[str] = field(default_factory=list)
    cross_references: list[int] = field(default_factory=list)
    is_derogated: bool = False
    chunk_index: int = 0             # índice del chunk dentro del artículo
    total_chunks_in_article: int = 1

    def to_metadata(self) -> dict:
        """Metadata serializable para ChromaDB."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "tipo": self.tipo,
            "numero_doc": self.numero_doc,
            "titulo_doc": self.titulo_doc,
            "fecha_publicacion": self.fecha_publicacion,
            "article_number": self.article_number,
            "chapter": self.chapter,
            "title_section": self.title_section,
            "areas": ",".join(self.areas),           # ChromaDB no acepta listas
            "cross_references": ",".join(map(str, self.cross_references)),
            "is_derogated": self.is_derogated,
            "chunk_index": self.chunk_index,
            "total_chunks_in_article": self.total_chunks_in_article,
        }


# ── Splitter de LangChain configurado para texto legal ────────────────────────

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=MAX_CHUNK_CHARS,
    chunk_overlap=OVERLAP_CHARS,
    separators=[
        "\n\n",   # párrafos
        "\n",     # líneas
        ". ",     # oraciones
        ", ",     # cláusulas
        " ",      # palabras
        "",       # caracteres
    ],
    length_function=len,
)


# ── Chunker principal ─────────────────────────────────────────────────────────

def _chunk_article(article: LegalArticle, law: ParsedLaw) -> list[LegalChunk]:
    """
    Genera chunks para un artículo individual.
    Si el artículo es corto → 1 chunk.
    Si es largo → múltiples chunks con overlap.
    """
    if not article.text.strip():
        return []

    if len(article.text) <= MAX_CHUNK_CHARS:
        # Artículo corto: un solo chunk
        chunk = LegalChunk(
            chunk_id=f"{law.doc_id}_art_{article.article_number}_chunk_0",
            text=article.text,
            doc_id=law.doc_id,
            tipo=law.tipo,
            numero_doc=law.numero,
            titulo_doc=law.titulo,
            fecha_publicacion=law.fecha_publicacion,
            article_number=article.article_number,
            chapter=article.chapter,
            title_section=article.title_section,
            areas=law.areas,
            cross_references=article.cross_references,
            is_derogated=article.is_derogated,
            chunk_index=0,
            total_chunks_in_article=1,
        )
        return [chunk]

    # Artículo largo: dividir con LangChain
    sub_texts = _splitter.split_text(article.text)
    chunks = []

    for i, sub_text in enumerate(sub_texts):
        chunk = LegalChunk(
            chunk_id=f"{law.doc_id}_art_{article.article_number}_chunk_{i}",
            text=sub_text,
            doc_id=law.doc_id,
            tipo=law.tipo,
            numero_doc=law.numero,
            titulo_doc=law.titulo,
            fecha_publicacion=law.fecha_publicacion,
            article_number=article.article_number,
            chapter=article.chapter,
            title_section=article.title_section,
            areas=law.areas,
            cross_references=article.cross_references,
            is_derogated=article.is_derogated,
            chunk_index=i,
            total_chunks_in_article=len(sub_texts),
        )
        chunks.append(chunk)

    return chunks


def chunk_law(law: ParsedLaw) -> list[LegalChunk]:
    """
    Genera todos los chunks de una ley parseada.
    Omite artículos derogados para no contaminar el índice.

    Args:
        law: ParsedLaw con artículos.

    Returns:
        Lista de LegalChunk listos para embedding.
    """
    all_chunks = []
    skipped_derogated = 0

    for article in law.articles:
        if article.is_derogated:
            skipped_derogated += 1
            continue

        chunks = _chunk_article(article, law)
        all_chunks.extend(chunks)

    logger.success(
        f"Chunking: {law.doc_id} | "
        f"{len(all_chunks)} chunks | "
        f"{skipped_derogated} artículos derogados omitidos"
    )
    return all_chunks


def chunk_many_laws(laws: list[ParsedLaw]) -> list[LegalChunk]:
    """Genera chunks para múltiples leyes."""
    all_chunks = []
    for law in laws:
        chunks = chunk_law(law)
        all_chunks.extend(chunks)
    logger.info(f"Total chunks generados: {len(all_chunks)} de {len(laws)} leyes")
    return all_chunks
