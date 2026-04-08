"""
Parser de documentos legales bolivianos.
Convierte texto limpio en estructura JSON por artículo,
detecta referencias cruzadas y derogaciones.
"""

import re
from dataclasses import dataclass, field
from loguru import logger


# ── Patrones regex para leyes bolivianas ──────────────────────────────────────

# Encabezados de artículos: "Artículo 1.", "ARTÍCULO 23.-", "Art. 5°"
ARTICLE_PATTERN = re.compile(
    r"(?:ARTÍCULO|Artículo|ART\.?|Art\.?)\s*(\d+)[°\.\-\s]",
    re.IGNORECASE,
)

# Encabezados de capítulos
CHAPTER_PATTERN = re.compile(
    r"(?:CAPÍTULO|Capítulo)\s+([IVXLCDM]+|\d+)[\.\-\s]*(.*?)$",
    re.IGNORECASE | re.MULTILINE,
)

# Encabezados de título
TITLE_PATTERN = re.compile(
    r"(?:TÍTULO|Título)\s+([IVXLCDM]+|\d+)[\.\-\s]*(.*?)$",
    re.IGNORECASE | re.MULTILINE,
)

# Referencias cruzadas: "véase el Artículo 23", "conforme al Art. 5"
CROSS_REFERENCE_PATTERN = re.compile(
    r"(?:véase|conforme|según|establece|dispone|previsto en|señalado en)?\s*"
    r"(?:el\s+)?(?:Artículo|Art\.?)\s*(\d+)",
    re.IGNORECASE,
)

# Derogaciones: "queda derogado el Artículo 5", "deróguese el Art. 10"
DEROGATION_PATTERN = re.compile(
    r"(?:queda\s+derogad[ao]|deróguese|se\s+deroga)\s+"
    r"(?:el\s+)?(?:Artículo|Art\.?)\s*(\d+)",
    re.IGNORECASE,
)

# Modificaciones: "modifícase el Artículo 3", "se modifica el Art. 7"
MODIFICATION_PATTERN = re.compile(
    r"(?:modifícase|se\s+modifica)\s+"
    r"(?:el\s+)?(?:Artículo|Art\.?)\s*(\d+)",
    re.IGNORECASE,
)

# Número de ley/decreto en el texto
LAW_NUMBER_PATTERN = re.compile(
    r"(?:Ley\s+N[°º]?\s*|Decreto\s+Supremo\s+N[°º]?\s*)(\d+)",
    re.IGNORECASE,
)


# ── Modelos de datos ──────────────────────────────────────────────────────────

@dataclass
class LegalArticle:
    """Representa un artículo individual de una ley boliviana."""
    article_number: int
    text: str
    chapter: str = ""
    title_section: str = ""
    cross_references: list[int] = field(default_factory=list)   # artículos mencionados
    derogates: list[int] = field(default_factory=list)          # artículos que deroga
    modifies: list[int] = field(default_factory=list)           # artículos que modifica
    is_derogated: bool = False
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)

    def to_dict(self) -> dict:
        return {
            "article_number": self.article_number,
            "text": self.text,
            "chapter": self.chapter,
            "title_section": self.title_section,
            "cross_references": self.cross_references,
            "derogates": self.derogates,
            "modifies": self.modifies,
            "is_derogated": self.is_derogated,
            "char_count": self.char_count,
        }


@dataclass
class ParsedLaw:
    """Ley completa parseada con todos sus artículos."""
    doc_id: str
    tipo: str                           # ley / decreto_supremo / etc.
    numero: str
    titulo: str
    fecha_publicacion: str
    areas: list[str] = field(default_factory=list)
    articles: list[LegalArticle] = field(default_factory=list)
    referenced_laws: list[str] = field(default_factory=list)   # otras leyes citadas
    total_articles: int = 0

    def __post_init__(self):
        self.total_articles = len(self.articles)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "tipo": self.tipo,
            "numero": self.numero,
            "titulo": self.titulo,
            "fecha_publicacion": self.fecha_publicacion,
            "areas": self.areas,
            "total_articles": self.total_articles,
            "referenced_laws": self.referenced_laws,
            "articles": [a.to_dict() for a in self.articles],
        }


# ── Funciones de parsing ──────────────────────────────────────────────────────

def _split_by_articles(text: str) -> list[tuple[int, str]]:
    """
    Divide el texto en segmentos por artículo.

    Returns:
        Lista de (número_artículo, texto_del_artículo)
    """
    segments = []
    matches = list(ARTICLE_PATTERN.finditer(text))

    for i, match in enumerate(matches):
        article_num = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        article_text = text[start:end].strip()
        segments.append((article_num, article_text))

    return segments


