"""
Descarga PDFs de la Gaceta Oficial de Bolivia con reintentos,
delay configurable y verificación de integridad.
"""

import asyncio
import hashlib
from pathlib import Path

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from data_engineering.scraper.change_detector import compute_hash


RAW_PDFS_PATH = Path("data/raw_pdfs")


def _build_save_path(filename: str, subfolder: str = "") -> Path:
    """Construye la ruta de guardado del PDF."""
    target = RAW_PDFS_PATH / subfolder if subfolder else RAW_PDFS_PATH
    target.mkdir(parents=True, exist_ok=True)
    return target / filename


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def download_pdf(
    url: str,
    filename: str,
    subfolder: str = "",
    delay_seconds: float = 2.0,
) -> Path | None:
    """
    Descarga un PDF desde una URL y lo guarda en disco.

    Args:
        url: URL directa al PDF.
        filename: Nombre del archivo destino (ej: 'ley_1234.pdf').
        subfolder: Subcarpeta opcional dentro de raw_pdfs/.
        delay_seconds: Tiempo de espera antes de la descarga (cortesía al servidor).

    Returns:
        Path al archivo guardado, o None si ya existe sin cambios.
    """
    save_path = _build_save_path(filename, subfolder)

    await asyncio.sleep(delay_seconds)

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "LexiaBot/1.0 (Proyecto de Grado - UPDS Bolivia)"
            )
        }
        logger.info(f"Descargando: {url}")
        response = await client.get(url, headers=headers)
        response.raise_for_status()

        content = response.content

        # Si el archivo ya existe y es idéntico, no reescribir
        if save_path.exists():
            existing_hash = compute_hash(save_path.read_bytes())
            new_hash = compute_hash(content)
            if existing_hash == new_hash:
                logger.debug(f"Sin cambios, omitiendo: {filename}")
                return save_path

        save_path.write_bytes(content)
        logger.success(f"PDF guardado: {save_path} ({len(content) / 1024:.1f} KB)")
        return save_path


async def download_many(
    tasks: list[dict],
    delay_seconds: float = 2.0,
    max_concurrent: int = 3,
) -> list[Path | None]:
    """
    Descarga múltiples PDFs con concurrencia controlada.

    Args:
        tasks: Lista de dicts con keys 'url', 'filename', 'subfolder' (opcional).
        delay_seconds: Delay entre descargas.
        max_concurrent: Máximo de descargas simultáneas.

    Returns:
        Lista de paths de archivos descargados.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _bounded_download(task: dict) -> Path | None:
        async with semaphore:
            return await download_pdf(
                url=task["url"],
                filename=task["filename"],
                subfolder=task.get("subfolder", ""),
                delay_seconds=delay_seconds,
            )

    results = await asyncio.gather(
        *[_bounded_download(t) for t in tasks],
        return_exceptions=True,
    )

    successful = [r for r in results if isinstance(r, Path)]
    failed = [r for r in results if isinstance(r, Exception)]

    logger.info(f"Descargados: {len(successful)} | Fallidos: {len(failed)}")
    for err in failed:
        logger.error(f"Error en descarga: {err}")

    return results
