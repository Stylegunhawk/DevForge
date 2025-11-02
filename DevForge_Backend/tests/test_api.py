"""Integration tests for API endpoints.

Tests cover:
- Manifest endpoint (GET /api/manifests/devforge.json)
- Gateway endpoint (POST /api/gateway)
- Error handling (unsupported tools, invalid requests)
- Performance tracking (execution_time field)
"""

import json
import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "uptime" in data
        assert isinstance(data["uptime"], (int, float))


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "DevForge backend running"
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_manifest_endpoint():
    """Test manifest endpoint returns valid JSON with tools array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/manifests/devforge.json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        manifest = response.json()

        # Check structure
        assert manifest["name"] == "devforge"
        assert manifest["version"] == "0.1.0"
        assert "gateway" in manifest
        assert manifest["gateway"].startswith("http://")
        assert "/api/gateway" in manifest["gateway"]

        # Check tools array
        assert "tools" in manifest
        assert isinstance(manifest["tools"], list)
        assert len(manifest["tools"]) > 0

        # Check generate_data tool
        generate_data_tool = next((t for t in manifest["tools"] if t["name"] == "generate_data"), None)
        assert generate_data_tool is not None
        assert "parameters" in generate_data_tool
        assert "description" in generate_data_tool


@pytest.mark.asyncio
async def test_gateway_generate_data_json():
    """Test gateway endpoint with valid generate_data request (JSON format)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 5, "format": "json"}),
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Check GatewayResponse structure
        assert data["success"] is True
        assert data["tool"] == "generate_data"
        assert data["format"] == "json"
        assert "data" in data
        assert data["execution_time"] is not None
        assert data["execution_time"] > 0

        # Verify data is valid JSON
        json_data = json.loads(data["data"])
        assert isinstance(json_data, list)
        assert len(json_data) == 5


@pytest.mark.asyncio
async def test_gateway_generate_data_csv():
    """Test gateway endpoint with valid generate_data request (CSV format)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 3, "format": "csv"}),
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["tool"] == "generate_data"
        assert data["format"] == "csv"
        assert "data" in data
        assert isinstance(data["data"], str)

        # Verify CSV structure (has multiple lines)
        lines = data["data"].strip().split("\n")
        assert len(lines) >= 2  # header + data rows


@pytest.mark.asyncio
async def test_gateway_generate_data_custom_fields():
    """Test gateway endpoint with custom fields."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 2, "format": "json", "fields": ["email", "phone"]}),
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        json_data = json.loads(data["data"])
        assert "email" in json_data[0]
        assert "phone" in json_data[0]


@pytest.mark.asyncio
async def test_gateway_generate_data_dict_arguments():
    """Test gateway endpoint accepts arguments as dict (not just JSON string)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": {"rows": 5, "format": "json"},  # Dict instead of JSON string
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_gateway_unsupported_tool():
    """Test gateway endpoint returns 400 for unsupported tool."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "unknown_tool",
            "arguments": json.dumps({"some": "data"}),
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "unsupported" in data["detail"].lower() or "unknown_tool" in data["detail"]


@pytest.mark.asyncio
async def test_gateway_invalid_arguments():
    """Test gateway endpoint returns 400 for invalid arguments."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 0}),  # Invalid: rows must be >= 1
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_gateway_execution_time_present():
    """Test that execution_time is present and positive for successful requests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 5, "format": "json"}),
        }

        response = await client.post("/api/gateway", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "execution_time" in data
        assert data["execution_time"] is not None
        assert isinstance(data["execution_time"], (int, float))
        assert data["execution_time"] > 0


@pytest.mark.asyncio
async def test_gateway_missing_name():
    """Test gateway endpoint validation with missing name field."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "arguments": json.dumps({"rows": 5}),
        }

        response = await client.post("/api/gateway", json=payload)

        # Pydantic validation should return 422
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_gateway_invalid_json_string():
    """Test gateway endpoint handles invalid JSON in arguments string."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": "not valid json {",
        }

        response = await client.post("/api/gateway", json=payload)

        # Should return 400 or 422 (validation error)
        assert response.status_code in (400, 422)

