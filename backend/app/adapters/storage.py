from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class SignedDownload:
    url: str
    expires_at: datetime


class StorageAdapter:
    def sign(self, storage_key: str, *, minutes: int = 10) -> SignedDownload:
        raise NotImplementedError


class LocalStorageAdapter(StorageAdapter):
    """Documents stay private. This only mints a placeholder expiring URL."""

    def sign(self, storage_key: str, *, minutes: int = 10) -> SignedDownload:
        expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
        return SignedDownload(url=f"/api/files/{storage_key}", expires_at=expires_at)


storage_adapter: StorageAdapter = LocalStorageAdapter()
