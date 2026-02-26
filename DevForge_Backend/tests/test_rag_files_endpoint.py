"""
Test for GET /api/v1/rag/files endpoint
"""
import pytest
from httpx import AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_get_all_files_empty():
    """Test GET /files returns empty list for tenant with no files"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/rag/files",
            headers={"X-User-ID": "empty_tenant_123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


@pytest.mark.asyncio
async def test_get_all_files_tenant_isolation():
    """Test that files are properly isolated by tenant"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload file for tenant A
        with open("tests/fixtures/test.txt", "rb") as f:
            response_a = await client.post(
                "/api/v1/rag/file/upload",
                headers={"X-User-ID": "tenant_a"},
                files={"files": ("test_a.txt", f, "text/plain")},
                data={"collection": "default"}
            )
        assert response_a.status_code == 200
        
        # Upload file for tenant B  
        with open("tests/fixtures/test.txt", "rb") as f:
            response_b = await client.post(
                "/api/v1/rag/file/upload",
                headers={"X-User-ID": "tenant_b"},
                files={"files": ("test_b.txt", f, "text/plain")},
                data={"collection": "default"}
            )
        assert response_b.status_code == 200
        
        # Get files for tenant A
        files_a = await client.get(
            "/api/v1/rag/files",
            headers={"X-User-ID": "tenant_a"}
        )
        assert files_a.status_code == 200
        data_a = files_a.json()
        assert len(data_a) >= 1
        assert all(f["tenant_id"] == "tenant_a" for f in data_a)
        
        # Get files for tenant B
        files_b = await client.get(
            "/api/v1/rag/files",
            headers={"X-User-ID": "tenant_b"}
        )
        assert files_b.status_code == 200
        data_b = files_b.json()
        assert len(data_b) >= 1
        assert all(f["tenant_id"] == "tenant_b" for f in data_b)
        
        # Ensure tenant A cannot see tenant B's files
        tenant_a_file_ids = {f["id"] for f in data_a}
        tenant_b_file_ids = {f["id"] for f in data_b}
        assert tenant_a_file_ids.isdisjoint(tenant_b_file_ids)


@pytest.mark.asyncio
async def test_get_all_files_default_tenant():
    """Test that default tenant is used when X-User-ID is not provided"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/rag/files")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # If there are any files, they should have tenant_id="default"
        if data:
            assert all(f.get("tenant_id") == "default" for f in data)


@pytest.mark.asyncio
async def test_get_all_files_response_schema():
    """Test that response matches FileStatusResponse schema"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload a test file first
        with open("tests/fixtures/test.txt", "rb") as f:
            upload_response = await client.post(
                "/api/v1/rag/file/upload",
                headers={"X-User-ID": "schema_test_tenant"},
                files={"files": ("test.txt", f, "text/plain")},
                data={"collection": "default"}
            )
        assert upload_response.status_code == 200
        
        # Get all files
        response = await client.get(
            "/api/v1/rag/files",
            headers={"X-User-ID": "schema_test_tenant"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Validate schema of first file
        file = data[0]
        assert "id" in file
        assert "name" in file
        assert "size" in file
        assert "url" in file
        assert "fileType" in file
        assert "chunkCount" in file
        assert "chunkingStatus" in file
        assert "embeddingStatus" in file
        assert "finishEmbedding" in file
        assert isinstance(file["finishEmbedding"], bool)
