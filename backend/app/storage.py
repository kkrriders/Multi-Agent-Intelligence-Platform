from pathlib import Path

from app.config import settings


def _resolve(storage_path: str) -> Path:
    root = Path(settings.document_storage_dir).resolve()
    target = (root / storage_path).resolve()
    if root not in target.parents:
        raise ValueError("storage path escapes the storage root")
    return target


def save(storage_path: str, content: bytes) -> None:
    target = _resolve(storage_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def delete(storage_path: str) -> None:
    _resolve(storage_path).unlink(missing_ok=True)
