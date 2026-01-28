# generate_data - Advanced Synthetic Data Generation Tool

**Tool Name:** `generate_data`  
**Version:** 1.1.0 (Phase 1 Complete - Production Ready)  
**Phase:** Phase 1 (3-Layer Semantic Architecture)  
**Status:** ✅ Production Ready (Verified)

---

## Overview

The `generate_data` tool generates realistic synthetic data with two operational modes:

- **V1 Mode (Simple)**: Original Faker-based generation for backward compatibility
- **V2 Mode (Advanced)**: LLM-powered semantic analysis with domain-specific value generation, multi-entity relationships, and data quality simulation

Perfect for testing, prototyping, development workflows, and generating complex relational datasets.

**Phase 1 Refactor:** LLM is now confined to **classification only** - it never generates data values. All values come from Faker or catalogs, fixing the "Agent every development say" prose bug permanently!

> [!IMPORTANT]
> **Key Guarantee:** LLM outputs are metadata (semantic types, constraints), never actual data values.

---

## Features

### V1 Mode (Backward Compatible)
- ✅ Generate realistic mock data with Faker library
- ✅ Support for CSV and JSON output formats
- ✅ Customizable field selection
- ✅ Configurable row counts (1-10,000 rows)
- ✅ Fast execution (\u003c 1s for small datasets)

### V2 Mode (Phase 1 Advanced)
- 🆕 **LLM-powered schema design** from natural language prompts
- 🆕 **Domain templates** for ecommerce and SaaS use cases
- 🆕 **Multi-entity generation** - generates data for multiple related entities
- 🆕 **Semantic field analysis** - understands field context (e.g., `flowers.name` vs `person.name`)
- 🆕 **Data quality realism** - null injection based on realism level (Phase 1 simplified realism)
- 🆕 **Relationship-aware generation** - foreign key relationships are tracked **and enforced** during generation

### Phase 1 (3-Layer Semantic Architecture)
- 🏗️ **Layer 1: Semantic Understanding** - Multi-tier classification (lexical → pattern → context → LLM → fallback)
- 🏗️ **Layer 2: Generator Selection** - Semantic type → generator mapping via `SemanticRouter`
- 🏗️ **Layer 3: Value Production** - Faker/catalogs only, **never LLM**
- ✨ **303 lexical mappings** - Fast dictionary-based field name recognition
- ✨ **Pattern matching** - Regex for suffixes (`_at`, `_id`) and prefixes (`is_`, `has_`)
- ✨ **Context classification** - Entity-aware name resolution (flowers.name → flower_name)
- ✨ **LLM classification** - Only returns semantic metadata, never values
- ✨ **Two-tier catalog caching** - L1 (request) + L2 (process with TTL)
- ✨ **Feature flag** - `ENABLE_SEMANTIC_ANALYZER` environment variable
- ✨ **Full observability** - Metadata with source, confidence, and warnings

### Supported Constraints (Phase 1)
The following constraints are enforced during generation:
- `pattern`: Regex strings (e.g., `^[A-Z]{3}-[0-9]{3}$`). Requires `rstr` package for complex patterns.
- `enum`: List of allowed values (e.g., `["active", "inactive"]`).
- `min`/`max`: Numeric ranges (e.g., `min: 10, max: 100`).

---

## Parameters

| Parameter | Type | Required | Default | Description | Mode |
|-----------|------|----------|---------|-------------|------|
| `rows` | integer | ✅ Yes | - | Number of rows to generate (1-10,000) | V1, V2 |
| `format` | string | No | `"json"` | Output format: `"json"` or `"csv"` | V1, V2 |
| `fields` | array[string] | No | Default fields | Custom fields to generate | V1 only |
| `prompt` | string | No | `null` | Natural language schema description | V2 only |
| `domain` | string | No | `null` | Pre-defined domain: `"ecommerce"` or `"saas"` | V2 only |
| `realism_level` | string | No | `"basic"` | Data quality level: `"basic"`, `"medium"`, `"high"` | V2 only |
| `enable_semantic_generation` | boolean | No | `true` | Enable Phase 1 semantic analysis (handled via getattr, not in schema) | V2 only |

