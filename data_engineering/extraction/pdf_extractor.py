"""
Extractor de texto desde PDFs de la Gaceta Oficial de Bolivia.

Estrategia en cascada (LLM-agnóstica):
  1. PyMuPDF  → extracción nativa de texto con layout
  2. pdfplumber → mejor para tablas y columnas múltiples
  3. Tesseract OCR → fallback para PDFs escaneados (solo imágenes)

El resultado es siempre texto limpio listo para el pipeline,
independientemente del LLM que se use después.
"""

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
from loguru import logger

from data_engineering.extraction.ocr_fallback import extract_with_ocr
from data_engineering.extraction.text_cleaner import clean_text


# ── Umbrales ──────────────────────────────────────────────────────────────────
# Si PyMuPDF extrae menos de este ratio de caracteres por página,
# asumimos que el PDF es una imagen escaneada y caemos al OCR.
MIN_CHARS_PER_PAGE = 50


# ── Modelos de datos ──────────────────────────────────────────────────────────

@dataclass
class ExtractedPage:
    """Texto extraído de una sola página del PDF."""
    page_number: int
    text: str
    method: str          # "pymupdf" | "pdfplumber" | "ocr"
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ExtractedDocument:
    """Resultado completo de la extracción de un PDF."""
    pdf_path: str
    doc_id: str
    pages: list[ExtractedPage] = field(default_factory=list)
    total_pages: int = 0
    extraction_method: str = ""   # método predominante usado
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Texto completo del documento, todas las páginas unidas."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def success(self) -> bool:
        return bool(self.full_text.strip())


# ── Extracción con PyMuPDF ────────────────────────────────────────────────────

def _extract_pymupdf(pdf_path: Path) -> list[ExtractedPage]:
    """Extrae texto con PyMuPDF preservando layout."""
    pages = []
    doc = fitz.open(str(pdf_path))

    for i, page in enumerate(doc, start=1):
        # "text" preserva layout; "rawtext" es más básico
        text = page.get_text("text")
        pages.append(ExtractedPage(
            page_number=i,
            text=text,
            method="pymupdf",
        ))

    doc.close()
    return pages


# ── Extracción con pdfplumber ─────────────────────────────────────────────────

def _extract_pdfplumber(pdf_path: Path) -> list[ExtractedPage]:
    """
    Extrae texto con pdfplumber. Mejor para PDFs con tablas
    o múltiples columnas (común en la Gaceta Oficial).
    """
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            pages.append(ExtractedPage(
                page_number=i,
                text=text,
                method="pdfplumber",
            ))
    return pages


# ── Selector de método ────────────────────────────────────────────────────────

def _is_scanned_page(page: ExtractedPage) -> bool:
    """
    Determina si una página es imagen escaneada (sin texto extraíble).
    """
    return page.char_count < MIN_CHARS_PER_PAGE


def _merge_best_pages(
    pymupdf_pages: list[ExtractedPage],
    pdfplumber_pages: list[ExtractedPage],
) -> list[ExtractedPage]:
    """
    Para cada página, elige el mejor resultado entre PyMuPDF y pdfplumber.
    Gana el que extrajo más texto.
    """
    result = []
    for pm_page, pp_page in zip(pymupdf_pages, pdfplumber_pages):
        best = pm_page if pm_page.char_count >= pp_page.char_count else pp_page
        result.append(best)
    return result


# ── Extractor principal ───────────────────────────────────────────────────────

def extract_pdf(pdf_path: str | Path, doc_id: str = "") -> ExtractedDocument:
    """
    Extrae texto de un PDF usando la estrategia en cascada:
    PyMuPDF → pdfplumber → OCR.

    Args:
        pdf_path: Ruta al archivo PDF.
        doc_id: Identificador del documento (ej: "ley_1234").

    Returns:
        ExtractedDocument con texto limpio por página.
    """
    pdf_path = Path(pdf_path)
    doc_id = doc_id or pdf_path.stem

    if not pdf_path.exists():
        logger.error(f"PDF no encontrado: {pdf_path}")
        return ExtractedDocument(pdf_path=str(pdf_path), doc_id=doc_id)

    logger.info(f"Extrayendo texto: {pdf_path.name}")
    result = ExtractedDocument(
        pdf_path=str(pdf_path),
        doc_id=doc_id,
    )

    try:
        # Paso 1: PyMuPDF
        pymupdf_pages = _extract_pymupdf(pdf_path)
        result.total_pages = len(pymupdf_pages)

        # Paso 2: pdfplumber (en paralelo conceptual)
        pdfplumber_pages = _extract_pdfplumber(pdf_path)

        # Alinear longitudes por si difieren
        min_len = min(len(pymupdf_pages), len(pdfplumber_pages))
        pymupdf_pages = pymupdf_pages[:min_len]
        pdfplumber_pages = pdfplumber_pages[:min_len]

        # Elegir el mejor para cada página
        merged_pages = _merge_best_pages(pymupdf_pages, pdfplumber_pages)

        # Paso 3: OCR para páginas que quedaron vacías (escaneadas)
        final_pages = []
        ocr_used = False

        for page in merged_pages:
            if _is_scanned_page(page):
                logger.warning(
                    f"Página {page.page_number} sin texto suficiente "
                    f"({page.char_count} chars). Aplicando OCR..."
                )
                ocr_text = extract_with_ocr(pdf_path, page_number=page.page_number)
                final_pages.append(ExtractedPage(
                    page_number=page.page_number,
                    text=ocr_text,
                    method="ocr",
                ))
                ocr_used = True
            else:
                final_pages.append(page)

        # Limpiar texto de cada página
        for page in final_pages:
            page.text = clean_text(page.text)

        result.pages = final_pages
        result.extraction_method = "ocr" if ocr_used else merged_pages[0].method if merged_pages else "none"

        logger.success(
            f"Extraído: {doc_id} | {result.total_pages} páginas | "
            f"método: {result.extraction_method} | "
            f"{len(result.full_text)} chars totales"
        )

    except Exception as e:
        logger.error(f"Error extrayendo {pdf_path}: {e}")

    return result


def extract_many(pdf_paths: list[str | Path]) -> list[ExtractedDocument]:
    """Extrae texto de múltiples PDFs secuencialmente."""
    results = []
    for path in pdf_paths:
        doc = extract_pdf(path)
        if doc.success:
            results.append(doc)
        else:
            logger.warning(f"Extracción fallida para: {path}")
    return results
