"""
Scraper de la Gaceta Oficial de Bolivia.
URL real: http://www.gacetaoficialdebolivia.gob.bo

El sitio usa Drupal 10 con HTML server-side (NO necesita Playwright).
Usamos httpx + BeautifulSoup directamente.

Estructura del sitio:
  Leyes:      /normas/listadonor/10/page:{N}
  Decretos:   /normas/listadonor/11/page:{N}
  Resoluc.:   /normas/listadonor/16/page:{N}
  PDF:        /normas/descargarNrms/{ID}
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from data_engineering.scraper.change_detector import (
    compute_hash,
    has_changed,
    update_checkpoint,
)
from data_engineering.scraper.downloader import download_many


# ── Configuración ──────────────────────────────────────────────────────────────

GACETA_BASE_URL = "http://www.gacetaoficialdebolivia.gob.bo"

DOCUMENT_SECTIONS = {
    "ley":                  "/normas/listadonor/10",
    "decreto_supremo":      "/normas/listadonor/11",
    "resolucion_suprema":   "/normas/listadonor/16",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "LexiaBot/1.0 (Proyecto de Grado UPDS Bolivia)"
    ),
    "Accept-Language": "es-BO,es;q=0.9",
}

AREA_KEYWORDS = {
    "penal":          ["penal", "delito", "crimen", "sanción", "código penal"],
    "civil":          ["civil", "contrato", "propiedad", "sucesión", "familia"],
    "laboral":        ["laboral", "trabajo", "empleador", "trabajador", "salario"],
    "tránsito":       ["tránsito", "transporte", "vehículo", "conductor"],
    "comercial":      ["comercial", "empresa", "sociedad", "mercantil"],
    "administrativo": ["administrativo", "estado", "gobierno", "municipal"],
    "constitucional": ["constitución", "derechos", "garantías"],
    "tributario":     ["tributario", "impuesto", "renta", "aduana"],
}


# ── Modelos ────────────────────────────────────────────────────────────────────

@dataclass
class GacetaDocument:
    doc_id: str
    tipo: str
    titulo: str
    numero: str
    fecha_publicacion: str
    url_detalle: str
    url_pdf: str | None = None
    areas_detectadas: list[str] = field(default_factory=list)
    hash_actual: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _detect_areas(text: str) -> list[str]:
    text_lower = text.lower()
    return [
        area for area, kws in AREA_KEYWORDS.items()
        if any(kw in text_lower for kw in kws)
    ]


async def _fetch_html(url: str, client: httpx.AsyncClient) -> str | None:
    """Descarga HTML de una URL con manejo de errores."""
    try:
        await asyncio.sleep(1.5)  # cortesía al servidor
        response = await client.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"Error fetch {url}: {e}")
        return None


# ── Parser de listado ──────────────────────────────────────────────────────────

def _parse_listing(html: str, tipo: str) -> list[GacetaDocument]:
    """
    Parsea la página de listado de normas.
    Estructura HTML real de gacetaoficialdebolivia.gob.bo
    """
    soup = BeautifulSoup(html, "lxml")
    documents = []

    # Buscar filas de normas — el sitio usa tablas o divs con clase 'views-row'
    rows = soup.select("table tbody tr, .views-row, .norma-item")

    # Fallback: buscar todos los links que apuntan a /normas/verGratis_gob/
    if not rows:
        links = soup.find_all("a", href=re.compile(r"/normas/verGratis_gob/\d+"))
        for link in links:
            try:
                url_detalle = GACETA_BASE_URL + link["href"]
                # Extraer ID del URL
                match = re.search(r"/(\d+)$", link["href"])
                if not match:
                    continue
                doc_id_num = match.group(1)
                titulo = link.get_text(strip=True) or f"{tipo}_{doc_id_num}"

                # Buscar número en el texto del link o alrededor
                numero = ""
                num_match = re.search(r"[Nn][°º]?\s*(\d+)", titulo)
                if num_match:
                    numero = num_match.group(1)

                doc_id = f"{tipo}_{doc_id_num}"
                areas = _detect_areas(titulo)
                url_pdf = f"{GACETA_BASE_URL}/normas/descargarNrms/{doc_id_num}"

                documents.append(GacetaDocument(
                    doc_id=doc_id,
                    tipo=tipo,
                    titulo=titulo,
                    numero=numero,
                    fecha_publicacion="",
                    url_detalle=url_detalle,
                    url_pdf=url_pdf,
                    areas_detectadas=areas,
                ))
            except Exception as e:
                logger.debug(f"Error parseando link: {e}")
                continue
        return documents

    # Si hay filas de tabla
    for row in rows:
        try:
            link = row.find("a", href=re.compile(r"/normas/verGratis_gob/\d+"))
            if not link:
                # Buscar link de descarga PDF directa
                link = row.find("a", href=re.compile(r"/normas/descargarNrms/\d+"))
            if not link:
                continue

            href = link["href"]
            match = re.search(r"/(\d+)$", href)
            if not match:
                continue
            doc_id_num = match.group(1)

            titulo = link.get_text(strip=True)
            if not titulo:
                titulo_tag = row.find(["td", "div", "span"], class_=re.compile(r"titulo|nombre|title"))
                titulo = titulo_tag.get_text(strip=True) if titulo_tag else f"{tipo}_{doc_id_num}"

            numero = ""
            num_match = re.search(r"[Nn][°º]?\s*(\d+)", titulo)
            if num_match:
                numero = num_match.group(1)

            fecha = ""
            fecha_tag = row.find(["td", "span"], class_=re.compile(r"fecha|date"))
            if fecha_tag:
                fecha = fecha_tag.get_text(strip=True)

            doc_id = f"{tipo}_{doc_id_num}"
            areas = _detect_areas(titulo)
            url_pdf = f"{GACETA_BASE_URL}/normas/descargarNrms/{doc_id_num}"
            url_detalle = f"{GACETA_BASE_URL}/normas/verGratis_gob/{doc_id_num}"

            documents.append(GacetaDocument(
                doc_id=doc_id,
                tipo=tipo,
                titulo=titulo,
                numero=numero,
                fecha_publicacion=fecha,
                url_detalle=url_detalle,
                url_pdf=url_pdf,
                areas_detectadas=areas,
            ))
        except Exception as e:
            logger.debug(f"Error parseando fila: {e}")
            continue

    return documents


# ── Scraper principal ──────────────────────────────────────────────────────────

async def scrape_gaceta(
    sections: list[str] | None = None,
    max_pages: int = 5,
    delay_seconds: float = 1.5,
) -> list[GacetaDocument]:
    """
    Scrapea la Gaceta Oficial usando httpx (sin navegador).
    Detecta documentos nuevos comparando hashes.
    """
    target_sections = {
        k: v for k, v in DOCUMENT_SECTIONS.items()
        if sections is None or k in sections
    }

    new_or_changed: list[GacetaDocument] = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for tipo, path in target_sections.items():
            logger.info(f"Scrapeando sección: {tipo}")

            for page_num in range(1, max_pages + 1):
                # Paginación real: /normas/listadonor/10/page:{N}
                if page_num == 1:
                    url = f"{GACETA_BASE_URL}{path}"
                else:
                    url = f"{GACETA_BASE_URL}{path}/page:{page_num}"

                html = await _fetch_html(url, client)
                if not html:
                    logger.warning(f"No se pudo obtener: {url}")
                    break

                page_hash = compute_hash(html)
                page_id = f"listing_{tipo}_page{page_num}"

                if not has_changed(page_id, page_hash):
                    logger.debug(f"Sin cambios en: {page_id}")
                    break

                documents = _parse_listing(html, tipo)
                if not documents:
                    logger.info(f"Sin documentos en página {page_num}, fin de sección.")
                    break

                logger.info(f"  {tipo} pág.{page_num}: {len(documents)} documentos encontrados")

                for doc in documents:
                    doc_hash = compute_hash(doc.url_pdf or doc.doc_id)
                    if has_changed(doc.doc_id, doc_hash):
                        doc.hash_actual = doc_hash
                        new_or_changed.append(doc)

                update_checkpoint(page_id, page_hash)

    logger.success(f"Scraping completo: {len(new_or_changed)} documentos nuevos/modificados")
    return new_or_changed


async def run_scraper_and_download(
    sections: list[str] | None = None,
    max_pages: int = 5,
    delay_seconds: float = 1.5,
) -> list[dict]:
    """Pipeline completo: scraping + descarga de PDFs + checkpoints."""
    documents = await scrape_gaceta(sections, max_pages, delay_seconds)

    if not documents:
        logger.info("No hay documentos nuevos.")
        return []

    # Descargar PDFs
    download_tasks = [
        {
            "url": doc.url_pdf,
            "filename": f"{doc.doc_id}.pdf",
            "subfolder": doc.tipo,
        }
        for doc in documents if doc.url_pdf
    ]

    if download_tasks:
        await download_many(download_tasks, delay_seconds=delay_seconds)

    # Actualizar checkpoints y retornar metadata
    results = []
    for doc in documents:
        if doc.hash_actual:
            update_checkpoint(doc.doc_id, doc.hash_actual, metadata={
                "tipo": doc.tipo,
                "titulo": doc.titulo,
                "numero": doc.numero,
                "fecha": doc.fecha_publicacion,
                "url": doc.url_detalle,
                "areas": doc.areas_detectadas,
            })
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


if __name__ == "__main__":
    import sys
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    results = asyncio.run(run_scraper_and_download(
        sections=["ley"],
        max_pages=2,
    ))
    logger.info(f"Total: {len(results)} documentos")
    for r in results[:5]:
        logger.info(f"  → {r['tipo']} | {r['titulo'][:60]}")
