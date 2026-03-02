
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Set env vars before importing the app
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ["JWT_SECRET"] = "test-jwt-secret"

from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_google_verify():
    with patch("src.core.auth.id_token.verify_oauth2_token") as mock:
        yield mock

def test_google_login_success(client, mock_google_verify):
    mock_google_verify.return_value = {"sub": "test-google-user-id"}
    response = client.post(
        "/api/auth/google",
        json={"google_token": "valid-google-token", "mongodb_id": "test-tenant-id"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600

def test_google_login_invalid_token(client, mock_google_verify):
    mock_google_verify.side_effect = ValueError("Invalid token")
    response = client.post(
        "/api/auth/google",
        json={"google_token": "invalid-google-token", "mongodb_id": "test-tenant-id"},
    )
    assert response.status_code == 401

def test_rag_endpoint_no_token(client):
    response = client.get("/api/v1/rag/files")
    assert response.status_code == 401

def test_rag_endpoint_invalid_token(client):
    response = client.get(
        "/api/v1/rag/files", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401

def test_rag_endpoint_valid_token(client):
    # 1. Get a valid token
    with patch("src.core.auth.id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = {"sub": "test-google-user-id"}
        login_response = client.post(
            "/api/auth/google",
            json={"google_token": "valid-google-token", "mongodb_id": "test-tenant-id"},
        )
    access_token = login_response.json()["access_token"]

    # 2. Use the token to access a protected RAG endpoint
    with patch("src.storage.redis_file_store.RedisFileStore.get_all_files_for_tenant") as mock_get_files:
        mock_get_files.return_value = []
        rag_response = client.get(
            "/api/v1/rag/files",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert rag_response.status_code == 200
        mock_get_files.assert_called_with("test-tenant-id")

def test_rag_endpoint_wrong_tenant(client):
    # 1. Get a token for tenant "A"
    with patch("src.core.auth.id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = {"sub": "google-user-a"}
        login_response = client.post(
            "/api/auth/google",
            json={"google_token": "token-a", "mongodb_id": "tenant-a"},
        )
    token_a = login_response.json()["access_token"]

    # 2. Try to access a resource for tenant "B"
    with patch("src.storage.redis_file_store.RedisFileStore.get_file_metadata") as mock_get_meta:
        # This file metadata belongs to tenant-b
        mock_get_meta.return_value = {"tenant_id": "tenant-b", "name": "file.txt"}
        
        response = client.get(
            "/api/v1/rag/file/some-file-id",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # The middleware should block this
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"

