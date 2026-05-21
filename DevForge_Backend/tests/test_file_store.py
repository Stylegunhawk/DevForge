# tests/test_file_store.py
"""Unit tests for src/storage/file_store.py

Covers:
- LocalFileStore.can_handle  — origin matching, negative cases
- LocalFileStore.read_bytes  — happy path, missing file, traversal block, size limit
- read_upload_url             — registry dispatch, external URL passthrough
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(file_base_url: str):
    s = MagicMock()
    s.FILE_BASE_URL = file_base_url
    return s


# ---------------------------------------------------------------------------
# LocalFileStore.can_handle
# ---------------------------------------------------------------------------

class TestLocalFileStoreCanHandle:
    def test_matches_same_origin_and_static_path(self, tmp_path):
        from src.storage.file_store import LocalFileStore
        store = LocalFileStore()
        with patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            assert store.can_handle("http://localhost:8001/static/uploads/users/abc/f.py")

    def test_rejects_different_origin(self):
        from src.storage.file_store import LocalFileStore
        store = LocalFileStore()
        with patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            assert not store.can_handle("https://cdn.example.com/static/uploads/users/abc/f.py")

    def test_rejects_non_static_path(self):
        from src.storage.file_store import LocalFileStore
        store = LocalFileStore()
        with patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            assert not store.can_handle("http://localhost:8001/api/files/abc/f.py")

    def test_rejects_empty_url(self):
        from src.storage.file_store import LocalFileStore
        store = LocalFileStore()
        assert not store.can_handle("")

    def test_matches_docker_service_name(self):
        from src.storage.file_store import LocalFileStore
        store = LocalFileStore()
        with patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://api:8001"):
            assert store.can_handle("http://api:8001/static/uploads/users/t/col/file.py")


# ---------------------------------------------------------------------------
# LocalFileStore.read_bytes
# ---------------------------------------------------------------------------

class TestLocalFileStoreReadBytes:
    def test_reads_existing_file(self, tmp_path):
        from src.storage.file_store import LocalFileStore, _STATIC_URL_PREFIX

        content = b"def hello(): pass\n"
        rel = "uploads/users/tenant1/default/script.py"
        (tmp_path / "uploads/users/tenant1/default").mkdir(parents=True)
        (tmp_path / rel).write_bytes(content)

        store = LocalFileStore()
        url = f"http://localhost:8001{_STATIC_URL_PREFIX}/{rel}"

        with patch("src.storage.file_store._STATIC_DISK_ROOT", tmp_path), \
             patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            result = store.read_bytes(url)

        assert result == content

    def test_returns_none_for_missing_file(self, tmp_path):
        from src.storage.file_store import LocalFileStore, _STATIC_URL_PREFIX

        store = LocalFileStore()
        url = f"http://localhost:8001{_STATIC_URL_PREFIX}/uploads/users/nobody/missing.py"

        with patch("src.storage.file_store._STATIC_DISK_ROOT", tmp_path):
            result = store.read_bytes(url)

        assert result is None

    def test_blocks_path_traversal(self, tmp_path):
        from src.storage.file_store import LocalFileStore, _STATIC_URL_PREFIX

        # Crafted URL trying to escape ./data/
        store = LocalFileStore()
        url = f"http://localhost:8001{_STATIC_URL_PREFIX}/../../../etc/passwd"

        with patch("src.storage.file_store._STATIC_DISK_ROOT", tmp_path):
            result = store.read_bytes(url)

        assert result is None

    def test_raises_for_oversized_file(self, tmp_path):
        from src.storage.file_store import LocalFileStore, _STATIC_URL_PREFIX, _MAX_FILE_BYTES

        large = b"x" * (_MAX_FILE_BYTES + 1)
        rel = "uploads/users/t/col/huge.bin"
        (tmp_path / "uploads/users/t/col").mkdir(parents=True)
        (tmp_path / rel).write_bytes(large)

        store = LocalFileStore()
        url = f"http://localhost:8001{_STATIC_URL_PREFIX}/{rel}"

        with patch("src.storage.file_store._STATIC_DISK_ROOT", tmp_path), \
             patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            with pytest.raises(ValueError, match="too large"):
                store.read_bytes(url)


# ---------------------------------------------------------------------------
# read_upload_url (registry dispatch)
# ---------------------------------------------------------------------------

class TestReadUploadUrl:
    def test_dispatches_to_local_store(self, tmp_path):
        from src.storage.file_store import read_upload_url, _STATIC_URL_PREFIX

        content = b"# hello\n"
        rel = "uploads/users/u/d/hello.py"
        (tmp_path / "uploads/users/u/d").mkdir(parents=True)
        (tmp_path / rel).write_bytes(content)

        url = f"http://localhost:8001{_STATIC_URL_PREFIX}/{rel}"

        with patch("src.storage.file_store._STATIC_DISK_ROOT", tmp_path), \
             patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            result = read_upload_url(url)

        assert result == content

    def test_returns_none_for_external_url(self):
        from src.storage.file_store import read_upload_url
        with patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"):
            result = read_upload_url("https://cdn.example.com/files/script.py")
        assert result is None

    def test_returns_none_for_empty_url(self):
        from src.storage.file_store import read_upload_url
        assert read_upload_url("") is None


# ---------------------------------------------------------------------------
# Integration: _safe_fetch_url delegates to file_store for local URLs
# ---------------------------------------------------------------------------

class TestSafeFetchUrlIntegration:
    def test_local_url_reads_from_disk_not_http(self, tmp_path):
        from src.tools.github.tools import _safe_fetch_url
        from src.storage.file_store import _STATIC_URL_PREFIX

        content = b"print('from disk')\n"
        rel = "uploads/users/u/d/app.py"
        (tmp_path / "uploads/users/u/d").mkdir(parents=True)
        (tmp_path / rel).write_bytes(content)

        url = f"http://localhost:8001{_STATIC_URL_PREFIX}/{rel}"

        with patch("src.storage.file_store._STATIC_DISK_ROOT", tmp_path), \
             patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"), \
             patch("httpx.Client") as mock_http:
            result = _safe_fetch_url(url)

        assert result == content
        mock_http.assert_not_called()  # no HTTP request made

    def test_external_url_goes_through_http(self):
        from src.tools.github.tools import _safe_fetch_url
        import httpx

        with patch("src.storage.file_store.LocalFileStore._base_origin", return_value="http://localhost:8001"), \
             patch("src.tools.github.tools._validate_safe_url"), \
             patch("httpx.Client") as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.read.return_value = b"remote content"
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)

            mock_stream = MagicMock()
            mock_stream.__enter__ = lambda s: mock_response
            mock_stream.__exit__ = MagicMock(return_value=False)

            mock_client = MagicMock()
            mock_client.stream.return_value = mock_stream
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)

            mock_http.return_value = mock_client

            result = _safe_fetch_url("https://external.cdn.example.com/file.py")

        assert result == b"remote content"