### Mode Selection

The tool automatically selects the appropriate mode:
- **V2 Mode**: Triggered when `prompt` OR `domain` is provided
- **V1 Mode**: Used when neither `prompt` nor `domain` is provided (backward compatible)

### Realism Levels (V2 Only)

| Level | Null Injection | Duplicate Injection | Outlier Injection |
|-------|----------------|---------------------|-------------------|
| `basic` | 0% | 0% | 0% |
| `medium` | ~5% on nullable fields | 0% | 0% |
| `high` | ~10% on nullable fields | ~2% on key fields | ~1% on numeric fields |

---

## V1 Mode: Simple Generation (Backward Compatible)

### Supported Fields

When `fields` is not specified, default fields are generated:
- `name`, `email`, `phone`, `address`, `company`, `job`, `date`

**Custom field options:**
- Personal: `name`, `first_name`, `last_name`, `email`, `phone`, `ssn`
- Location: `address`, `city`, `state`, `zipcode`, `country`
- Business: `company`, `job`, `catch_phrase`
- Internet: `url`, `ipv4`, `user_name`, `password`
- Dates: `date`, `date_time`, `time`
- Text: `text`, `sentence`, `paragraph`
- Numbers: `random_int`, `random_digit`

### V1 Usage Examples

#### Basic JSON Generation
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

#### CSV with Custom Fields
```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 100,
      "format": "csv",
      "fields": ["name", "email", "phone", "company"]
    }
  }'
```

**V1 Response Format:**
```json
{
  "success": true,
  "data": {
    "data": "[{\"name\":\"John Doe\", ...}]",
    "format": "json",
    "rows": 10,
    "mode": "v1"
  }
}
```

---

## V2 Mode: Advanced Multi-Entity Generation

### Domain Templates

#### Ecommerce Domain
**Entities:** customers, products, orders  
**Relationships:** orders → customers (1:N), orders → products (1:N) (enforced during generation)  
**Distributions:** Lognormal prices, categorical order statuses  
**Default Counts:** 100 customers, 50 products, 500 orders

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 500,
      "format": "json",
      "domain": "ecommerce",
      "realism_level": "high"
    }
  }'
```

#### SaaS Domain
**Entities:** users, subscriptions, usage_logs  
**Relationships:** subscriptions → users (1:N), usage_logs → subscriptions (1:N) (enforced during generation)  
**Distributions:** Categorical plans, pareto API usage  
**Default Counts:** 100 users, 120 subscriptions, 1000 usage logs

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 1000,
      "format": "csv",
      "domain": "saas",
      "realism_level": "medium"
    }
  }'
```

### LLM-Powered Schema Design

Use natural language to describe your desired schema:

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 200,
      "format": "json",
      "prompt": "Generate healthcare patient data with appointments and prescriptions",
      "realism_level": "high"
    }
  }'
```

### Phase 1: Semantic Generation (NEW!)

**The Problem:** Before Phase 1, generating domain-specific data often resulted in generic Faker values that didn't match the context:

```bash
# ❌ Before Phase 1 (The "Daniel Doyle Flower" Bug)
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "prompt": "Generate a catalog of flowers with names and botanical families"
    }
  }'

# Result: flowers.name = "Daniel Doyle", "Michael Chen", "Sarah Johnson"
# (Generic Faker names, NOT actual flower names!)
```

**The Solution:** Phase 1 semantic analysis understands field context and generates domain-specific values:

```bash
# ✅ After Phase 1 (Semantic Intelligence)
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "prompt": "Generate a catalog of flowers with names and botanical families",
      "enable_semantic_generation": true
    }
  }'

