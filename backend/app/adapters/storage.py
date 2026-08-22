from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import get_settings


class StorageError(ValueError):
    pass


@dataclass(frozen=True)
class SignedDownload:
    url: str
    expires_at: datetime


class StorageAdapter:
    def put(self, storage_key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def get(self, storage_key: str) -> tuple[bytes, str]:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    def sign(
        self, storage_key: str, *, minutes: int = 10, download_url: str | None = None
    ) -> SignedDownload:
        raise NotImplementedError


class LocalStorageAdapter(StorageAdapter):
    """Private local files. Downloads are authorized API routes, not public URLs."""

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root) if root is not None else None

    @property
    def root(self) -> Path:
        return Path(self._root) if self._root is not None else Path(get_settings().storage_dir)

    def _path(self, storage_key: str) -> Path:
        if not storage_key or storage_key.startswith("/") or ".." in Path(storage_key).parts:
            raise StorageError("Invalid storage key.")
        root = self.root.resolve()
        path = (root / storage_key).resolve()
        if path != root and root not in path.parents:
            raise StorageError("Invalid storage key.")
        return path

    def put(self, storage_key: str, data: bytes, content_type: str) -> None:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_name(path.name + ".content-type").write_text(content_type, encoding="utf-8")

    def get(self, storage_key: str) -> tuple[bytes, str]:
        path = self._path(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        meta = path.with_name(path.name + ".content-type")
        content_type = (
            meta.read_text(encoding="utf-8").strip() if meta.is_file() else "application/octet-stream"
        )
        return path.read_bytes(), content_type

    def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        path.unlink(missing_ok=True)
        path.with_name(path.name + ".content-type").unlink(missing_ok=True)

    def sign(self, storage_key: str, *, minutes: int = 10, download_url: str | None = None) -> SignedDownload:
        del storage_key
        expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
        return SignedDownload(url=download_url or "", expires_at=expires_at)


storage_adapter: StorageAdapter = LocalStorageAdapter()