def _extract_chapter(text: str, position: int, full_text: str) -> str:
    """Encuentra el capítulo al que pertenece un artículo por posición."""
    # Buscar el último capítulo antes de la posición del artículo
    chapters = list(CHAPTER_PATTERN.finditer(full_text[:position]))
    if chapters:
        last = chapters[-1]
        chapter_title = last.group(2).strip() if last.group(2) else ""
        return f"Capítulo {last.group(1)} {chapter_title}".strip()
    return ""


def _extract_title_section(text: str, position: int, full_text: str) -> str:
    """Encuentra el título al que pertenece un artículo por posición."""
    titles = list(TITLE_PATTERN.finditer(full_text[:position]))
    if titles:
        last = titles[-1]
        title_text = last.group(2).strip() if last.group(2) else ""
        return f"Título {last.group(1)} {title_text}".strip()
    return ""


def _parse_article(
    article_num: int,
    article_text: str,
    position: int,
    full_text: str,
) -> LegalArticle:
    """Parsea un artículo individual extrayendo relaciones y metadata."""

    # Referencias cruzadas a otros artículos
    cross_refs = [
        int(m.group(1))
        for m in CROSS_REFERENCE_PATTERN.finditer(article_text)
        if int(m.group(1)) != article_num  # no auto-referencia
    ]

    # Artículos que este artículo deroga
    derogates = [int(m.group(1)) for m in DEROGATION_PATTERN.finditer(article_text)]

    # Artículos que este artículo modifica
    modifies = [int(m.group(1)) for m in MODIFICATION_PATTERN.finditer(article_text)]

    chapter = _extract_chapter(article_text, position, full_text)
    title_section = _extract_title_section(article_text, position, full_text)

    return LegalArticle(
        article_number=article_num,
        text=article_text,
        chapter=chapter,
        title_section=title_section,
        cross_references=list(set(cross_refs)),
        derogates=list(set(derogates)),
        modifies=list(set(modifies)),
    )


def _find_referenced_laws(full_text: str) -> list[str]:
    """Encuentra otras leyes/decretos citados en el documento."""
    return list(set(LAW_NUMBER_PATTERN.findall(full_text)))


def _mark_derogated_articles(articles: list[LegalArticle]) -> None:
    """Marca artículos como derogados si algún otro artículo los deroga."""
    derogated_nums = set()
    for article in articles:
        derogated_nums.update(article.derogates)

    for article in articles:
        if article.article_number in derogated_nums:
            article.is_derogated = True


# ── Parser principal ──────────────────────────────────────────────────────────

def parse_law(
    full_text: str,
    doc_id: str,
    tipo: str = "ley",
    numero: str = "",
    titulo: str = "",
    fecha_publicacion: str = "",
    areas: list[str] = None,
) -> ParsedLaw:
    """
    Parsea el texto completo de una ley y retorna estructura JSON.

    Args:
        full_text: Texto limpio del documento completo.
        doc_id: Identificador único (ej: "ley_1234").
        tipo: Tipo de documento (ley/decreto_supremo/etc.).
        numero: Número de la ley/decreto.
        titulo: Título del documento.
        fecha_publicacion: Fecha de publicación.
        areas: Áreas legales detectadas.

    Returns:
        ParsedLaw con todos los artículos y relaciones.
    """
    logger.info(f"Parseando: {doc_id} | {len(full_text)} chars")

    if not full_text.strip():
        logger.warning(f"Texto vacío para: {doc_id}")
        return ParsedLaw(doc_id=doc_id, tipo=tipo, numero=numero,
                         titulo=titulo, fecha_publicacion=fecha_publicacion)

    # Dividir por artículos
    article_segments = _split_by_articles(full_text)

    if not article_segments:
        logger.warning(f"No se encontraron artículos en: {doc_id}")
        # Crear un artículo único con todo el texto
        article_segments = [(0, full_text)]

    # Parsear cada artículo
    articles = []
    for article_num, article_text in article_segments:
        position = full_text.find(article_text)
        article = _parse_article(article_num, article_text, position, full_text)
        articles.append(article)

    # Marcar artículos derogados
    _mark_derogated_articles(articles)

    # Encontrar leyes referenciadas
    referenced_laws = _find_referenced_laws(full_text)

    parsed = ParsedLaw(
        doc_id=doc_id,
        tipo=tipo,
        numero=numero,
        titulo=titulo,
        fecha_publicacion=fecha_publicacion,
        areas=areas or [],
        articles=articles,
        referenced_laws=referenced_laws,
    )

    logger.success(
        f"Parseado: {doc_id} | {parsed.total_articles} artículos | "
        f"{len(referenced_laws)} leyes referenciadas"
    )
    return parsed
