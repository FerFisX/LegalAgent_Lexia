"""
Limpieza de texto extraído de PDFs legales bolivianos.
Elimina artefactos de extracción, normaliza espacios,
quita headers/footers repetitivos y estandariza el texto.
"""

import re
from loguru import logger


# Patrones de headers/footers comunes en la Gaceta Oficial Bolivia
GACETA_HEADER_PATTERNS = [
    r"GACETA\s+OFICIAL\s+DEL?\s+ESTADO\s+PLURINACIONAL\s+DE\s+BOLIVIA",
    r"Estado\s+Plurinacional\s+de\s+Bolivia",
    r"Ministerio\s+de\s+la\s+Presidencia",
    r"Órgano\s+Ejecutivo",
    r"Página\s+\d+\s+de\s+\d+",
    r"^\s*\d+\s*$",           # Números de página solos
    r"^\s*-\s*\d+\s*-\s*$",  # - N -
]

# Caracteres que suelen aparecer como basura en PDFs
GARBAGE_PATTERNS = [
    r"\x00",                   # null bytes
    r"[\x01-\x08\x0b-\x0c\x0e-\x1f]",  # control chars
    r"_{3,}",                  # separadores de guión bajo
    r"-{3,}",                  # líneas de guiones
    r"={3,}",                  # líneas de iguales
    r"\*{3,}",                 # asteriscos repetidos
]


def _remove_headers_footers(text: str) -> str:
    """Elimina headers y footers típicos de la Gaceta Oficial."""
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        skip = False
        for pattern in GACETA_HEADER_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                skip = True
                break
        if not skip:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _remove_garbage(text: str) -> str:
    """Elimina caracteres basura y artefactos de extracción."""
    for pattern in GARBAGE_PATTERNS:
        text = re.sub(pattern, " ", text)
    return text


def _normalize_whitespace(text: str) -> str:
    """Normaliza espacios, tabs y saltos de línea."""
    # Múltiples espacios → uno solo
    text = re.sub(r" {2,}", " ", text)
    # Más de 2 saltos de línea seguidos → máximo 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Espacios al inicio/fin de cada línea
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines)


def _fix_hyphenation(text: str) -> str:
    """
    Corrige palabras partidas por guión al final de línea,
    común en PDFs de documentos oficiales.
    Ej: "consti-\ntución" → "constitución"
    """
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)


def _normalize_legal_abbreviations(text: str) -> str:
    """
    Normaliza abreviaciones comunes en leyes bolivianas.
    """
    replacements = {
        r"\bArt\.\s*": "Artículo ",
        r"\barts\.\s*": "artículos ",
        r"\bInc\.\s*": "Inciso ",
        r"\bPár\.\s*": "Párrafo ",
        r"\bNum\.\s*": "Numeral ",
        r"\bD\.S\.\s*": "Decreto Supremo ",
        r"\bD\.L\.\s*": "Decreto Ley ",
        r"\bR\.M\.\s*": "Resolución Ministerial ",
        r"\bR\.S\.\s*": "Resolución Suprema ",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    return text


def clean_text(text: str) -> str:
    """
    Pipeline completo de limpieza de texto legal extraído de PDF.

    Pasos:
    1. Eliminar headers/footers de la Gaceta
    2. Eliminar caracteres basura
    3. Corregir palabras partidas por guión
    4. Normalizar abreviaciones legales
    5. Normalizar espacios y saltos de línea

    Returns:
        Texto limpio listo para el chunker.
    """
    if not text or not text.strip():
        return ""

    original_len = len(text)

    text = _remove_headers_footers(text)
    text = _remove_garbage(text)
    text = _fix_hyphenation(text)
    text = _normalize_legal_abbreviations(text)
    text = _normalize_whitespace(text)
    text = text.strip()

    logger.debug(
        f"Limpieza: {original_len} → {len(text)} chars "
        f"({100 * (1 - len(text)/original_len):.1f}% reducido)"
    )

    return text
