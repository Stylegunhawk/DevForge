# src/storage/file_store.py
"""Upload file store abstraction.

Resolves upload file URLs to raw bytes regardless of backend (local disk,
S3, MongoDB GridFS). The single entry point is `read_upload_url(url)`.

Adding a new backend (S3, MongoDB) requires only:
  1. Subclass FileStore and implement can_handle / read_bytes
  2. Append an instance to _STORE_REGISTRY

No changes are needed in the agent, tools, or router layers.

Current backends
----------------
LocalFileStore  — active; reads from ./data/ (the StaticFiles mount)

Planned backends (not yet implemented)
---------------------------------------
S3FileStore     — activate when UPLOAD_FILE_BACKEND="s3"; uses boto3
MongoFileStore  — activate when UPLOAD_FILE_BACKEND="mongodb"; uses GridFS
"""
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Maximum file size accepted by the GitHub Contents API.
_MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB

# Mirrors the StaticFiles mount in src/main.py:
#   app.mount("/static", StaticFiles(directory="data"), name="static")
# If you change the mount path or directory, update these two constants.
_STATIC_URL_PREFIX = "/static"
_STATIC_DISK_ROOT = Path(os.environ.get("STATIC_DISK_ROOT", "./data"))


class FileStore(ABC):
    """Abstract interface for resolving upload file URLs to raw bytes."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this store owns the given URL."""

    @abstractmethod
    def read_bytes(self, url: str) -> Optional[bytes]:
        """Return file bytes for url, or None if the file cannot be found.

        Raises:
            ValueError: if the file exceeds _MAX_FILE_BYTES.
        """


class LocalFileStore(FileStore):
    """Resolves FILE_BASE_URL upload URLs to local disk paths.

    Identifies ownership by comparing the URL's origin (scheme + netloc)
    against settings.FILE_BASE_URL. When they match it maps
    /static/{path} → ./data/{path} — the same StaticFiles mount as main.py.
    No HTTP requests are made; the file is read directly from disk.

    Works for:
      • Local dev  (FILE_BASE_URL = http://localhost:8001/static/uploads)
      • Docker     (FILE_BASE_URL = http://api:8001/static/uploads)

    Does NOT match when FILE_BASE_URL points to an external CDN/S3 bucket,
    so those URLs fall through to the HTTP fetch path (with SSRF guard).
    """

    def _base_origin(self) -> str:
        """Return the scheme+netloc of FILE_BASE_URL from settings."""
        try:
            from src.core.config import settings
            p = urlparse(settings.FILE_BASE_URL)
            return f"{p.scheme}://{p.netloc}"
        except Exception:
            return ""

    def can_handle(self, url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            url_origin = f"{parsed.scheme}://{parsed.netloc}"
            base_origin = self._base_origin()
            return (
                bool(url_origin)
                and bool(base_origin)
                and url_origin == base_origin
                and parsed.path.startswith(_STATIC_URL_PREFIX + "/")
            )
        except Exception:
            return False

    def read_bytes(self, url: str) -> Optional[bytes]:
        try:
            parsed = urlparse(url)
            # Strip /static prefix → path relative to ./data/
            relative = parsed.path[len(_STATIC_URL_PREFIX):].lstrip("/")

            data_root = _STATIC_DISK_ROOT.resolve()
            candidate = (data_root / relative).resolve()

            # Path traversal guard using pathlib (more robust than startswith)
            try:
                candidate.relative_to(data_root)
            except ValueError:
                logger.warning("Blocked path traversal in upload URL: %s → %s", url, candidate)
                return None

            if not candidate.is_file():
                logger.warning("LocalFileStore: file not found on disk: %s → %s", url, candidate)
                return None

            content = candidate.read_bytes()
            if len(content) > _MAX_FILE_BYTES:
                raise ValueError(
                    f"File too large: {len(content):,} bytes (GitHub limit is 100 MB)"
                )
            logger.info("LocalFileStore: read %d bytes from %s", len(content), candidate)
            return content

        except ValueError:
            raise
        except Exception as exc:
            logger.warning("LocalFileStore.read_bytes failed for %s: %s", url, exc)
            return None


# ---------------------------------------------------------------------------
# Future backends — implement FileStore and append to this list to activate.
# ---------------------------------------------------------------------------
#
# class S3FileStore(FileStore):
#     """Read from AWS S3 via boto3. Set UPLOAD_FILE_BACKEND=s3."""
#     def can_handle(self, url: str) -> bool:
#         return url.startswith("s3://") or ".s3.amazonaws.com" in url
#     def read_bytes(self, url: str) -> Optional[bytes]:
#         import boto3, io
#         from src.core.config import settings
#         s3 = boto3.client("s3")
#         bucket, key = _parse_s3_url(url)
#         buf = io.BytesIO()
#         s3.download_fileobj(bucket, key, buf)
#         return buf.getvalue()
#
# class MongoFileStore(FileStore):
#     """Read from MongoDB GridFS. Set UPLOAD_FILE_BACKEND=mongodb."""
#     def can_handle(self, url: str) -> bool:
#         return url.startswith("gridfs://")
#     def read_bytes(self, url: str) -> Optional[bytes]:
#         from motor.motor_asyncio import AsyncIOMotorGridFSBucket
#         ...
#
# ---------------------------------------------------------------------------

# Active store registry — tried in order; first match wins.
_STORE_REGISTRY: list[FileStore] = [
    LocalFileStore(),
    # S3FileStore(),
    # MongoFileStore(),
]


def read_upload_url(url: str) -> Optional[bytes]:
    """Resolve a file URL to bytes using the first matching store.

    Returns None when no store claims the URL (i.e. it is an external /
    remote URL and should be fetched via the SSRF-guarded HTTP path in
    _safe_fetch_url).

    This is the only function that agent and tool code should call.
    Storage backend changes are transparent to all callers.
    """
    for store in _STORE_REGISTRY:
        if store.can_handle(url):
            return store.read_bytes(url)
    return None
