# V2 Pipeline Audit Report - generate_data Tool

**Date:** December 2025  
**Audit Scope:** Execution trace from `agent.py` → `advanced_generator_v2.py` → `semantic_analyzer_v2.py` → `semantic_router.py` → realism → output

---

## Execution Flow Trace

### 1. Entry Point: `src/agents/datagen/agent.py`
- **Function:** `datagen_agent()` (line 23)
- **V2 Detection:** Line 67: `use_v2 = datagen_args.prompt is not None or datagen_args.domain is not None`
- **V2 Call:** Line 75: `result = await generate_advanced_data(...)` → calls `advanced_generator_v2.generate_advanced_data_v2`

### 2. Schema Design: `src/tools/datagen/advanced_generator_v2.py`
- **Function:** `generate_advanced_data_v2()` (line 363)
- **Schema Creation:** Lines 376-383: Calls `schema_designer.design_schema()` or `create_minimal_schema()`
- **Schema Conversion:** Lines 390-403: Converts Pydantic schema to dict format

### 3. Generator Initialization: `src/tools/datagen/advanced_generator_v2.py`
- **Class:** `AdvancedGeneratorV2` (line 36)
- **Initialization:** Lines 415-418: Creates generator with semantic components
- **Semantic Components:** Lines 58-61: Initializes `SemanticAnalyzer`, `CatalogFactory`, `SemanticRouter`

### 4. Generation: `src/tools/datagen/advanced_generator_v2.py`
- **Function:** `generate()` (line 69)
- **Semantic Analysis:** Line 97: `semantic_info = await self._analyze_schema_semantically(...)`
- **Data Generation Loop:** Lines 103-134: Iterates through entities, generates rows independently
- **Value Generation:** Lines 120-124: Calls `self.semantic_router.generate_value()` for each field

### 5. Semantic Analysis: `src/tools/datagen/semantic_analyzer_v2.py`
- **Function:** `analyze_schema()` (line 76)
- **Field Analysis:** Lines 100-113: Iterates fields, calls `analyze_field()` for each
- **5-Tier Pipeline:** Lines 48-74: Lexical → Pattern → Context → LLM → Fallback
- **Constraint Extraction:** Lines 141-162: Extracts constraints from field definitions

### 6. Value Generation: `src/tools/datagen/semantic_router.py`
- **Function:** `generate_value()` (line 25)
- **Constraint Check:** Lines 44-50: Checks enum/pattern constraints FIRST
- **Pattern Generation:** Line 50: Calls `_generate_pattern()` if pattern exists
- **Generator Selection:** Line 53: Gets generator function from registry
- **Value Production:** Line 56: Calls generator function

### 7. Realism Application: `src/tools/datagen/advanced_generator_v2.py`
- **Function:** `_apply_realism()` (line 212) - **NOT** `realism_engine.py`
- **Simplified Implementation:** Lines 217-239: Only null injection, no duplicates/outliers
- **ID Protection:** Lines 227-228: Skips `id` and fields ending with `_id`

### 8. Output Formatting: `src/tools/datagen/advanced_generator_v2.py`
- **Function:** `format_output()` (line 341)
- **JSON Formatting:** Line 351: `formatted[entity_name] = json.dumps(records, indent=2, default=str)`
- **CSV Formatting:** Lines 353-355: Uses pandas DataFrame

### 9. Return: `src/agents/datagen/agent.py`
- **Success Flag:** Line 88: `"success": True` (always True if no exception)
- **Data Return:** Line 90: `"data": result` (full result dict from generator)

---

## Verification Results

### 1. Are entity datasets returned as stringified JSON?

**CONFIRMED** ✅

**Evidence:**
- File: `src/tools/datagen/advanced_generator_v2.py`
- Function: `format_output()` (line 341)
- Line 351: `formatted[entity_name] = json.dumps(records, indent=2, default=str)`
- Return: `generate_advanced_data_v2()` line 438: `"data": formatted_data` where `formatted_data` is dict of entity_name → stringified JSON

**Code Path:**
```
advanced_generator_v2.py:429 → format_output() → line 351 → json.dumps()
```

---

### 2. Are FK values generated independently of parent IDs?

**CONFIRMED** ✅

**Evidence:**
- File: `src/tools/datagen/advanced_generator_v2.py`
- Function: `generate()` (line 69)
- Lines 103-134: Entity generation loop processes each entity independently
- Line 120-124: FK fields (e.g., `customer_id`) are generated via `semantic_router.generate_value()` with semantic type `UUID`
- **No code** that samples parent entity IDs or validates FK relationships
- **No code** that tracks parent entity IDs during generation

**Code Path:**
```
generate() → loop entities → loop fields → semantic_router.generate_value()
No parent ID tracking or FK validation
```

**Additional Evidence:**
- `semantic_router.py` line 100: `"uuid": lambda e, c: str(uuid.uuid4())` - generates random UUIDs
- No imports of `relationship_engine` in `advanced_generator_v2.py`

---

### 3. Is relationship_engine.py unused by advanced_generator_v2.py?

**CONFIRMED** ✅

**Evidence:**
- File: `src/tools/datagen/advanced_generator_v2.py`
- **No imports:** `grep` search shows zero matches for `relationship_engine` or `RelationshipEngine`
- **No usage:** Lines 1-442 contain no references to relationship engine
- **Independent generation:** Lines 103-134 generate entities independently in a loop

