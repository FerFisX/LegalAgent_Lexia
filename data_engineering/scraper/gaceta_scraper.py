"""
Scraper principal de la Gaceta Oficial de Bolivia.
Usa Playwright para renderizar el sitio (puede tener JS)
y BeautifulSoup para parsear el HTML resultante.

Detecta nuevos documentos comparando hashes y descarga
solo los que hayan cambiado o sean nuevos.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import async_playwright, Page

from data_engineering.scraper.change_detector import (
    compute_hash,
    has_changed,
    update_checkpoint,
)
from data_engineering.scraper.downloader import download_many


# ── Configuración ──────────────────────────────────────────────────────────────

GACETA_BASE_URL = "https://gacetaoficial.bo"

# Tipos de documentos que nos interesan con sus URLs de listado
DOCUMENT_SECTIONS = {
    "ley": "/leyes",
    "decreto_supremo": "/decretos-supremos",
    "decreto_presidencial": "/decretos-presidenciales",
    "resolucion_ministerial": "/resoluciones-ministeriales",
    "resolucion_suprema": "/resoluciones-supremas",
}

# Áreas legales para clasificación temprana (enriquecido luego por el parser)
AREA_KEYWORDS = {
    "penal": ["penal", "delito", "crimen", "sanción penal", "código penal"],
    "civil": ["civil", "contrato", "propiedad", "sucesión", "familia"],
    "laboral": ["laboral", "trabajo", "empleador", "trabajador", "salario", "despido"],
    "tránsito": ["tránsito", "transporte", "vehículo", "conductor", "accidente vial"],
    "comercial": ["comercial", "empresa", "sociedad", "mercantil"],
    "administrativo": ["administrativo", "estado", "gobierno", "municipal", "concesión"],
    "constitucional": ["constitución", "derechos", "garantías", "tribunal constitucional"],
    "tributario": ["tributario", "impuesto", "renta", "iva", "aduana"],
}


# ── Modelos de datos ───────────────────────────────────────────────────────────

@dataclass
class GacetaDocument:
    """Representa un documento encontrado en la Gaceta Oficial."""
    doc_id: str                    # ID único (ej: "ley_1234")
    tipo: str                      # ley / decreto_supremo / etc.
    titulo: str
    numero: str                    # Número de ley/decreto
    fecha_publicacion: str
    url_detalle: str               # URL de la página de detalle
    url_pdf: str | None = None     # URL directa al PDF
    areas_detectadas: list[str] = field(default_factory=list)
    hash_actual: str = ""


# ── Funciones de scraping ──────────────────────────────────────────────────────

async def _get_page_html(page: Page, url: str) -> str:
    """Navega a una URL y retorna el HTML renderizado."""
    await page.goto(url, wait_until="networkidle", timeout=30000)
    return await page.content()


def _detect_areas(text: str) -> list[str]:
    """Detecta áreas legales por keywords en el título/texto."""
    text_lower = text.lower()
    return [
        area
        for area, keywords in AREA_KEYWORDS.items()
        if any(kw in text_lower for kw in keywords)
    ]


def _extract_pdf_url(html: str, base_url: str) -> str | None:
    """Extrae la URL del PDF desde la página de detalle del documento."""
    soup = BeautifulSoup(html, "lxml")

    # Buscar enlaces directos a PDF
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.lower().endswith(".pdf"):
            return urljoin(base_url, href)

    # Buscar iframes con PDF embebido
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"]
        if ".pdf" in src.lower():
            return urljoin(base_url, src)

    # Buscar por texto del enlace
    for tag in soup.find_all("a", href=True):
        if any(kw in tag.get_text().lower() for kw in ["descargar", "pdf", "ver documento"]):
            return urljoin(base_url, tag["href"])

    return None


def _parse_document_list(html: str, tipo: str, base_url: str) -> list[GacetaDocument]:
    """
    Parsea el listado de documentos de una sección de la Gaceta.
    Retorna lista de GacetaDocument con metadata básica.
    """
    soup = BeautifulSoup(html, "lxml")
    documents = []

    # Buscar filas de tabla o cards de documento
    # La Gaceta Oficial Bolivia usa estructura de tabla o lista
    rows = soup.select("table tr, .documento-item, .gaceta-item, article")

    for row in rows:
        try:
            # Extraer título
            titulo_tag = row.select_one("td a, .titulo, h3, h4, .nombre-documento")
            if not titulo_tag:
                continue
            titulo = titulo_tag.get_text(strip=True)
            if not titulo or len(titulo) < 5:
                continue

            # Extraer URL de detalle
            link_tag = row.select_one("a[href]")
            if not link_tag:
                continue
            url_detalle = urljoin(base_url, link_tag["href"])

            # Extraer número de documento
            numero = ""
            numero_tag = row.select_one(".numero, .num-doc, td:nth-child(2)")
            if numero_tag:
                numero = numero_tag.get_text(strip=True)
            else:
                # Intentar extraer del título (ej: "Ley N° 1234")
                match = re.search(r"[Nn][°º]\s*(\d+)", titulo)
                if match:
                    numero = match.group(1)

            # Extraer fecha
            fecha = ""
            fecha_tag = row.select_one(".fecha, .date, td:nth-child(3)")
            if fecha_tag:
                fecha = fecha_tag.get_text(strip=True)

            # Generar ID único
            doc_id = f"{tipo}_{numero}" if numero else f"{tipo}_{hash(url_detalle)}"

            # Detectar áreas por título
            areas = _detect_areas(titulo)

            doc = GacetaDocument(
                doc_id=doc_id,
                tipo=tipo,
                titulo=titulo,
                numero=numero,
                fecha_publicacion=fecha,
                url_detalle=url_detalle,
                areas_detectadas=areas,
            )
            documents.append(doc)

        except Exception as e:
            logger.warning(f"Error parseando fila: {e}")
            continue

    return documents


# ── Scraper principal ──────────────────────────────────────────────────────────

async def scrape_gaceta(
    sections: list[str] | None = None,
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> list[GacetaDocument]:
    """
    Scraper principal. Recorre las secciones de la Gaceta Oficial,
    detecta documentos nuevos o modificados y los prepara para descarga.

    Args:
        sections: Lista de tipos a scrapear. Si None, scrapea todos.
        max_pages: Páginas máximas por sección (paginación).
        delay_seconds: Delay de cortesía entre requests.

    Returns:
        Lista de documentos con cambios detectados listos para descargar.
    """
    target_sections = {
        k: v for k, v in DOCUMENT_SECTIONS.items()
        if sections is None or k in sections
    }

    new_or_changed: list[GacetaDocument] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "LexiaBot/1.0 (Proyecto de Grado - UPDS Bolivia)"
            )
        )
        page = await context.new_page()

        for tipo, path in target_sections.items():
            logger.info(f"Scrapeando sección: {tipo}")

            for page_num in range(1, max_pages + 1):
                url = f"{GACETA_BASE_URL}{path}?page={page_num}"

                try:
                    html = await _get_page_html(page, url)
                    page_hash = compute_hash(html)

                    # Detectar si esta página del listado cambió
                    page_id = f"listing_{tipo}_page{page_num}"
                    if not has_changed(page_id, page_hash):
                        logger.debug(f"Sin cambios en listado: {page_id}")
                        break  # Si la página no cambió, las siguientes tampoco

                    documents = _parse_document_list(html, tipo, GACETA_BASE_URL)

                    if not documents:
                        logger.info(f"No se encontraron documentos en página {page_num}, fin de sección.")
                        break

                    # Para cada documento, obtener URL del PDF y verificar cambios
                    for doc in documents:
                        try:
                            detail_html = await _get_page_html(page, doc.url_detalle)
                            doc_hash = compute_hash(detail_html)

                            if has_changed(doc.doc_id, doc_hash):
                                pdf_url = _extract_pdf_url(detail_html, GACETA_BASE_URL)
                                doc.url_pdf = pdf_url
                                doc.hash_actual = doc_hash
                                new_or_changed.append(doc)
                                logger.info(f"Nuevo/Modificado: [{doc.tipo}] {doc.titulo[:60]}")

                            await asyncio.sleep(delay_seconds)

                        except Exception as e:
                            logger.error(f"Error procesando documento {doc.doc_id}: {e}")
                            continue

                    update_checkpoint(page_id, page_hash)

                except Exception as e:
                    logger.error(f"Error en página {url}: {e}")
                    break

        await browser.close()

    logger.success(f"Scraping completo. Documentos nuevos/modificados: {len(new_or_changed)}")
    return new_or_changed


async def run_scraper_and_download(
    sections: list[str] | None = None,
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> list[dict]:
    """
    Ejecuta el scraper completo: detecta cambios, descarga PDFs
    y actualiza checkpoints.

    Returns:
        Lista de dicts con metadata de cada documento procesado.
    """
    documents = await scrape_gaceta(sections, max_pages, delay_seconds)

    if not documents:
        logger.info("No hay documentos nuevos para descargar.")
        return []

    # Preparar tareas de descarga solo para docs con PDF
    download_tasks = [
        {
            "url": doc.url_pdf,
            "filename": f"{doc.doc_id}.pdf",
            "subfolder": doc.tipo,
        }
        for doc in documents
        if doc.url_pdf
    ]

    if download_tasks:
        await download_many(download_tasks, delay_seconds=delay_seconds)

    # Actualizar checkpoints de documentos procesados
    results = []
    for doc in documents:
        if doc.hash_actual:
            update_checkpoint(
                doc.doc_id,
                doc.hash_actual,
                metadata={
                    "tipo": doc.tipo,
                    "titulo": doc.titulo,
                    "numero": doc.numero,
                    "fecha": doc.fecha_publicacion,
                    "url": doc.url_detalle,
                    "areas": doc.areas_detectadas,
                },
            )
        results.append({
            "doc_id": doc.doc_id,
            "tipo": doc.tipo,
            "titulo": doc.titulo,
            "numero": doc.numero,
            "fecha": doc.fecha_publicacion,
            "pdf_path": f"data/raw_pdfs/{doc.tipo}/{doc.doc_id}.pdf" if doc.url_pdf else None,
            "areas": doc.areas_detectadas,
        })

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from loguru import logger

    logger.remove()
    logger.add(sys.stdout, level="INFO")
    logger.add("logs/scraper.log", rotation="10 MB", level="DEBUG")

    results = asyncio.run(run_scraper_and_download(max_pages=3))
    logger.info(f"Total procesados: {len(results)}")
    for r in results[:5]:
        logger.info(f"  → {r['tipo']} | {r['titulo'][:60]}")
