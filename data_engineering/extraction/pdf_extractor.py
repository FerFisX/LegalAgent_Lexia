"""
Extractor de texto desde PDFs de la Gaceta Oficial de Bolivia.
Todos los PDFs son digitales (no escaneados), por lo que no se usa OCR.

Estrategia:
  1. PyMuPDF  → extracción principal con layout preservado
  2. pdfplumber → fallback para páginas con tablas o columnas múltiples
"""

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
from loguru import logger

from data_engineering.extraction.text_cleaner import clean_text


MIN_CHARS_PER_PAGE = 50  # si PyMuPDF extrae menos, intentar con pdfplumber


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    method: str   # "pymupdf" | "pdfplumber"
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ExtractedDocument:
    pdf_path: str
    doc_id: str
    pages: list[ExtractedPage] = field(default_factory=list)
    total_pages: int = 0
    extraction_method: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def success(self) -> bool:
        return bool(self.full_text.strip())


def _extract_pymupdf(pdf_path: Path) -> list[ExtractedPage]:
    pages = []
    doc = fitz.open(str(pdf_path))
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append(ExtractedPage(page_number=i, text=text, method="pymupdf"))
    doc.close()
    return pages


def _extract_pdfplumber(pdf_path: Path) -> list[ExtractedPage]:
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            pages.append(ExtractedPage(page_number=i, text=text, method="pdfplumber"))
    return pages


def extract_pdf(pdf_path: str | Path, doc_id: str = "") -> ExtractedDocument:
    """
    Extrae texto de un PDF digital.
    Usa PyMuPDF por defecto; pdfplumber como fallback por página
    cuando PyMuPDF extrae muy poco texto (ej: página con tablas).
    """
    pdf_path = Path(pdf_path)
    doc_id = doc_id or pdf_path.stem

    if not pdf_path.exists():
        logger.error(f"PDF no encontrado: {pdf_path}")
        return ExtractedDocument(pdf_path=str(pdf_path), doc_id=doc_id)

    logger.info(f"Extrayendo: {pdf_path.name}")

    pymupdf_pages = _extract_pymupdf(pdf_path)
    pdfplumber_pages = _extract_pdfplumber(pdf_path)

    final_pages = []
    for pm, pp in zip(pymupdf_pages, pdfplumber_pages):
        if pm.char_count >= MIN_CHARS_PER_PAGE:
            best = pm
        else:
            # Tabla o columna compleja: pdfplumber lo hace mejor
            best = pp if pp.char_count > pm.char_count else pm
        best.text = clean_text(best.text)
        final_pages.append(best)

    result = ExtractedDocument(
        pdf_path=str(pdf_path),
        doc_id=doc_id,
        pages=final_pages,
        total_pages=len(final_pages),
        extraction_method="pymupdf+pdfplumber",
    )

    logger.success(
        f"Extraído: {doc_id} | {result.total_pages} págs | {len(result.full_text)} chars"
    )
    return result


def extract_many(pdf_paths: list[str | Path]) -> list[ExtractedDocument]:
    results = []
    for path in pdf_paths:
        doc = extract_pdf(path)
        if doc.success:
            results.append(doc)
        else:
            logger.warning(f"Extracción fallida: {path}")
    return results
