# generate_data - Advanced Synthetic Data Generation Tool

**Tool Name:** `generate_data`
**Version:** 0.9.0 (Catalog-Sandbox + Realism Consolidation)
**Phase:** Phase 1 (3-Layer Semantic Architecture) + v0.9 catalog-sandbox
**Status:** Beta — production-grade for known domains, off-template prompts now LLM-cataloged

> **v0.9 Production-Grade (Catalog-Sandbox):**
> - **Per-entity batched LLM catalogs**: every string field gets a domain-realistic value catalog (50 values per field), generated in one LLM call per entity, cached L1+L2 with 1h TTL. Replaces the v0.8 Faker `_smart_free_text` fallback for unknown semantic types.
> - **SchemaValidator**: post-LLM schema fixes (enum-swap correction + range inference for numeric fields without explicit min/max).
> - **Realism consolidation**: V2's dead-code dual realism implementation is gone. Single call to `realism_engine.apply_realism_to_data` handles nulls + duplicates + outliers per `REALISM_CONFIGS`.
> - **Domain templates mark fields nullable**: `customers.phone`, `customers.address`, `products.category`, `products.description`, `users.phone`, `users.last_login`, `subscriptions.cancellation_reason`, `usage_logs.error_message`, `devices.last_seen`, `readings.error_code` are now nullable so `realism_level="high"` actually injects the documented ~10% nulls.
>
> **Behavior change**: `realism_level="high"` on the `ecommerce` / `saas` / `iot_devices` domains now produces 5-15% nulls in the fields listed above. Previous v0.8 behavior produced 0% nulls. Update test assertions and downstream consumers accordingly.

---

## Overview

The `generate_data` tool generates realistic synthetic data with two operational modes:

- **V1 Mode (Simple)**: Original Faker-based generation for backward compatibility
- **V2 Mode (Advanced)**: LLM-powered schema design + per-entity catalog-sandbox + multi-entity relationships + data-quality realism

Perfect for testing, prototyping, development workflows, and generating complex relational datasets.

**Phase 1 Refactor (v0.8):** LLM is confined to **classification + catalog generation only** — it never generates per-row data values directly. All values come from Faker or LLM-pre-generated catalogs (the catalog is metadata; row sampling is deterministic).

**v0.9 Catalog-Sandbox:** Every string field on every V2 entity gets a domain-realistic value catalog from a single per-entity LLM call (cached L1/L2 with 1h TTL). Replaces the v0.8 Faker `_smart_free_text` fallback for unknown semantic types — `instrument_name` returns `"Spectrophotometer"` not `"Agent every development say."`; `measurement_unit` returns `"Pascal"` not `"perform"`. See [v0.9 spec](../../../docs/superpowers/specs/2026-05-15-generate-data-production-grade-design.md).

> [!IMPORTANT]
> **Key Guarantee:** LLM outputs are metadata (semantic types, constraint hints, value catalogs), never per-row data values. The generator samples from catalogs via `random.choice`; values themselves are never LLM-streamed prose.

---

## Features

### V1 Mode (Backward Compatible)
- ✅ Generate realistic mock data with Faker library
- ✅ Support for CSV and JSON output formats
- ✅ Customizable field selection
- ✅ Configurable row counts (1-10,000 rows; Pydantic gate, V2 internal allows 100,000 but Pydantic blocks earlier)
- ✅ Fast execution (\u003c 1s for small datasets)

### V2 Mode (Phase 1 + v0.9 Catalog-Sandbox)
- 🆕 **LLM-powered schema design** from natural language prompts
- 🆕 **SchemaValidator** (v0.9) - post-LLM enum-swap fix + range inference for numeric fields without explicit min/max
- 🆕 **Domain templates** for `ecommerce`, `saas`, `iot_devices` use cases
- 🆕 **Per-entity catalog-sandbox** (v0.9) - one LLM call per entity returns 50 realistic values per string field; cached L1/L2
- 🆕 **Multi-entity generation** - generates data for multiple related entities with FK linkage
- 🆕 **Semantic field analysis** - understands field context (e.g., `flowers.name` vs `person.name`)
- 🆕 **Data quality realism** (v0.9 consolidated) - nulls + duplicates + outliers via single `realism_engine.apply_realism_to_data` call
- 🆕 **Relationship-aware generation** - foreign keys enforced during generation, validated via `fk_integrity` block