# Result: flowers.name = "Rose", "Tulip", "Orchid", "Lily", "Sunflower"
# (Actual flower names!)
```

**How It Works:**

1. **Schema Design**: LLM creates schema with `flowers` entity
2. **Semantic Analysis**: Analyzer understands `flowers.name` means "flower_name" not "person_name"
3. **Catalog Generation**: LLM generates 50 realistic flower names
4. **Value Sampling**: Generator samples from catalog for each row

**More Examples:**

```bash
# Universities get university names
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "prompt": "Generate database of 100 universities with locations",
      "enable_semantic_generation": true
    }
  }'
# universities.name = "Harvard", "MIT", "Stanford", "Oxford"...

# Tools get tool names  
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "prompt": "Generate hardware store inventory",
      "enable_semantic_generation": true
    }
  }'
# tools.name = "Hammer", "Screwdriver", "Drill", "Wrench"...
```

**Disabling Semantic Generation (V1 Mode):**

For backward compatibility or when LLM access is limited:

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "prompt": "Generate flower catalog",
      "enable_semantic_generation": false
    }
  }'
# Falls back to Faker (generic values)
```

**V2 Response Format:**
```json
{
  "success": true,
  "data": {
    "entities": ["customers", "orders", "products"],
    "schema": {
      "domain": "ecommerce",
      "entity_count": 3,
      "relationship_count": 2
    },
    "data": {
      "customers": [
        {"id": "uuid-1", "email": "..."},
        ...
      ],
      "orders": [
        {"id": "uuid-2", "customer_id": "uuid-1", ...},
        ...
      ],
      "products": [
        {"id": "uuid-3", ...},
        ...
      ]
    },
    "format": "json",
    "rows": 500,
    "mode": "v2",
    "semantic_generation_used": true,
    "metadata": {
      "semantic_analysis_summary": {
        "enabled": true,
        "total_fields": 15,
        "classified_by_lexical": 10,
        "classified_by_pattern": 3,
        "classified_by_context": 1,
        "classified_by_llm": 1,
        "fallback_used": 0,
        "avg_confidence": 0.92,
        "llm_call_rate": 6.7
      },
      "field_analysis": {
        "customers": {
          "email": {
            "semantic_type": "EMAIL_ADDRESS",
            "source": "lexical",
            "confidence": 1.0
          }
        }
      },
      "warnings": [],
      "performance": {
        "analysis_ms": 150,
        "generation_ms": 1200,
        "total_ms": 1350
      },
      "constraint_enforcement": {
        "enforced": true,
        "violations_count": 0
      }
    },
    "constraint_violations": [],
    "fk_integrity": {
      "valid": true,
      "errors": [],
      "statistics": {
        "orders->customers": {
          "total_children": 500,
          "total_parents": 100,
          "parents_with_children": 100,
          "parents_with_zero_children": 0,
          "orphaned_children": 0
        }
      }
    }
  }
}
```

> **Note:** `semantic_generation_used` field indicates whether Phase 1 semantic analysis was successfully applied. `false` means fallback to Faker was used. The `enable_semantic_generation` parameter is not part of the Pydantic schema but is handled dynamically via `getattr()` in the agent.

---

## Use Cases

### V1 Mode Use Cases

#### 1. API Testing
```json
{
  "rows": 100,
  "format": "json",
  "fields": ["name", "email", "password"]
}
```

#### 2. Database Seeding
```json
{
  "rows": 10000,
  "format": "csv",
  "fields": ["name", "email", "phone", "address", "company"]
}
```

### V2 Mode Use Cases

#### 1. E-commerce Testing
Generate complete e-commerce dataset with relationships:
```json
{
  "rows": 1000,
  "domain": "ecommerce",
  "realism_level": "high",
  "format": "json"
}
```

#### 2. SaaS Platform Simulation
Generate realistic SaaS user and subscription data:
```json
{
  "rows": 500,
  "domain": "saas",
  "realism_level": "medium",
  "format": "csv"
}
```