**Comparison:**
- `advanced_generator.py` (legacy) line 19: `from src.tools.datagen.relationship_engine import RelationshipEngine`
- `advanced_generator_v2.py`: No such import

**Conclusion:** `relationship_engine.py` exists but is **completely unused** by the V2 pipeline.

---

### 4. Can realism inject nulls into IDs / FKs?

**REFUTED** ❌

**Evidence:**
- File: `src/tools/datagen/advanced_generator_v2.py`
- Function: `_apply_realism()` (line 212)
- Lines 226-228:
```python
# Skip IDs
if field_name == "id" or field_name.endswith("_id"):
    continue
```

**Protection Logic:**
- Primary keys (`id`) are skipped
- Foreign keys (fields ending with `_id`) are skipped
- Only non-ID fields can receive null injection

**Note:** This is the simplified realism in `advanced_generator_v2.py`, NOT the full `realism_engine.py` which has different logic.

---

### 5. Are regex patterns enforced only at generation time?

**CONFIRMED** ✅

**Evidence:**
- File: `src/tools/datagen/semantic_router.py`
- Function: `generate_value()` (line 25)
- Lines 48-50:
```python
# Check for pattern override
if "pattern" in constraints and constraints["pattern"]:
    return self._generate_pattern(constraints["pattern"])
```

**Enforcement Point:**
- Pattern check happens **during** `generate_value()` call
- `generate_value()` is called **during row generation** (line 120 in `advanced_generator_v2.py`)
- No pre-validation or post-validation of patterns
- Pattern enforcement is **only at generation time**, not validated after

**Code Path:**
```
generate() → loop rows → semantic_router.generate_value() → _generate_pattern()
```

---

### 6. Does constraints_respected mean "constraint exists" not "constraint enforced"?

**CONFIRMED** ✅

**Evidence:**
- File: `src/tools/datagen/advanced_generator_v2.py`
- Function: `_build_metadata()` (line 241)
- Line 302:
```python
"constraints_respected": bool(field_info.constraints)  # Flag if constraints were detected
```

**Logic Analysis:**
- `bool(field_info.constraints)` checks if constraints dict exists and is non-empty
- **Does NOT** verify that constraints were actually enforced
- **Does NOT** validate that generated values match constraints
- Comment says "Flag if constraints were detected" - confirms it's about existence, not enforcement

**Example:**
- If `field_info.constraints = {"pattern": "^[A-Z]{3}$"}` → `constraints_respected = True`
- But generated value might be `"abc"` (lowercase) - constraint exists but not enforced
- Flag would still be `True` because constraint dict exists

---

### 7. Do metadata violations ever affect success=true?

**REFUTED** ❌

**Evidence:**
- File: `src/agents/datagen/agent.py`
- Function: `datagen_agent()` (line 23)
- Lines 88-94:
```python
return {
    "success": True,  # Always True if no exception
    "data": result,
    "format": datagen_args.format,
    "rows": datagen_args.rows,
    "mode": "v2"
}
```

**Success Logic:**
- Line 88: `"success": True` is hardcoded
- Only exceptions (lines 118-123) can prevent success=True
- Metadata warnings are added to `result["metadata"]["warnings"]` but never checked
- No validation of metadata quality or constraint violations

**Metadata Handling:**
- Warnings are collected in `_build_metadata()` (line 309-321)
- Warnings are returned in metadata dict (line 338)
- **No code** checks warnings or sets success=False based on them

**Exception Handling:**
- Lines 118-123: Only `ValueError` and general `Exception` raise errors
- Metadata violations are not exceptions - they're just warnings

---

## Summary Table

| Question | Answer | File + Function | Line(s) |
|----------|--------|-----------------|---------|
| 1. Entity datasets as stringified JSON? | ✅ CONFIRMED | `advanced_generator_v2.py::format_output()` | 351 |
| 2. FK values independent of parent IDs? | ✅ CONFIRMED | `advanced_generator_v2.py::generate()` | 103-134 |
| 3. relationship_engine.py unused? | ✅ CONFIRMED | `advanced_generator_v2.py` (no imports) | N/A |
| 4. Realism can inject nulls into IDs/FKs? | ❌ REFUTED | `advanced_generator_v2.py::_apply_realism()` | 227-228 |
| 5. Regex patterns enforced only at generation? | ✅ CONFIRMED | `semantic_router.py::generate_value()` | 48-50 |
| 6. constraints_respected = "exists" not "enforced"? | ✅ CONFIRMED | `advanced_generator_v2.py::_build_metadata()` | 302 |
| 7. Metadata violations affect success=true? | ❌ REFUTED | `agent.py::datagen_agent()` | 88 |

---

## Key Findings

1. **No FK Validation:** Foreign keys are generated as random UUIDs with no relationship to parent entity IDs.

2. **Simplified Realism:** V2 uses a simplified `_apply_realism()` method, NOT the full `realism_engine.py`. Only null injection is implemented.

3. **Pattern Enforcement:** Regex patterns are enforced at generation time via `rstr.xeger()`, but there's no post-generation validation.

4. **Metadata is Informational Only:** Warnings and constraint violations in metadata never affect the `success` flag.

5. **Relationship Engine Unused:** The `relationship_engine.py` module exists but is completely unused by the V2 pipeline.

---

**Audit Complete** - All findings based on code inspection only, no speculation.

