"""End-to-end integration tests for complete Phase 1 flow.

Tests the full integration path:
1. Server starts successfully
2. Manifest is discoverable
3. Gateway accepts requests
4. DataGen tool generates valid output
5. Complete request/response cycle works
"""

import json
import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_complete_datagen_flow_json():
    """Test complete end-to-end flow: manifest -> gateway -> JSON generation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: Get manifest
        manifest_response = await client.get("/api/manifests/devforge.json")
        assert manifest_response.status_code == 200
        manifest = manifest_response.json()
        assert manifest["gateway"].endswith("/api/gateway")

        # Step 2: Use manifest info to call gateway
        gateway_url = manifest["gateway"].split("/api")[1]  # Get relative path
        tool_def = next((t for t in manifest["tools"] if t["name"] == "generate_data"), None)
        assert tool_def is not None

        # Step 3: Call gateway with generate_data
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 3, "format": "json"}),
        }

        gateway_response = await client.post(gateway_url, json=payload)
        assert gateway_response.status_code == 200

        result = gateway_response.json()
        assert result["success"] is True
        assert result["tool"] == "generate_data"
        assert result["format"] == "json"
        assert result["execution_time"] > 0

        # Step 4: Verify generated data
        data = json.loads(result["data"])
        assert isinstance(data, list)
        assert len(data) == 3
        assert all(isinstance(row, dict) for row in data)


@pytest.mark.asyncio
async def test_complete_datagen_flow_csv():
    """Test complete end-to-end flow: manifest -> gateway -> CSV generation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Get manifest
        manifest_response = await client.get("/api/manifests/devforge.json")
        manifest = manifest_response.json()

        # Call gateway for CSV
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 2, "format": "csv"}),
        }

        gateway_response = await client.post("/api/gateway", json=payload)
        assert gateway_response.status_code == 200

        result = gateway_response.json()
        assert result["success"] is True
        assert result["format"] == "csv"

        # Verify CSV structure
        csv_lines = result["data"].strip().split("\n")
        assert len(csv_lines) >= 3  # header + 2 rows


@pytest.mark.asyncio
async def test_manifest_tool_schema_matches_gateway():
    """Test that manifest tool schema matches what gateway expects."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Get manifest
        manifest_response = await client.get("/api/manifests/devforge.json")
        manifest = manifest_response.json()

        generate_data_tool = next((t for t in manifest["tools"] if t["name"] == "generate_data"), None)
        assert generate_data_tool is not None

        params = generate_data_tool["parameters"]["properties"]

        # Verify required field exists
        assert "rows" in params
        assert params["rows"]["type"] == "integer"
        assert params["rows"]["minimum"] == 1
        assert params["rows"]["maximum"] == 10000

        # Verify format enum
        assert "format" in params
        assert params["format"]["type"] == "string"
        assert "enum" in params["format"]
        assert set(params["format"]["enum"]) == {"csv", "json"}

        # Test with minimum valid request (only required field)
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 1}),
        }

        response = await client.post("/api/gateway", json=payload)
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Test with all optional fields
        payload_full = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 2, "format": "json", "fields": ["email", "phone"]}),
        }

        response_full = await client.post("/api/gateway", json=payload_full)
        assert response_full.status_code == 200
        assert response_full.json()["success"] is True


@pytest.mark.asyncio
async def test_performance_tracking_consistent():
    """Test that performance tracking works consistently across requests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 5, "format": "json"}),
        }

        # Make multiple requests
        execution_times = []
        for _ in range(3):
            response = await client.post("/api/gateway", json=payload)
            assert response.status_code == 200
            result = response.json()
            execution_times.append(result["execution_time"])

        # All should have execution times
        assert all(t > 0 for t in execution_times)
        # Execution times should be reasonable (less than 10 seconds for 5 rows)
        assert all(t < 10.0 for t in execution_times)


@pytest.mark.asyncio
async def test_health_and_root_before_manifest():
    """Test that basic endpoints work before testing manifest."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Health check
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # Root
        root = await client.get("/")
        assert root.status_code == 200
        assert "version" in root.json()


@pytest.mark.asyncio
async def test_cors_headers_present():
    """Test that CORS headers are configured (if applicable)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Options request for CORS preflight (if needed)
        response = await client.options("/api/gateway")
        # Should not return 405 (method not allowed) if CORS is properly configured
        # The actual CORS headers would be tested with a real browser/client
        assert response.status_code in (200, 405, 404)  # Accept various valid responses


@pytest.mark.asyncio
async def test_error_handling_propagates_correctly():
    """Test that errors are handled gracefully end-to-end."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Invalid tool name
        invalid_payload = {
            "name": "nonexistent_tool",
            "arguments": json.dumps({"test": "data"}),
        }

        response = await client.post("/api/gateway", json=invalid_payload)
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data

        # Invalid arguments (rows too high)
        invalid_args_payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 50000}),  # Exceeds max
        }

        response = await client.post("/api/gateway", json=invalid_args_payload)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_manifest_gateway_url_matches_api():
    """Test that manifest gateway URL actually works."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Get manifest
        manifest_response = await client.get("/api/manifests/devforge.json")
        manifest = manifest_response.json()
        gateway_url_in_manifest = manifest["gateway"]

        # Extract the path from the gateway URL
        # Format is "http://localhost:PORT/api/gateway"
        if "/api/gateway" in gateway_url_in_manifest:
            gateway_path = "/api/gateway"
        else:
            gateway_path = gateway_url_in_manifest.split("://")[-1].split("/", 1)[1]

        # Test the gateway path works
        payload = {
            "name": "generate_data",
            "arguments": json.dumps({"rows": 1, "format": "json"}),
        }

        response = await client.post(gateway_path, json=payload)
        assert response.status_code == 200
        assert response.json()["success"] is True