#### 3. Custom Domain Modeling
Use LLM to design schemas for specific use cases:
```json
{
  "rows": 200,
  "prompt": "Create a library management system with books, authors, and checkouts",
  "realism_level": "high",
  "format": "json"
}
```

#### 4. Data Quality Testing
Test how applications handle imperfect data:
```json
{
  "rows": 1000,
  "domain": "ecommerce",
  "realism_level": "high",
  "format": "json"
}
```
*Includes 10% nulls, 2% duplicates, 1% outliers*

---

## Performance

| Dataset Size | Mode | Execution Time | Use Case |
|--------------|------|----------------|----------|
| 10 rows | V1 | \u003c 0.1s | Quick tests |
| 100 rows | V1 | \u003c 0.5s | Prototyping |
| 100 rows | V2 (3 entities) | \u003c 2s | Multi-entity testing |
| 1,000 rows | V1 | \u003c 2s | Development |
| 1,000 rows | V2 (3 entities) | \u003c 5s | Relational data |
| 10,000 rows | V1 | \u003c 5s | Load testing |

---

## Implementation Details

### Technology Stack
- **Faker** 28.0.0 - Realistic fake data generation (V1)
- **Pandas** 2.2.0 - Data manipulation and formatting
- **FastAPI** - Async endpoint handling
- **Pydantic** - Schema validation (V2)
- **NumPy** - Statistical distributions (V2)
- **LangChain** - LLM integration for schema design (V2)

### Architecture (Phase 1 - 3-Layer Semantic)

```
User Request
    ↓
Gateway (/api/gateway)
    ↓
DataGen Agent (mode router + feature flag)
    ↓
┌─────────────────────────────────────────────┐
│ V1 Mode            │ V2 Mode (Phase 1)      │
│ Faker + Pandas     │ 3-Layer Semantic       │
└────────────────────┴────────────────────────┘
                          ↓
    ┌─────────────────────────────────────────┐
    │ Layer 1: Semantic Understanding         │
    │ ┌─────────────────────────────────────┐ │
    │ │ Lexical → Pattern → Context → LLM  │ │
    │ │ (classification only, no values!)  │ │
    │ └─────────────────────────────────────┘ │
    └─────────────────────────────────────────┘
                          ↓
    ┌─────────────────────────────────────────┐
    │ Layer 2: Generator Selection            │
    │ SemanticRouter (type → generator map)  │
    └─────────────────────────────────────────┘
                          ↓
    ┌─────────────────────────────────────────┐
    │ Layer 3: Value Production               │
    │ Faker + Catalogs (NEVER LLM!)          │
    └─────────────────────────────────────────┘
                          ↓
                JSON/CSV Output
```

### Workflow & Internals

The Phase 1 architecture follows a strict pipeline to ensure data quality and prevent LLM hallucinations.

#### 1. Schema Design
- **Input:** User prompt (e.g., "Generate 100 users with zip codes")
- **Process:** `SchemaDesigner` uses an LLM to convert the prompt into a structured JSON schema defining entities, fields, and constraints (enum, pattern, min/max).
- **Output:** JSON Schema (e.g., `{"users": {"fields": {"zip_code": {"type": "string"}}}}`)

#### 2. Semantic Analysis (5-Tier Pipeline)
The `SemanticAnalyzer` determines the *meaning* of each field using a waterfall approach:
1.  **Tier 1: Lexical (Fastest)**: Checks `lexical_dict.py` for exact matches (e.g., "zip_code" → `ZIP_CODE`). Covers 303 common field mappings.
2.  **Tier 2: Pattern (Fast)**: Checks `PatternClassifier` for regex matches on field names (e.g., `*_id` → `UUID`, `is_*` → `BOOLEAN`).
3.  **Tier 3: Context (Heuristic)**: Checks `ContextClassifier` for entity-specific meanings (e.g., `product.name` → `PRODUCT_NAME` vs `person.name` → `PERSON_FULL_NAME`).
4.  **Tier 4: LLM (Fallback)**: Uses `LLMClassifier` to analyze ambiguous fields based on name and description. Returns *metadata only* (semantic type), never data values.
5.  **Tier 5: Fallback**: Defaults to `UNKNOWN` (generates generic text).

