"""
Detecta si un documento de la Gaceta Oficial ha cambiado
comparando el hash MD5 de la URL o contenido contra el
registro guardado en checkpoints.
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime

from loguru import logger


CHECKPOINTS_FILE = Path("data/checkpoints/hashes.json")


def _load_checkpoints() -> dict:
    """Carga el archivo de hashes guardados."""
    if not CHECKPOINTS_FILE.exists():
        CHECKPOINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        return {}
    with open(CHECKPOINTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_checkpoints(data: dict) -> None:
    """Persiste el diccionario de hashes en disco."""
    with open(CHECKPOINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def compute_hash(content: str | bytes) -> str:
    """Calcula MD5 de un contenido (texto o bytes)."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.md5(content).hexdigest()


def has_changed(document_id: str, new_hash: str) -> bool:
    """
    Devuelve True si el documento cambió respecto al checkpoint guardado,
    o si es la primera vez que se ve.
    """
    checkpoints = _load_checkpoints()
    old_hash = checkpoints.get(document_id, {}).get("hash")
    return old_hash != new_hash


def update_checkpoint(document_id: str, new_hash: str, metadata: dict = None) -> None:
    """Actualiza el hash guardado para un documento."""
    checkpoints = _load_checkpoints()
    checkpoints[document_id] = {
        "hash": new_hash,
        "last_seen": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    }
    _save_checkpoints(checkpoints)
    logger.debug(f"Checkpoint actualizado: {document_id}")


def get_all_checkpoints() -> dict:
    """Devuelve todos los checkpoints guardados."""
    return _load_checkpoints()
