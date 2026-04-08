"""
Fallback OCR usando Tesseract para PDFs escaneados (solo imagen).
Convierte cada página a imagen y aplica reconocimiento de caracteres
con configuración optimizada para español.
"""

from pathlib import Path

import fitz  # PyMuPDF - para convertir páginas a imagen
import pytesseract
from PIL import Image
from loguru import logger


# Configuración de Tesseract para español boliviano
TESSERACT_CONFIG = "--oem 3 --psm 6 -l spa"
# oem 3 = LSTM + legacy (más preciso)
# psm 6 = bloque uniforme de texto (típico en leyes)
# spa = español

# Resolución de render (mayor = mejor OCR, más lento)
RENDER_DPI = 300


def _page_to_image(pdf_path: Path, page_number: int) -> Image.Image:
    """
    Convierte una página de PDF a imagen PIL para procesar con OCR.

    Args:
        pdf_path: Ruta al PDF.
        page_number: Número de página (1-indexed).
    """
    doc = fitz.open(str(pdf_path))
    page = doc[page_number - 1]  # fitz es 0-indexed

    # Renderizar a alta resolución
    matrix = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    doc.close()

    # Convertir a PIL Image
    img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    return img


def extract_with_ocr(pdf_path: Path, page_number: int) -> str:
    """
    Aplica OCR a una página específica del PDF.

    Args:
        pdf_path: Ruta al PDF.
        page_number: Número de página (1-indexed).

    Returns:
        Texto extraído por OCR.
    """
    try:
        img = _page_to_image(pdf_path, page_number)
        text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
        logger.debug(
            f"OCR página {page_number}: {len(text)} chars extraídos"
        )
        return text

    except Exception as e:
        logger.error(f"Error OCR en página {page_number} de {pdf_path}: {e}")
        return ""


def extract_full_pdf_ocr(pdf_path: Path) -> str:
    """
    Aplica OCR a todas las páginas de un PDF.
    Usar cuando el PDF es 100% imagen escaneada.
    """
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    full_text = []
    for page_num in range(1, total_pages + 1):
        text = extract_with_ocr(pdf_path, page_num)
        if text.strip():
            full_text.append(f"[Página {page_num}]\n{text}")

    return "\n\n".join(full_text)