#### 3. Generator Selection
- **Input:** Semantic Type (e.g., `ZIP_CODE`)
- **Process:** `SemanticRouter` maps the type to a specific generator function.
- **Routing:**
    - `ZIP_CODE` → `faker.zipcode()`
    - `PRODUCT_NAME` → `CatalogFactory` (cached list of products)
    - `PATTERN` → `rstr.xeger()` (regex generation)

#### 4. Value Production
- **Process:** The selected generator produces a value for each row.
- **Constraint Enforcement:**
    - **Enums:** Randomly selects from allowed values.
    - **Patterns:** Generates string matching the regex.
    - **Ranges:** Generates number within min/max.
- **Realism:** `_apply_realism` injects nulls (if nullable) and outliers based on `realism_level`.

#### 5. Output Formatting
- **Process:** Data is formatted as JSON or CSV.
- **Metadata:** Performance metrics and semantic analysis confidence scores are attached.

### Code Location
- **Agent:** `src/agents/datagen/agent.py` (V1/V2 router + feature flag)
- **V1 Tools:** `src/tools/datagen/tools.py`
- **Phase 1 Components:**
  - Semantic Types: `src/tools/datagen/semantic_types.py`
  - Lexical Dictionary: `src/tools/datagen/lexical_dict.py` (303 mappings)
  - Lexical Classifier: `src/tools/datagen/lexical_classifier.py`
  - Pattern Classifier: `src/tools/datagen/pattern_classifier.py`
  - Context Classifier: `src/tools/datagen/context_classifier.py`
  - LLM Classifier: `src/tools/datagen/llm_classifier.py`
  - Semantic Analyzer: `src/tools/datagen/semantic_analyzer_v2.py`
  - Catalog Factory: `src/tools/datagen/catalog_factory.py`
  - Semantic Router: `src/tools/datagen/semantic_router.py`

  - **Orchestrator:** `src/tools/datagen/advanced_generator_v2.py` (Main engine - Phase 1)
- **V2 Legacy Components (not used in Phase 1):**
  - Schema Designer: `src/tools/datagen/schema_designer.py` (used for schema design)
  - Relationship Engine: `src/tools/datagen/relationship_engine.py` (exists but not used in `advanced_generator_v2.py`)
  - Realism Engine: `src/tools/datagen/realism_engine.py` (simplified realism in V2 generator)
- **Tests:** `tests/test_semantic_analyzer_v2.py`, `tests/test_semantic_router.py`, `tests/test_datagen.py`, `tests/test_relationships.py`, `tests/test_realism.py`

---

## Validation & Robustness

The tool has been rigorously verified against complex production scenarios.

### "All-In-One" Stress Test
The following complex prompt verifies multi-entity logic, regex patterns, context classification, and new semantic types in a single request:

```bash
curl -X POST "http://localhost:8001/api/gateway" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 20,
      "format": "json",
      "prompt": "Generate a digital library and HR system. Entities: \n1. employees (employee_id pattern: \"^EMP-[0-9]{5}$\", name, title, email, job_title, ip_v6, mac_address)\n2. books (isbn pattern: \"^978-[0-9]{10}$\", title, author, genre enum:[\"Fiction\",\"Non-Fiction\",\"Sci-Fi\"])\n3. libraries (name, city, street_address, zip_code)\n4. checkouts (id, employee_id FK, book_id FK, library_id FK, status enum:[\"active\",\"returned\",\"overdue\"], checkout_date). \nEnsure employees have unique IPs and checkouts link correctly.",
      "realism_level": "high",
      "enable_semantic_generation": true
    }
  }'
```

