"""DataGen tools for generating mock CSV/JSON data.

Uses Faker for realistic data generation and Pandas for data manipulation.
"""

import json
import logging
from typing import Any

import pandas as pd
from faker import Faker

# Initialize Faker with deterministic seed for testing
_faker = Faker()
Faker.seed(42)  # Seed for reproducible tests


def _get_default_fields() -> dict[str, Any]:
    """Get default field definitions for data generation.

    Returns:
        Dictionary mapping field names to Faker providers
    """
    return {
        "name": lambda: _faker.name(),
        "email": lambda: _faker.email(),
        "address": lambda: _faker.address().replace("\n", ", "),
        "phone": lambda: _faker.phone_number(),
        "company": lambda: _faker.company(),
        "job": lambda: _faker.job(),
        "date_of_birth": lambda: _faker.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
        "city": lambda: _faker.city(),
        "country": lambda: _faker.country(),
        "zipcode": lambda: _faker.zipcode(),
    }


def _generate_field_data(field_name: str, faker_instance: Faker) -> Any:
    """Generate data for a specific field using Faker.

    Args:
        field_name: Name of the field to generate
        faker_instance: Faker instance to use

    Returns:
        Generated field value
    """
    default_fields = _get_default_fields()

    # Check if it's a default field
    if field_name.lower() in default_fields:
        return default_fields[field_name.lower()]()

    # Try common Faker methods based on field name
    field_lower = field_name.lower()

    if "email" in field_lower:
        return faker_instance.email()
    elif "phone" in field_lower or "tel" in field_lower:
        return faker_instance.phone_number()
    elif "name" in field_lower:
        return faker_instance.name()
    elif "address" in field_lower:
        return faker_instance.address().replace("\n", ", ")
    elif "city" in field_lower:
        return faker_instance.city()
    elif "country" in field_lower:
        return faker_instance.country()
    elif "zip" in field_lower or "postal" in field_lower:
        return faker_instance.zipcode()
    elif "date" in field_lower or "birth" in field_lower:
        return faker_instance.date_of_birth(minimum_age=18, maximum_age=80).isoformat()
    elif "company" in field_lower or "organization" in field_lower:
        return faker_instance.company()
    elif "job" in field_lower or "title" in field_lower or "position" in field_lower:
        return faker_instance.job()
    elif "url" in field_lower or "website" in field_lower:
        return faker_instance.url()
    elif "uuid" in field_lower or "id" in field_lower:
        return faker_instance.uuid4()
    else:
        # Default: use Lorem text
        return faker_instance.text(max_nb_chars=50)


def generate_mock_data(rows: int, format: str = "json", fields: list[str] | None = None) -> str:
    """Generate mock data in CSV or JSON format.

    Args:
        rows: Number of rows to generate (1-10000)
        format: Output format ("csv" or "json")
        fields: Optional list of custom field names. If None, uses default fields.

    Returns:
        String containing CSV or JSON data

    Raises:
        ValueError: If format is invalid or rows is out of range
    """
    logging.info(
        f"Generating {rows} rows of mock data in {format} format",
        extra={"rows": rows, "format": format, "custom_fields": fields is not None},
    )

    # Validate format
    format_lower = format.lower()
    if format_lower not in ("csv", "json"):
        raise ValueError(f"Format must be 'csv' or 'json', got: {format}")

    # Validate rows
    if rows < 1 or rows > 10000:
        raise ValueError(f"Rows must be between 1 and 10000, got: {rows}")

    # Determine fields to generate
    if fields is None or len(fields) == 0:
        # Use default fields (limit to top 8 for readability)
        fields_to_generate = list(_get_default_fields().keys())[:8]
    else:
        # Use custom fields (remove duplicates, preserve order)
        fields_to_generate = list(dict.fromkeys(fields))

    # Generate data
    faker_instance = Faker()
    data_rows = []

    for _ in range(rows):
        row = {}
        for field_name in fields_to_generate:
            row[field_name] = _generate_field_data(field_name, faker_instance)
        data_rows.append(row)

    # Convert to requested format
    if format_lower == "json":
        # Return as JSON array
        return json.dumps(data_rows, indent=2)
    else:  # CSV
        # Use Pandas to generate CSV
        df = pd.DataFrame(data_rows)
        return df.to_csv(index=False)