### Phase 1 (3-Layer Semantic Architecture)
- 🏗️ **Layer 1: Semantic Understanding** - Multi-tier classification (lexical → pattern → context → LLM → fallback)
- 🏗️ **Layer 2: Generator Selection** - Semantic type → generator mapping via `SemanticRouter`
- 🏗️ **Layer 3: Value Production** - Faker/catalogs only, **never LLM**
- ✨ **299 lexical mappings** - Fast dictionary-based field name recognition
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
| `rows` | integer | ✅ Yes | - | Number of rows to generate (1-10,000, enforced by Pydantic; V2 internal allows up to 100,000 but Pydantic blocks earlier) | V1, V2 |
| `format` | string | No | `"json"` | Output format: `"json"` or `"csv"` | V1, V2 |
| `fields` | array[string] | No | Default fields | Custom fields to generate | V1 only |
| `prompt` | string | No | `null` | Natural language schema description | V2 only |
| `domain` | string | No | `null` | Pre-defined domain: `"ecommerce"`, `"saas"`, or `"iot_devices"` | V2 only |
| `realism_level` | string | No | `"basic"` | Data quality level: `"basic"`, `"medium"`, `"high"` | V2 only |
| `enable_semantic_generation` | boolean | No | `true` | Enable Phase 1 semantic analysis for context-aware values | V2 only |

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

> [!NOTE]
> **v0.9 update:** Domain templates now mark business-domain fields as `nullable=True` so realism levels actually inject the documented rates. Verified via MCP at 2000-row scale: `customers.phone` 10.4% null, `customers.address` 10.7% null at `realism_level="high"` (target 10%, ±5% sampling jitter at lower row counts).
>
> Nullable fields per domain:
> - **ecommerce**: `customers.phone`, `customers.address`, `products.category`, `products.description`
> - **saas**: `users.phone`, `users.last_login`, `subscriptions.cancellation_reason`, `subscriptions.expires_at`, `usage_logs.error_message`
> - **iot_devices**: `devices.last_seen`, `readings.error_code`

> [!IMPORTANT]
> **Critical Field Protection:** To maintain data integrity, the following semantic types are **never** injected with nulls, even if nullable in the schema:
> `email_address`, `phone_number`, `uuid`, `numeric_id`, `timestamp`, `date`, `bank_account_number`, `transaction_id`. Verified via MCP — at `realism_level="high"` on 308 customers, `email`, `id`, and `created_at` all showed 0 nulls.

---

## V1 Mode: Simple Generation (Backward Compatible)

### Supported Fields

When `fields` is not specified, default fields are generated:
- `name`, `email`, `address`, `phone`, `company`, `job`, `date_of_birth`, `city`

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
**Relationships:** orders → customers (1:N), orders → products (1:N) (enforced during generation and validated via `fk_integrity`)  
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
**Relationships:** subscriptions → users (1:N), usage_logs → subscriptions (1:N) (enforced during generation and validated via `fk_integrity`)  
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

#### IoT Devices Domain
**Entities:** devices, readings  
**Relationships:** readings → devices (1:N)  
**Distributions:** Normal distribution for reading values  
**Default Counts:** 100 devices, 1000 readings

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {
      "rows": 500,
      "domain": "iot_devices",
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

---

## MCP Protocol (JSON-RPC 2.0)

The tool is fully compliant with the **Model Context Protocol (MCP)**. Use the `/mcp` endpoint for standardized tool calling.

### MCP: List Tools
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

### MCP: Generate Data (V2 Mode)
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "generate_data",
      "arguments": {
        "rows": 50,
        "prompt": "Generate a list of 50 vintage cars with year and manufacturer",
        "enable_semantic_generation": true
      }
    }
  }'
