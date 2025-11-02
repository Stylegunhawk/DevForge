"""Unit and integration tests for DataGen feature.

Tests cover:
- generate_mock_data() with various parameters
- CSV and JSON format generation
- Custom fields vs default fields
- Edge cases and validation
- Agent async execution
"""

import json
import pytest
from src.agents.datagen.agent import datagen_agent
from src.tools.datagen.tools import generate_mock_data


class TestGenerateMockData:
    """Unit tests for generate_mock_data function."""

    def test_generate_json_default_fields(self):
        """Test JSON generation with default fields."""
        result = generate_mock_data(rows=10, format="json")
        data = json.loads(result)

        assert isinstance(data, list)
        assert len(data) == 10

        # Check structure of first row
        first_row = data[0]
        assert isinstance(first_row, dict)
        assert len(first_row) > 0

        # Check common default fields exist
        assert "name" in first_row
        assert "email" in first_row

    def test_generate_csv_default_fields(self):
        """Test CSV generation with default fields."""
        result = generate_mock_data(rows=5, format="csv")
        lines = result.strip().split("\n")

        assert len(lines) == 6  # header + 5 rows
        assert "name" in lines[0].lower() or "email" in lines[0].lower()

    def test_generate_json_custom_fields(self):
        """Test JSON generation with custom fields."""
        custom_fields = ["email", "phone", "city"]
        result = generate_mock_data(rows=3, format="json", fields=custom_fields)
        data = json.loads(result)

        assert len(data) == 3
        first_row = data[0]

        # Check all custom fields are present
        for field in custom_fields:
            assert field in first_row

    def test_generate_csv_custom_fields(self):
        """Test CSV generation with custom fields."""
        custom_fields = ["email", "phone"]
        result = generate_mock_data(rows=2, format="csv", fields=custom_fields)
        lines = result.strip().split("\n")

        assert len(lines) == 3  # header + 2 rows
        # Check header contains both fields
        header = lines[0].lower()
        assert "email" in header
        assert "phone" in header

    def test_single_row(self):
        """Test generation of single row."""
        result = generate_mock_data(rows=1, format="json")
        data = json.loads(result)
        assert len(data) == 1

    def test_max_rows(self):
        """Test generation of maximum allowed rows."""
        result = generate_mock_data(rows=10000, format="json")
        data = json.loads(result)
        assert len(data) == 10000

    def test_json_format_is_valid(self):
        """Test that JSON output is valid JSON."""
        result = generate_mock_data(rows=5, format="json")
        # Should not raise exception
        data = json.loads(result)
        assert isinstance(data, list)

    def test_csv_format_has_header(self):
        """Test that CSV output has header row."""
        result = generate_mock_data(rows=3, format="csv")
        lines = result.strip().split("\n")
        assert len(lines) >= 2  # At least header + 1 row

    def test_custom_field_auto_detection(self):
        """Test that common field names are auto-detected."""
        # Test various field name patterns
        fields = ["user_email", "phone_number", "full_name", "user_id"]
        result = generate_mock_data(rows=2, format="json", fields=fields)
        data = json.loads(result)

        # All fields should be present
        for field in fields:
            assert field in data[0]

    def test_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Format must be"):
            generate_mock_data(rows=10, format="xml")

    def test_invalid_rows_too_low(self):
        """Test that rows < 1 raises ValueError."""
        with pytest.raises(ValueError, match="Rows must be between"):
            generate_mock_data(rows=0, format="json")

    def test_invalid_rows_too_high(self):
        """Test that rows > 10000 raises ValueError."""
        with pytest.raises(ValueError, match="Rows must be between"):
            generate_mock_data(rows=10001, format="json")

    def test_empty_fields_list_uses_defaults(self):
        """Test that empty fields list uses default fields."""
        result = generate_mock_data(rows=2, format="json", fields=[])
        data = json.loads(result)
        # Should have default fields
        assert len(data[0]) > 0


class TestDataGenAgent:
    """Integration tests for datagen_agent async function."""

    @pytest.mark.asyncio
    async def test_agent_basic_json(self):
        """Test agent with basic JSON generation."""
        args = {"rows": 5, "format": "json"}
        result = await datagen_agent(args)

        assert result["success"] is True
        assert result["format"] == "json"
        assert isinstance(result["data"], str)

        # Verify it's valid JSON
        data = json.loads(result["data"])
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_agent_basic_csv(self):
        """Test agent with basic CSV generation."""
        args = {"rows": 3, "format": "csv"}
        result = await datagen_agent(args)

        assert result["success"] is True
        assert result["format"] == "csv"
        assert isinstance(result["data"], str)

        # Verify CSV structure
        lines = result["data"].strip().split("\n")
        assert len(lines) == 4  # header + 3 rows

    @pytest.mark.asyncio
    async def test_agent_custom_fields(self):
        """Test agent with custom fields."""
        args = {"rows": 2, "format": "json", "fields": ["email", "phone"]}
        result = await datagen_agent(args)

        assert result["success"] is True
        data = json.loads(result["data"])
        assert "email" in data[0]
        assert "phone" in data[0]

    @pytest.mark.asyncio
    async def test_agent_default_format(self):
        """Test agent with default format (should be json)."""
        args = {"rows": 2}
        result = await datagen_agent(args)

        assert result["success"] is True
        assert result["format"] == "json"

    @pytest.mark.asyncio
    async def test_agent_invalid_rows(self):
        """Test agent validation with invalid rows."""
        args = {"rows": 0, "format": "json"}
        with pytest.raises(ValueError):
            await datagen_agent(args)

    @pytest.mark.asyncio
    async def test_agent_invalid_format(self):
        """Test agent validation with invalid format."""
        args = {"rows": 5, "format": "xml"}
        with pytest.raises(ValueError):
            await datagen_agent(args)

    @pytest.mark.asyncio
    async def test_agent_large_dataset(self):
        """Test agent with large dataset."""
        args = {"rows": 100, "format": "json"}
        result = await datagen_agent(args)

        assert result["success"] is True
        data = json.loads(result["data"])
        assert len(data) == 100