**Verified Capabilities:**
- ✅ **Context Refinement:** Distinguishes `book.title` (Product Name) from `employee.title` (Job Title).
- ✅ **Lexical Expansion:** Generates valid `ip_v6`, `mac_address`, `zip_code`, `street_address`.
- ✅ **Pattern Constraints:** Enforces `^EMP-[0-9]{5}$` and `^978-[0-9]{10}$` (ISBN) using `rstr`.
- ✅ **Enum Constraints:** Respects status enums (`active`, `returned`, `overdue`).
- ✅ **Multi-Entity:** Generates data for multiple entities (relationships tracked but foreign keys not validated in Phase 1).

### Known Limitations
- **Enum Extraction from Prompt:** While the tool supports enums defined in the schema, the LLM Schema Designer may occasionally miss specific enum values provided in a complex natural language prompt (e.g., specific book genres might default to a generic list).
- **Foreign Key Relationships:** In Phase 1, relationships are tracked in the schema but foreign keys are not validated or enforced during generation. The `RelationshipEngine` exists but is not used by `advanced_generator_v2.py`. Foreign key fields are generated as regular UUIDs/IDs without ensuring they reference existing parent records.
- **enable_semantic_generation Parameter:** This parameter is not part of the `DataGenArgs` Pydantic schema but is handled dynamically via `getattr()` in the agent. It defaults to `True` if the `ENABLE_SEMANTIC_ANALYZER` environment variable is set.

---

## Error Handling

### V1 Mode Errors

#### Invalid Row Count
```json
{
  "rows": 0,
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

#### Invalid Format
```json
{
  "rows": 10,
  "format": "xml"
}
```

**Response:**
```json
{
  "success": false,
  "message": "format must be 'json' or 'csv'"
}
```

### V2 Mode Errors

#### Invalid Domain
```json
{
  "rows": 100,
  "domain": "healthcare"
}
```

**Response:**
```json
{
  "success": false,
  "message": "Unknown domain: 'healthcare'. Available: ['ecommerce', 'saas']"
}
```

#### Invalid Realism Level
```json
{
  "rows": 100,
  "domain": "ecommerce",
  "realism_level": "extreme"
}
```

**Response:**
```json
{
  "success": false,
  "message": "realism_level must be one of: basic, medium, high"
}
```

---

## Testing

### Run Tests
```bash
# V1 tests (backward compatibility)
pytest tests/test_datagen.py -v

# V2 component tests
pytest tests/test_schema_designer.py -v
pytest tests/test_relationships.py -v
pytest tests/test_distributions.py -v
pytest tests/test_domain_templates.py -v
pytest tests/test_realism.py -v