```

> [!TIP]
> **Success Mapping:** The MCP endpoint maps the tool's internal `success` status directly to MCP's `isError` field. If constraints are violated or FK integrity fails, `isError` will be `true`, allowing the LLM to recognize the failure automatically.

---

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

> **Note:** `semantic_generation_used` field indicates whether Phase 1 semantic analysis was successfully applied. `false` means fallback to Faker was used.

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

LLM-bound for V2 modes — the free Ollama endpoint (currently `gpt-oss:20b-cloud`) dominates wall-clock time. Measured on the live MCP container at v0.9:

| Scenario | Mode | Cold (no cache) | Warm (L2 hit) | Use Case |
|----------|------|-----------------|---------------|----------|
| 5–10 rows | V1 (Faker) | < 0.1s | — | Quick mock users |
| 1,000 rows | V1 (Faker, CSV) | ~1s | — | Development seed |
| 10,000 rows | V1 (Faker, CSV, max) | ~3s | — | Load testing |
| 50–500 rows | V2 domain (template, no schema-design LLM) | 9–17s | 5–10s | Realistic ecommerce / saas / iot |
| 100–500 rows | V2 prompt (1 schema-design LLM + N entity-catalog LLM calls) | 15–30s | 5–10s | Novel domains |
| 2,000 rows | V2 domain ecommerce, realism=high | ~45s | ~30s | Stress + realism scale-out |

> **Why V2 cold-cache is slow:** Schema design takes 4–6s (LLM call #1) and each entity catalog adds 3–4s (LLM call #N). For a 3-entity domain that's 4 LLM calls. The L2 cache (1h TTL, keyed by `entity+fields_hash+prompt_hash`) amortizes within minutes for repeat prompts.

> **Frontend integration:** `progress_callback` at `routers/__init__.py:1162-1168` emits stage events (`schema_design 20% → semantic_analysis 40% → catalog_generation 60% → row_generation 80% → complete 100%`). Subscribe instead of showing a blocking spinner.

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

### Workflow & Internals (v0.9 pipeline)

The v0.9 pipeline adds two stages (SchemaValidator + Catalog-Sandbox) on top of the Phase 1 architecture, while keeping the strict "LLM never returns per-row values" guarantee.

#### 1. Schema Design (LLM call #1)
- **Input:** User prompt (e.g., "Generate 100 users with zip codes")
- **Process:** `SchemaDesigner` uses an LLM to convert the prompt into a structured JSON schema defining entities, fields, and constraints (enum, pattern, min/max). The system prompt (`SCHEMA_DESIGN_PROMPT`) was updated in v0.9 with explicit nullable-marking instructions and few-shot examples.
- **Output:** `SchemaDesign` Pydantic object with entities, fields, relationships.

#### 2. SchemaValidator (v0.9, pure function — no LLM)
- **Input:** `SchemaDesign` from step 1 + the original user prompt.
- **Process:** Two post-LLM corrections:
    - **Enum-swap fix:** Match `<field> enum: [...]` patterns in the prompt and force the LLM-supplied values onto the named field. Clear the same values from any other field that received them by mistake (fixes the v0.8 stress-test bug where `genre` got `{active, pending}` instead of `{Fiction, Non-Fiction, Sci-Fi}`).
    - **Range inference:** For any numeric field with no explicit `min`/`max`, look up sane defaults in `RANGE_HINTS` by field-name pattern (longest-match wins). Examples: `bedroom_count` → `(1, 6)`, `age` → `(1, 120)`, `year_built` → `(1900, 2030)`, `square_feet` → `(200, 20000)`.
- **Output:** Corrected `SchemaDesign`. Pure function — no side effects, deterministic.

#### 3. Semantic Analysis (5-Tier Pipeline)
The `SemanticAnalyzer` determines the *meaning* of each field using a waterfall approach:
1.  **Tier 1: Lexical (Fastest)**: Checks `lexical_dict.py` for exact matches (e.g., "zip_code" → `ZIP_CODE`). Covers 299 common field mappings.
2.  **Tier 2: Pattern (Fast)**: Checks `PatternClassifier` for regex matches on field names (e.g., `*_id` → `UUID`, `is_*` → `BOOLEAN`).
3.  **Tier 3: Context (Heuristic)**: Checks `ContextClassifier` for entity-specific meanings (e.g., `product.name` → `PRODUCT_NAME` vs `person.name` → `PERSON_FULL_NAME`).
4.  **Tier 4: LLM (Fallback)**: Uses `LLMClassifier` to analyze ambiguous fields based on name and description. Returns *metadata only* (semantic type), never data values.
5.  **Tier 5: Fallback**: Defaults to `UNKNOWN` / `FREE_TEXT` — historically the lorem-ipsum source; in v0.9 the catalog-sandbox handles these cases first.

#### 4. Catalog-Sandbox precompute (v0.9, LLM call per entity)
- **Input:** For each entity, the list of `(field_name, "string")` pairs plus the user prompt.
- **Process:** `CatalogFactory.get_entity_catalogs(entity_name, fields, user_prompt, count=50)` issues a single LLM call returning a JSON object `{field_name: [50 realistic values], ...}`. Cached via:
    - **L1** (request-scope, key `entity_catalog:{entity}:{fields_hash}:{prompt_hash}`)
    - **L2** (process-scope, 1h TTL, same key)
- **Fallback:** If the LLM call fails, returns malformed JSON, or yields < 40 items per field, falls back per-field to `_smart_field_fallback` (Faker `catch_phrase` for `_name` fields, short sentences for `description`, `faker.email/phone/city/country` for known suffixes, `faker.word()` otherwise). Never produces placeholder garbage like `<field>_value_1`.
- **Output:** `Dict[str, List[str]]` — one catalog per string field.

#### 5. Generator Selection & Value Production
- **Input:** Semantic Type + `field_catalog` (from step 4, if applicable).
- **Process:** `SemanticRouter.generate_value(...)` routes per row:
    - **Constraint-first:** `enum` > `pattern` > catalog-sandbox > registered semantic-type generator > smart-free-text fallback.
    - **v0.9 catalog-sandbox branch:** If the classifier landed on `free_text` / `unknown` / `enum_value`-without-values AND a `field_catalog` was supplied, sample from it via `random.choice`. Known semantic types (email, person_name, uuid, etc.) ignore the catalog and use their dedicated generators.
- **Output:** Per-row values for every entity.

#### 6. Validation & Safety (Invariant 3)
- **Constraint check:** Every generated value verified against schema constraints (pattern, enum, min/max, nullable). Violations land in `data.constraint_violations`.
- **FK integrity:** `RelationshipEngine._validate_fk_integrity` confirms every foreign key references a real parent row. Surfaces as `data.fk_integrity.{valid, errors, statistics}` (per-relationship: total_children, parents_with_zero_children, orphaned_children).
- **Strict safety:** If *any* row violates constraints OR `fk_integrity.valid == false`, the entire dataset for that entity is **cleared** and `_internal_success` is set to `false`.

#### 7. Realism (v0.9 consolidated)
- **Process:** Single call to `realism_engine.apply_realism_to_data(generated_data, schema_design, realism_level)` — replaces V2's old inline `_apply_realism` (deleted in v0.9; the v0.8 dual-implementation was applying realism twice).
- **Injection:** Per `REALISM_CONFIGS` — medium=5% nulls, high=10% nulls + 2% duplicates + 1% outliers. Respects critical-field protection AND the schema's `nullable` flag (gated by domain template updates).

#### 8. Output Formatting
- **Process:** Data is formatted as JSON (native arrays) or CSV (strings per entity).
- **Metadata:** Performance metrics (`analysis_ms`, `generation_ms`, `total_ms`), semantic-analysis source counts (lexical/pattern/context/llm/fallback), and the `_internal_success` flag are attached.

### Code Location
- **Agent:** `src/agents/datagen/agent.py` (V1/V2 router + feature flag)
- **V1 Tools:** `src/tools/datagen/tools.py`
- **Phase 1 Components:**
  - Semantic Types: `src/tools/datagen/semantic_types.py`
  - Lexical Dictionary: `src/tools/datagen/lexical_dict.py` (299 mappings)
  - Lexical Classifier: `src/tools/datagen/lexical_classifier.py`
  - Pattern Classifier: `src/tools/datagen/pattern_classifier.py`
  - Context Classifier: `src/tools/datagen/context_classifier.py`
  - LLM Classifier: `src/tools/datagen/llm_classifier.py`
  - Semantic Analyzer: `src/tools/datagen/semantic_analyzer_v2.py`
  - Catalog Factory: `src/tools/datagen/catalog_factory.py` (v0.9 adds `get_entity_catalogs`)
  - Semantic Router: `src/tools/datagen/semantic_router.py` (v0.9 adds `field_catalog` param)
- **v0.9 Components (new):**
  - **Schema Validator:** `src/tools/datagen/schema_validator.py` (enum-swap fix + range inference, pure function)
- **Orchestrator:** `src/tools/datagen/advanced_generator_v2.py` (v0.9: wires SchemaValidator, per-entity catalog precompute, consolidated realism — internal `_apply_realism` deleted)
- **V2 Supporting Components:**
  - Schema Designer: `src/tools/datagen/schema_designer.py` (v0.9: prompt updated with nullable-marking rules + examples)
  - Relationship Engine: `src/tools/datagen/relationship_engine.py` (FK linkage during generation + `validate_relationships()` post-validation)
  - Realism Engine: `src/tools/datagen/realism_engine.py` (v0.9: single source of truth — V2 internal `_apply_realism` was deleted, now routes here)
  - Domain Templates: `src/tools/datagen/domain_templates.py` (v0.9: `nullable=True` markers on business-domain fields)
- **Tests (v0.9 adds 3 new files):**
  - Existing: `tests/test_semantic_analyzer_v2.py`, `tests/test_semantic_router.py`, `tests/test_datagen.py`, `tests/test_relationships.py`, `tests/test_realism.py`, `tests/test_domain_templates.py`, `tests/test_distributions.py`, `tests/test_schema_designer.py`
  - **New in v0.9:** `tests/test_schema_validator.py` (13 tests), `tests/test_catalog_sandbox.py` (10 tests), `tests/test_realism_consolidation.py` (3 tests)

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
- ✅ **Multi-Entity:** Generates data for multiple entities; foreign keys are enforced via `_generate_with_relationships` and validated by `_validate_fk_integrity`. The response includes an `fk_integrity` block with `valid`, `errors`, and `statistics` (per-relationship `total_children`, `total_parents`, `parents_with_children`, `parents_with_zero_children`, `orphaned_children`).

### Known Limitations
- **NL constraint extraction:** The LLM schema designer occasionally drops natural-language constraints embedded in prompts (e.g. `duration_minutes between 15 and 120` or inline regex patterns). v0.9 SchemaValidator handles enum-swap and range inference for fields with no explicit constraints, but it cannot recover constraints the LLM didn't transcribe into the schema in the first place. **Workaround:** keep prompt enums in the `field enum: ["A","B"]` form (SchemaValidator parses these reliably).
- **Schema non-determinism:** Same prompt → potentially different schema (entity names, field counts) across calls, because the LLM schema designer is non-deterministic. This defeats the entity-catalog cache when the LLM picks different entity names (`cocktail` vs `cocktails`). Reproducibility (optional `seed` argument + schema-hash cache) deferred to v0.10.
- **Cold-cache latency:** First V2-prompt call against the free Ollama endpoint takes 15–25s (schema design + per-entity catalog generation). Warm-cache (within 1h L2 TTL, same prompt + entity names): 5–10s. Frontend should subscribe to the existing `progress_callback` (`routers/__init__.py:1162-1168`) for staged progress UI.
- **Doc/version drift:** `manifests/devforge.json` is at `0.10.0`, this doc is at `0.9.0`, `src/main.py` and `Dockerfile` carry separate version stamps. Reconciliation to a single source of truth is deferred to v0.10.
- **enable_semantic_generation parameter:** Typed `bool` field on `DataGenArgs` (default `True`). The `ENABLE_SEMANTIC_ANALYZER` environment variable acts as the system-level feature flag. Setting either to `False` disables both the analyzer AND the v0.9 catalog-sandbox, restoring v0.7 Faker-only behavior.

### Invariant Enforcement
The tool now strictly enforces data quality invariants:
- **Invariant 3 (No Post-Hoc Fixing):** Invalid data is detected and withheld, never silently "fixed" or returned.
- **Invariant 8 (Deterministic Success):** Success is boolean. If validation fails, `success` is `False` and data is empty.

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
  "message": "Unknown domain: 'healthcare'. Available: ['ecommerce', 'saas', 'iot_devices']"
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

#### Constraint & Integrity Failures
If generated data violates schema constraints (pattern, enum, min/max) or foreign key integrity:

```json
{
  "success": false,
  "data": {},
  "constraint_violations": [
    {
      "entity": "users",
      "field": "age",
      "value": 15,
      "constraint": "min",
      "expected": 18
    }
  ]
}
```
*Data is withheld to prevent using invalid data.*

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

### Test Coverage (v0.9)
- ✅ **221 passing tests** across all suites (51 new in v0.9; 2 pre-existing `test_agent_invalid_*` failures predate v0.9)
- ✅ V1 backward compatibility (`test_datagen.py`)
- ✅ Schema designer + LLM fallback (`test_schema_designer.py`)
- ✅ Phase 1 Semantic Analyzer (`test_semantic_analyzer_v2.py` — 14 sync-vs-async failures predate v0.9, deferred to test-modernization)
- ✅ Semantic Router (`test_semantic_router.py` — extended in v0.9 with 7 catalog-sandbox tests)
- ✅ Relationship integrity (`test_relationships.py`)
- ✅ Distribution accuracy (`test_distributions.py`)
- ✅ Domain template validation (`test_domain_templates.py` — extended in v0.9 with `nullable` markers)
- ✅ Realism injection rates (`test_realism.py`)
- ✅ **NEW v0.9 SchemaValidator (13 tests)** — `test_schema_validator.py`
- ✅ **NEW v0.9 Catalog-Sandbox (10 tests)** — `test_catalog_sandbox.py`
- ✅ **NEW v0.9 Realism consolidation (3 tests)** — `test_realism_consolidation.py`

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
6. **Note on relationships** - Foreign keys are enforced during generation and validated via `_validate_fk_integrity`; check the `fk_integrity` block in the response for per-relationship statistics.
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
**Solution:** Foreign keys are enforced via `_generate_with_relationships` and validated by `_validate_fk_integrity`. Inspect the `fk_integrity` block in the response (`valid`, `errors`, and per-relationship `statistics`) to confirm referential integrity.

**Issue:** Need more domains beyond ecommerce/saas  
**Solution:** Use natural language prompts with LLM schema designer

---

## Related Tools

- `refine_prompt` - Optimize data generation prompts for V2 mode
- `retrieve_docs` - Search Faker and schema design documentation

---

## Changelog

### Version 0.9.0 (2026-05-15 — Catalog-Sandbox + Realism Consolidation)
- 🆕 **`SchemaValidator`** (new module `src/tools/datagen/schema_validator.py`): post-LLM enum-swap fix + range inference for numeric fields without explicit min/max. Pure function; no LLM calls. Fixes the v0.8 stress-test bug where `genre` enum got `{active, pending}` instead of `{Fiction, Non-Fiction, Sci-Fi}`.
- 🆕 **Per-entity catalog-sandbox**: `CatalogFactory.get_entity_catalogs()` issues one LLM call per entity returning `{field_name: [50 realistic values]}`. Cached via L1 (request) + L2 (process, 1h TTL). Replaces v0.8 Faker `_smart_free_text` fallback. Verified production-grade: `Spectrophotometer` / `Beta Particle Counter` for instruments, `Pascal` / `Newton` / `Coulomb` for units, `Mojito` / `Rob Roy` for cocktails.
- 🔧 **Realism consolidation**: deleted V2's internal `_apply_realism` (double-application bug + only-nulls implementation). All realism now routes through `realism_engine.apply_realism_to_data` — single source of truth, handles nulls + duplicates + outliers per `REALISM_CONFIGS`.
- 🔧 **Schema designer prompt updated**: explicit `nullable: true|false` instructions + few-shot examples (always-nullable: `middle_name`, `last_login`, `description`, `notes`, `cancellation_reason`, `error_message`; never-nullable: `id`, `email`, `created_at`, FKs).
- 🔧 **Domain templates marked nullable**: `customers.phone`, `customers.address`, `products.category`, `products.description`, `users.phone`, `users.last_login`, `subscriptions.cancellation_reason`, `usage_logs.error_message`, `devices.last_seen`, `readings.error_code`. Verified at 2000-row scale: 10.4% null on `phone`, 10.7% null on `address` at `realism_level="high"`.
- 🔧 **MCP tool description rewritten**: now teaches calling agents the 3-mode model (V1 / V2 domain / V2 prompt) with cold/warm cache latency expectations. Row bound corrected from misleading `1-100000` to actual Pydantic gate `1-10000`.
- 🔒 **Critical-field protection verified at scale**: `id`, `email`, `created_at`, `uuid`, `*_id` foreign keys show 0% nulls across 308 customers + 820 usage_logs + 455 IoT readings at `realism_level="high"`.
- ✅ **51 new tests** (13 SchemaValidator + 10 Catalog-Sandbox + 7 router-extension + 18 domain-template extensions + 3 realism-consolidation). Total: 221 passing tests.
- ✅ Earlier session fixes folded in: v0.8.5 silent-failure cascade (NameError `user_id`) and success-calculation fix; field-name-aware `_smart_free_text` fallback in semantic_router (extended numeric-suffix coverage).
- 📊 **Cold-cache latency**: V2 prompt mode now 15–30s on free Ollama (4 LLM calls: 1 schema + N entity catalogs). Warm-cache (within 1h L2 TTL, same entity names): 5–10s. Frontend should use `progress_callback` for staged UI.

### Version 0.8.0 (Phase 1 Refactor - matches manifest)
- 🏗️ **3-Layer Semantic Architecture** - LLM confined to classification only
- 🔒 **Key Guarantee:** LLM never generates data values (fixes "Agent every" bug)
- 🆕 Multi-tier classification pipeline (lexical → pattern → context → LLM → fallback)
- 🆕 `semantic_types.py` - Core data models (`SemanticType`, `FieldContext`, `SemanticFieldInfo`)
- 🆕 `lexical_dict.py` - 299 field name → semantic type mappings
- 🆕 `pattern_classifier.py` - Regex-based suffix/prefix detection
- 🆕 `context_classifier.py` - Entity-aware name resolution
- 🆕 `llm_classifier.py` - LLM for classification metadata only
- 🆕 `semantic_analyzer_v2.py` - Multi-tier pipeline orchestrator
- 🆕 `catalog_factory.py` - L1/L2 caching for value catalogs
- 🆕 `semantic_router.py` - Semantic type → Faker/catalog routing
- 🆕 `advanced_generator_v2.py` - Integrated generator with metadata
- 🆕 V2 mode with advanced multi-entity generation
- 🆕 LLM-powered schema design from natural language
- 🆕 Domain templates for ecommerce, SaaS, and IoT devices
- 🆕 Feature flag: `ENABLE_SEMANTIC_ANALYZER` environment variable
- 🆕 Full observability: metadata with source, confidence, warnings
- ✅ 169 total passing tests

### Version 0.7.0 (Phase 7 - December 2025)
- ✅ Original Faker-based generation (V1 mode)

---

**Last Updated:** 2026-05-15
**Maintainer:** DevForge Team
**Feedback:** Create an issue in the repository

---

## Recent Updates in generate_data Mode

### 1. Strict Validation & Safety Invariants
- **Previous Behavior:** Data with minor constraint violations might have been returned with warnings.
- **Current Behavior:** Implements **Invariant 3 (Invalid values must never be returned)**. If any constraint violation is detected (Regex, Enum, Min/Max) or Foreign Key integrity fails, the generator strictly returns **empty data** and marks `success: false`.
- **Impact:** Guarantees 100% compliant data consumption. Users must handle `success: false` explicitly.

### 2. Protected Critical Semantic Types
- **Previous Behavior:** Realism engine could inject nulls into any nullable field.
- **Current Behavior:** The following semantic types are now **protected** and will NEVER be null, even if nullable and high realism is selected: `email_address`, `phone_number`, `uuid`, `numeric_id`, `timestamp`, `date`, `bank_account_number`, `transaction_id`.
- **Impact:** Prevents "realistic" data from breaking core application logic (e.g., missing IDs or timestamps).

### 3. Constraint Precedence
- **Behavior:** Explicit precedence logic for generator selection: **Enum > Pattern > Min/Max**.
- **Impact:** Ensures that if a field has both a regex pattern and an enum, the enum values are strictly respected, preventing generation of valid-looking but disallowed values.
