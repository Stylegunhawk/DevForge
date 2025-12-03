# generate_data - Mock Data Generation Tool

**Tool Name:** `generate_data`  
**Version:** 0.7.0  
**Phase:** 1 (Foundation)  
**Status:** ✅ Production Ready

---

## Overview

The `generate_data` tool generates realistic mock data in CSV or JSON format using Faker and Pandas libraries. Perfect for testing, prototyping, and development workflows where you need sample datasets quickly.

---

## Features

- ✅ Generate realistic mock data with Faker library
- ✅ Support for CSV and JSON output formats
- ✅ Customizable field selection
- ✅ Configurable row counts (1-10,000 rows)
- ✅ Default field set for quick generation
- ✅ Fast execution (< 1s for small datasets)

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `rows` | integer | ✅ Yes | 10 | Number of rows to generate (1-10,000) |
| `format` | string | No | `"json"` | Output format: `"json"` or `"csv"` |
| `fields` | array[string] | No | Default fields | Custom fields to generate |

### Supported Fields

When `fields` is not specified, the tool generates these default fields:
- `name` - Full name
- `email` - Email address
- `phone` - Phone number
- `address` - Street address
- `company` - Company name
- `job` - Job title
- `date` - Date

**Custom field options include:**
- Personal: `name`, `first_name`, `last_name`, `email`, `phone`, `ssn`
- Location: `address`, `city`, `state`, `zipcode`, `country`
- Business: `company`, `job`, `catch_phrase`
- Internet: `url`, `ipv4`, `user_name`, `password`
- Dates: `date`, `date_time`, `time`
- Text: `text`, `sentence`, `paragraph`
- Numbers: `random_int`, `random_digit`

---

## API Usage

### Basic JSON Generation

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 10,
      "format": "json"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "data": "[{\"name\":\"John Doe\",\"email\":\"john@example.com\",...}, ...]",
    "format": "json",
    "rows": 10
  },
  "message": "generate_data executed successfully"
}
```

### CSV Generation

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 100,
      "format": "csv"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "data": "name,email,phone,address,...\nJohn Doe,john@example.com,...",
    "format": "csv",
    "rows": 100
  }
}
```

### Custom Fields

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 50,
      "format": "json",
      "fields": ["email", "company", "job", "city"]
    }
  }'
```

---

## Lobe Chat Usage

### Simple Request
```
"Generate 20 user records in JSON format"
```

### Custom Fields Request
```
"Create 100 rows of mock data with email, phone, and company name in CSV format"
```

### Large Dataset
```
"Generate 5000 employee records with name, email, job title, and department"
```

---

## Use Cases

### 1. API Testing
Generate mock user data for testing REST APIs:
```json
{
  "rows": 100,
  "format": "json",
  "fields": ["name", "email", "password", "date"]
}
```

### 2. Database Seeding
Create CSV files for importing into databases:
```json
{
  "rows": 10000,
  "format": "csv",
  "fields": ["name", "email", "phone", "address", "company"]
}
```

### 3. UI Prototyping
Generate sample data for frontend mockups:
```json
{
  "rows": 10,
  "format": "json",
  "fields": ["name", "email", "url"]
}
```

### 4. Performance Testing
Test application performance with large datasets:
```json
{
  "rows": 10000,
  "format": "json"
}
```

---

## Performance

| Dataset Size | Execution Time | Use Case |
|--------------|----------------|----------|
| 10 rows | < 0.1s | Quick tests |
| 100 rows | < 0.5s | Prototyping |
| 1,000 rows | < 2s | Development |
| 10,000 rows | < 5s | Load testing |

---

## Implementation Details

### Technology Stack
- **Faker** 28.0.0 - Realistic fake data generation
- **Pandas** 2.2.0 - Data manipulation and formatting
- **FastAPI** - Async endpoint handling

### Agent Architecture
```
User Request
    ↓
Gateway (/api/gateway)
    ↓
DataGen Agent
    ↓
Faker + Pandas Tools
    ↓
JSON/CSV Output
```

### Code Location
- Agent: `src/agents/datagen/agent.py`
- Tools: `src/tools/datagen/tools.py`
- Tests: `tests/test_datagen.py`

---

## Error Handling

### Invalid Row Count
```json
{
  "rows": 0,  // Error: minimum is 1
  "format": "json"
}
```

**Response:**
```json
{
  "success": false,
  "message": "rows must be between 1 and 10000"
}
```

### Invalid Format
```json
{
  "rows": 10,
  "format": "xml"  // Error: only json/csv supported
}
```

**Response:**
```json
{
  "success": false,
  "message": "format must be 'json' or 'csv'"
}
```

### Invalid Fields
```json
{
  "rows": 10,
  "fields": ["invalid_field"]
}
```

**Response:**
```json
{
  "success": false,
  "message": "Unknown field: invalid_field"
}
```

---

## Examples

### E-Commerce Users
```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 50,
      "format": "json",
      "fields": ["name", "email", "address", "phone", "company"]
    }
  }'
```

### Employee Directory
```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 200,
      "format": "csv",
      "fields": ["name", "email", "job", "company", "phone"]
    }
  }'
```

### Social Media Profiles
```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 100,
      "format": "json",
      "fields": ["user_name", "email", "url", "text"]
    }
  }'
```

---

## Testing

### Run Tests
```bash
pytest tests/test_datagen.py -v
```

### Test Coverage
- ✅ Unit tests (13 tests)
- ✅ Integration tests
- ✅ E2E workflow tests
- ✅ Edge case validation

---

## Best Practices

1. **Use appropriate row counts** - Start small, scale as needed
2. **Specify custom fields** - Only generate what you need
3. **Choose the right format** - JSON for APIs, CSV for imports
4. **Cache results** - Reuse generated data when possible
5. **Validate output** - Check data meets your requirements

---

## Troubleshooting

**Issue:** Slow generation for large datasets  
**Solution:** Use streaming or batch generation for 10k+ rows

**Issue:** Memory errors with very large datasets  
**Solution:** Reduce row count or generate in batches

**Issue:** Fields not recognized  
**Solution:** Check supported fields list or use defaults

---

## Related Tools

- `refine_prompt` - Optimize data generation prompts
- `retrieve_docs` - Search Faker documentation

---

**Last Updated:** December 2, 2025  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