# All tests
pytest tests/test_datagen.py tests/test_schema_designer.py tests/test_relationships.py tests/test_distributions.py tests/test_domain_templates.py tests/test_realism.py -v
```

### Test Coverage
- ✅ **180+ passing tests** across 8 test suites
- ✅ V1 backward compatibility (20 tests)
- ✅ Schema validation and LLM fallback (36 tests)
- ✅ **Phase 1 Semantic Analyzer (30 tests)** ← NEW
- ✅ **Phase 1 Semantic Router (20 tests)** ← NEW
- ✅ Relationship integrity (11 tests)
- ✅ Distribution accuracy (28 tests)
- ✅ Domain template validation (18 tests)
- ✅ Realism injection rates (17 tests)

#### Critical Tests
```bash
# Verify no LLM prose in output
pytest tests/test_semantic_analyzer_v2.py::TestEndToEnd::test_banking_example_no_llm_prose -v
```

---

## Best Practices

### V1 Mode
1. **Use appropriate row counts** - Start small, scale as needed
2. **Specify custom fields** - Only generate what you need
3. **Choose the right format** - JSON for APIs, CSV for imports

### V2 Mode
4. **Use domain templates** - Faster than LLM prompts for known use cases
5. **Start with basic realism** - Increase to medium/high as needed
6. **Note on relationships** - Foreign keys are generated but not validated in Phase 1. Manually verify FK integrity if needed.
7. **Monitor entity counts** - Balance parent/child ratios
8. **Test with realism** - Simulate real-world data quality issues
9. **Semantic generation** - Enabled by default via `ENABLE_SEMANTIC_ANALYZER` environment variable

---

## Migration from V1 to V2

### Backward Compatibility

All V1 requests continue to work unchanged:

```json
// V1: Still works exactly the same
{
  "rows": 100,
  "format": "json",
  "fields": ["name", "email"]
}
```

### Upgrading to V2

Add `domain` or `prompt` to enable V2 mode:

```json
// V2: Add domain parameter
{
  "rows": 500,
  "format": "json",
  "domain": "ecommerce",
  "realism_level": "medium"
}
```

---

## Troubleshooting

### V1 Issues

**Issue:** Slow generation for large datasets  
**Solution:** Use V2 mode which is optimized for multi-entity data

**Issue:** Memory errors with very large datasets  
**Solution:** Reduce row count or generate in batches

### V2 Issues

**Issue:** LLM schema design fails  
**Solution:** Automatic fallback to domain templates or minimal schema

**Issue:** Too few/many child records  
**Solution:** Adjust row counts or use domain templates with balanced ratios

**Issue:** Foreign keys don't match parent IDs  
**Solution:** This is a Phase 1 limitation. Foreign keys are generated but not validated. Consider post-processing or wait for Phase 2 relationship enforcement.

**Issue:** Need more domains beyond ecommerce/saas  
**Solution:** Use natural language prompts with LLM schema designer

---

## Related Tools

- `refine_prompt` - Optimize data generation prompts for V2 mode
- `retrieve_docs` - Search Faker and schema design documentation

---

## Changelog

### Version 1.0.0 (Phase 1 Refactor - December 2025)
- 🏗️ **3-Layer Semantic Architecture** - LLM confined to classification only
- 🔒 **Key Guarantee:** LLM never generates data values (fixes "Agent every" bug)
- 🆕 Multi-tier classification pipeline (lexical → pattern → context → LLM → fallback)
- 🆕 `semantic_types.py` - Core data models (`SemanticType`, `FieldContext`, `SemanticFieldInfo`)
- 🆕 `lexical_dict.py` - 303 field name → semantic type mappings
- 🆕 `pattern_classifier.py` - Regex-based suffix/prefix detection
- 🆕 `context_classifier.py` - Entity-aware name resolution
- 🆕 `llm_classifier.py` - LLM for classification metadata only
- 🆕 `semantic_analyzer_v2.py` - Multi-tier pipeline orchestrator
- 🆕 `catalog_factory.py` - L1/L2 caching for value catalogs
- 🆕 `semantic_router.py` - Semantic type → Faker/catalog routing
- 🆕 `advanced_generator_v2.py` - Integrated generator with metadata
- 🆕 Feature flag: `ENABLE_SEMANTIC_ANALYZER` environment variable
- 🆕 Full observability: metadata with source, confidence, warnings
- ✅ 50 new Phase 1 tests
- ✅ 180+ total passing tests

### Version 0.9.0 (Phase 8.6 - December 2025)
- ✨ Semantic field analysis (initial implementation)
- ✨ Domain-specific value catalogs
- ⚠️ Bug: LLM sometimes generated prose as values

### Version 0.8.0 (Phase 8 - December 2025)
- 🆕 V2 mode with advanced multi-entity generation
- 🆕 LLM-powered schema design from natural language
- 🆕 Domain templates for ecommerce and SaaS
- ✅ 130 passing tests

### Version 0.7.0 (Phase 7 - December 2025)
- ✅ Original Faker-based generation (V1 mode)

---

**Last Updated:** December 11, 2025  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
