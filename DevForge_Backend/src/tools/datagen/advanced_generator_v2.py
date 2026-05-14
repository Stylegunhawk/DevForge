"""Advanced data generator v2 with Phase 1 semantic architecture.

Clean 3-layer architecture:
- Layer 1: Semantic Understanding (LLM confined here for classification only)
- Layer 2: Generator Selection (semantic_type → generator mapping)
- Layer 3: Value Production (Faker, catalogs - never LLM)
- Layer 4: Constraint Validation (post-generation verification)
"""

import json
import logging
import re
from typing import Any, Literal, Optional, List, Dict
from dataclasses import dataclass

import pandas as pd
from faker import Faker

from src.tools.datagen.semantic_analyzer_v2 import SemanticAnalyzer
from src.tools.datagen.catalog_factory import CatalogFactory
from src.tools.datagen.semantic_router import SemanticRouter
from src.tools.datagen.semantic_types import SemanticFieldInfo, FieldContext
from src.tools.datagen.schema_designer import schema_designer
from src.tools.datagen.schema_models import create_minimal_schema, SchemaDesign
from src.tools.datagen.relationship_engine import RelationshipEngine
from src.core.model_router import model_router

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetadata:
    """Metadata about the generation process for observability."""
    semantic_analysis_summary: dict
    field_analysis: dict[str, dict]
    warnings: List[dict]


class AdvancedGeneratorV2:
    """
    Phase 1 refactored generator.
    
    Key guarantees:
    - LLM is ONLY used for classification (semantic type inference)
    - All values come from Faker or catalogs
    - No "Agent every development say" in output!
    """
    
    def __init__(self, llm_client=None, enable_semantic: bool = True):
        """
        Initialize generator with semantic components.
        
        Args:
            llm_client: LangChain LLM instance for classification (optional)
            enable_semantic: Enable semantic analysis (default: True)
        """
        self.faker = Faker()
        self.enable_semantic = enable_semantic
        self._progress_callback = None
        
        # Initialize semantic components
        if enable_semantic:
            self.catalog_factory = CatalogFactory(llm_client) if llm_client else CatalogFactory()
            self.semantic_analyzer = SemanticAnalyzer(llm_client)
            self.semantic_router = SemanticRouter(self.catalog_factory)
        else:
            self.catalog_factory = None
            self.semantic_analyzer = None
            self.semantic_router = SemanticRouter()  # Basic router, no catalogs
        
        logger.info(f"AdvancedGeneratorV2 initialized: semantic={enable_semantic}, llm={llm_client is not None}")

    def _report(self, stage: str, percent: int, message: str):
        """Safe wrapper for progress reporting."""
        if self._progress_callback:
            try:
                self._progress_callback(stage, percent, message)
            except Exception as e:
                # Callback should be safe, but we're defensive
                logger.warning(f"Progress callback failed: {e}")

    
    async def generate(
        self,
        schema: dict,
        schema_design: Optional[SchemaDesign] = None,
        row_count: int = 100,
        user_prompt: str = None,
        realism_level: str = "basic",
        *,
        progress_callback: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None
    ) -> dict:
        """
        Generate data with semantic awareness and relationship integrity.
        
        Args:
            schema: Entity schema (entity_name -> {fields: {field_name: field_config}})
            schema_design: Optional SchemaDesign object for relationship-aware generation
            row_count: Number of rows per entity
            user_prompt: Original user prompt for context
            realism_level: "basic", "medium", or "high"
            
        Returns:
            {
                "data": {entity_name: [rows]},
                "metadata": GenerationMetadata,
                "constraint_violations": list,
                "fk_integrity": dict
            }
        """
        import time
        start_time = time.time()
        self._progress_callback = progress_callback
        
        logger.info(f"Starting generation: entities={list(schema.keys())}, rows={row_count}")
        self._report("schema_design", 20, "Initializing generator components")
        
        try:
            # Step 1: Semantic analysis
            # NOTE: user_id is intentionally NOT forwarded here. `generate()`
            # does not accept user_id in its signature; threading it from the
            # outer wrapper is the responsibility of the wrapper. Forwarding
            # an undefined name here caused a NameError that silently failed
            # every V2 call.
            semantic_info = await self._analyze_schema_semantically(
                schema,
                user_prompt,
                tenant_id=tenant_id,
                integration_name=integration_name,
            )
            analysis_end_time = time.time()
            self._report("semantic_analysis", 40, "Schema semantic analysis complete")
            
            # Step 2: Generate data with relationship awareness if schema_design provided
            self._report("catalog_generation", 60, "Generating domain-specific catalogs")
            if schema_design and schema_design.relationships:
                generated_data = await self._generate_with_relationships(
                    schema_design, semantic_info, row_count
                )
            else:
                generated_data = await self._generate_independent_entities(
                    schema, semantic_info, row_count
                )
            
            self._report("row_generation", 80, f"Bulk row generation complete ({row_count} rows)")
            
            # Step 3: Validate constraints
            constraint_violations = self._validate_constraints(
                generated_data, schema, semantic_info
            )
            
            # Step 4: Validate FK integrity (if relationships exist)
            fk_integrity = {}
            if schema_design and schema_design.relationships:
                fk_integrity = self._validate_fk_integrity(generated_data, schema_design)
            
            # Step 5: Apply realism (if needed) - must respect schema constraints
            if realism_level != "basic":
                generated_data = self._apply_realism(
                    generated_data, realism_level, semantic_info, schema
                )
        except Exception as e:
            logger.error(f"Pipeline failure during data generation: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Internal pipeline error: {str(e)}",
                "data": {},
                "metadata": {"error": True}
            }
        
        # Step 5: Apply realism (if needed) - must respect schema constraints
        if realism_level != "basic":
            generated_data = self._apply_realism(
                generated_data, realism_level, semantic_info, schema
            )
        
        # Step 6: Build metadata with actual enforcement status
        metadata = self._build_metadata(
            semantic_info, generated_data, schema, constraint_violations
        )
        
        # Add performance metrics
        total_time = time.time() - start_time
        analysis_time = analysis_end_time - start_time
        generation_time = total_time - analysis_time
        
        self._report("complete", 100, "Generation complete")
        self._progress_callback = None  # Reset for reuse
        
        metadata["performance"] = {
            "analysis_ms": int(analysis_time * 1000),
            "generation_ms": int(generation_time * 1000),
            "total_ms": int(total_time * 1000)
        }
        
        if constraint_violations or not fk_integrity.get("valid", True):
             # Invariant 3: Invalid values must never be returned.
             # Invariant 8: Deterministic Success Semantics.
             
             # We must NOT return invalid data.
             # If violations exist, we return EMPTY data for the affected entities or fail globally.
             # The instruction says "Standardized failure object" or exception.
             # However, the return type is dict.
             # To strictly satisfy "Invalid values must never be returned", we clear the data.
             logger.error("Generation failed invariant checks. Preventing invalid data return.")
             generated_data = {} 
        
        return {
            "data": generated_data,
            "metadata": metadata,
            "semantic_generation_used": self.enable_semantic,
            "constraint_violations": constraint_violations,
            "fk_integrity": fk_integrity
        }
    
    async def _analyze_schema_semantically(
        self, 
        schema: dict, 
        user_prompt: str = None,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None  # NEW: Phase 4 analytics support
    ) -> dict[str, List[SemanticFieldInfo]]:
        """
        Analyze schema using semantic analyzer.
        
        Args:
            schema: Entity schema from schema designer
            user_prompt: Original user prompt for context
            
        Returns:
            Dict mapping entity names to semantic field info
        """
        if not self.enable_semantic or not self.semantic_analyzer:
            logger.info("Semantic analysis disabled")
            return {}
        
        try:
            logger.info("Running semantic analysis...")
            result = await self.semantic_analyzer.analyze_schema(
                schema,
                user_prompt,
                tenant_id=tenant_id,
                integration_name=integration_name,
            )
            
            # Log analysis results
            total_fields = sum(len(fields) for fields in result.values())
            logger.info(f"Semantic analysis complete: {total_fields} fields analyzed")
            
            return result
        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            logger.info("Falling back to non-semantic generation")
            return {}
    
    async def _generate_with_relationships(
        self,
        schema_design: SchemaDesign,
        semantic_info: dict,
        row_count: int
    ) -> dict[str, list]:
        """Generate data using RelationshipEngine for FK integrity."""
        # Build field generator adapter that uses semantic router
        class SemanticFieldGeneratorAdapter:
            """Adapter to bridge RelationshipEngine with semantic router."""
            def __init__(self, router, semantic_info, faker):
                self.router = router
                self.semantic_info = semantic_info
                self.faker = faker
            
            def get_generator(self, entity_name: str, field_name: str):
                """Return a generator function for a field."""
                entity_semantic = self.semantic_info.get(entity_name, [])
                semantic_map = {info.field_name: info for info in entity_semantic}

                if field_name in semantic_map:
                    sem_info = semantic_map[field_name]
                    return lambda: self.router.generate_value(
                        semantic_type=sem_info.semantic_type,
                        entity_name=entity_name,
                        constraints=sem_info.constraints,
                        field_name=field_name,
                    )
                else:
                    return lambda: self.faker.word()
        
        # Create adapter
        field_generator = SemanticFieldGeneratorAdapter(
            self.semantic_router, semantic_info, self.faker
        )
        
        # Use RelationshipEngine for generation (it handles FK sampling)
        engine = RelationshipEngine(schema_design, field_generator)
        generated_data = engine.generate_all_entities()
        
        return generated_data
    
    async def _generate_independent_entities(
        self,
        schema: dict,
        semantic_info: dict,
        row_count: int
    ) -> dict[str, list]:
        """Generate entities independently (no relationships)."""
        generated_data = {}
        
        for entity_name, entity_schema in schema.items():
            entity_rows = []
            fields = entity_schema.get("fields", entity_schema.get("properties", {}))
            
            # Get semantic info for this entity
            entity_semantic = semantic_info.get(entity_name, [])
            semantic_map = {
                info.field_name: info for info in entity_semantic
            } if entity_semantic else {}
            
            for i in range(row_count):
                row = {}
                
                for field_name, field_config in fields.items():
                    # Use semantic routing if available
                    if field_name in semantic_map:
                        sem_info = semantic_map[field_name]
                        row[field_name] = self.semantic_router.generate_value(
                            semantic_type=sem_info.semantic_type,
                            entity_name=entity_name,
                            constraints=sem_info.constraints,
                            field_name=field_name,
                        )
                    else:
                        # Fallback to simple generation
                        row[field_name] = self._fallback_generate_field(
                            field_name, field_config
                        )
                
                entity_rows.append(row)
            
            generated_data[entity_name] = entity_rows
            logger.info(f"Generated {len(entity_rows)} rows for {entity_name}")
        
        return generated_data
    
    def _validate_constraints(
        self,
        generated_data: dict,
        schema: dict,
        semantic_info: dict
    ) -> list[dict]:
        """Validate that generated values respect constraints.
        
        Invariant 3: No Post-Hoc Fixing (Detection only).
        Invariant 8: Deterministic Success (Must detect all violations).
        """
        violations = []
        
        for entity_name, rows in generated_data.items():
            entity_schema = schema.get(entity_name, {})
            fields = entity_schema.get("fields", entity_schema.get("properties", {}))
            entity_semantic = semantic_info.get(entity_name, [])
            semantic_map = {info.field_name: info for info in entity_semantic}
            
            for row_idx, row in enumerate(rows):
                for field_name in fields.keys():
                    field_config = fields.get(field_name, {})
                    constraints = field_config.get("constraints", {})
                    value = row.get(field_name)
                    
                    # Merge semantic constraints (Invariant 2: Canonical Shape - handled in semantic_router, but needed here for checking)
                    if field_name in semantic_map:
                        sem_info = semantic_map[field_name]
                        # Merge constraints
                        if sem_info.constraints:
                            constraints = {**constraints, **sem_info.constraints}

                    # Validate Nullability
                    # Invariant: If not nullable, must not be None
                    is_nullable = field_config.get("nullable", False)
                    if value is None:
                        if not is_nullable:
                            violations.append({
                                "entity": entity_name,
                                "field": field_name,
                                "row": row_idx,
                                "value": None,
                                "constraint": "nullable",
                                "expected": False
                            })
                        continue  # Stop checking other constraints if value is None
                    
                    # Validate enum
                    if "enum" in constraints and constraints["enum"]:
                        if value not in constraints["enum"]:
                            violations.append({
                                "entity": entity_name,
                                "field": field_name,
                                "row": row_idx,
                                "value": value,
                                "constraint": "enum",
                                "expected": constraints["enum"]
                            })
                    
                    # Validate pattern
                    if "pattern" in constraints and constraints["pattern"]:
                        try:
                            if not re.match(constraints["pattern"], str(value)):
                                violations.append({
                                    "entity": entity_name,
                                    "field": field_name,
                                    "row": row_idx,
                                    "value": value,
                                    "constraint": "pattern",
                                    "expected": constraints["pattern"]
                                })
                        except Exception as e:
                            logger.warning(f"Pattern validation failed for {entity_name}.{field_name}: {e}")
                    
                    # Validate min/max (Numeric)
                    # Note: bool is an int subclass, so we must explicitly exclude it for numeric min/max
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        if "min" in constraints and constraints["min"] is not None and value < constraints["min"]:
                            violations.append({
                                "entity": entity_name, 
                                "field": field_name, 
                                "row": row_idx, 
                                "value": value, 
                                "constraint": "min", 
                                "expected": constraints["min"]
                            })
                        if "max" in constraints and constraints["max"] is not None and value > constraints["max"]:
                            violations.append({
                                "entity": entity_name, 
                                "field": field_name, 
                                "row": row_idx, 
                                "value": value, 
                                "constraint": "max", 
                                "expected": constraints["max"]
                            })
                            
                    # Validate min/max (Dates/Timestamps)
                    # We accept strings, check if they are ISO dates
                    if isinstance(value, str):
                        # Simple check for min/max on string length OR date value
                        # If field type is date/timestamp, try parse
                        field_type = field_config.get("type", "string")
                        if field_type in ("date", "timestamp"):
                            try:
                                # Very basic comparison for ISO strings works mostly
                                if "min" in constraints and constraints["min"] is not None and value < str(constraints["min"]):
                                    violations.append({
                                        "entity": entity_name, "field": field_name, "row": row_idx,
                                        "value": value, "constraint": "min_date", "expected": constraints["min"]
                                    })
                                if "max" in constraints and constraints["max"] is not None and value > str(constraints["max"]):
                                    violations.append({
                                        "entity": entity_name, "field": field_name, "row": row_idx,
                                        "value": value, "constraint": "max_date", "expected": constraints["max"]
                                    })
                            except:
                                pass # Ignore if comparison fails
                        
        return violations
    
    def _validate_fk_integrity(
        self,
        generated_data: dict,
        schema_design: SchemaDesign
    ) -> dict:
        """Validate foreign key integrity."""
        # Create temporary RelationshipEngine to use its validation
        engine = RelationshipEngine(schema_design)
        engine.generated_entities = generated_data
        return engine.validate_relationships()
    
    def _fallback_generate_field(self, field_name: str, field_config: dict) -> Any:
        """Fallback to simple generation if semantic analysis unavailable.
        
        Must respect constraints (Invariant 1).
        """
        field_type = field_config.get("type", "string") if isinstance(field_config, dict) else "string"
        constraints = field_config.get("constraints", {})
        
        # Invariant 1: Enum overrides everything
        if "enum" in constraints and constraints["enum"]:
            import random
            return random.choice(constraints["enum"])
            
        if field_type == "string":
            if "pattern" in constraints:
                try:
                    import rstr
                    return rstr.xeger(constraints["pattern"])
                except:
                    pass
            return self.faker.word()
            
        elif field_type in ("number", "integer", "float"):
            raw_min = constraints.get("min") if constraints.get("min") is not None else field_config.get("minimum")
            raw_max = constraints.get("max") if constraints.get("max") is not None else field_config.get("maximum")
            
            min_val = float(raw_min) if raw_min is not None else 0.0
            max_val = float(raw_max) if raw_max is not None else 1000.0
            
            if field_type == "integer":
                return self.faker.random_int(min=int(min_val), max=int(max_val))
            return round(self.faker.pyfloat(min_value=min_val, max_value=max_val), 2)
            
        elif field_type == "boolean":
            return self.faker.boolean()
            
        elif field_type == "date":
             # Respect min/max date
             start = constraints.get("min") if constraints.get("min") is not None else "-10y"
             end = constraints.get("max") if constraints.get("max") is not None else "today"
             try:
                 return self.faker.date_between(start_date=start, end_date=end).isoformat()
             except:
                 return self.faker.date_this_decade().isoformat()
                 
        elif field_type == "timestamp":
             start = constraints.get("min") if constraints.get("min") is not None else "-1y"
             end = constraints.get("max") if constraints.get("max") is not None else "now"
             try:
                 return self.faker.date_time_between(start_date=start, end_date=end).isoformat()
             except:
                 return self.faker.date_time_this_year().isoformat()
        else:
            return self.faker.word()
    
    def _apply_realism(
        self,
        data: dict,
        level: str,
        semantic_info: dict = None,
        schema: dict = None
    ) -> dict:
        """Apply data quality realism (nulls, duplicates, outliers) respecting schema constraints."""
        import random
        
        null_rate = {"medium": 0.05, "high": 0.10}.get(level, 0)
        
        # Critical fields that should never be null
        critical_semantic_types = {
            "email_address", "phone_number", "uuid", "numeric_id",
            "timestamp", "date", "bank_account_number", "transaction_id"
        }
        
        for entity_name, rows in data.items():
            # Get schema info for this entity
            entity_schema = schema.get(entity_name, {}) if schema else {}
            fields = entity_schema.get("fields", entity_schema.get("properties", {}))
            
            # Get semantic map for this entity
            entity_semantic = semantic_info.get(entity_name, []) if semantic_info else []
            semantic_map = {info.field_name: info for info in entity_semantic}
            
            for row in rows:
                for field_name in list(row.keys()):
                    # Skip IDs and foreign keys
                    if field_name == "id" or field_name.endswith("_id"):
                        continue
                    
                    # Check schema nullable flag
                    field_config = fields.get(field_name, {})
                    if not field_config.get("nullable", False):
                        continue  # Skip non-nullable fields
                    
                    # Check semantic constraints
                    if field_name in semantic_map:
                        info = semantic_map[field_name]
                        # Skip enum fields
                        if info.constraints.get("enum"):
                            continue
                        # Skip critical semantic types
                        if info.semantic_type in critical_semantic_types:
                            continue
                    
                    # Apply null injection only to nullable, non-critical fields
                    if random.random() < null_rate:
                        row[field_name] = None
        
        return data
    
    def _build_metadata(
        self,
        semantic_info: dict[str, List[SemanticFieldInfo]],
        generated_data: dict = None,
        schema: dict = None,
        constraint_violations: list = None
    ) -> dict:
        """
        Build metadata for transparency and debugging with actual enforcement status.
        
        Args:
            semantic_info: Semantic analysis results
            generated_data: Generated data for validation
            schema: Schema for constraint checking
            constraint_violations: List of constraint violations found
            
        Returns:
            Metadata dict with analysis summary, warnings, and enforcement status
        """
        if not semantic_info:
            return {
                "semantic_analysis_summary": {
                    "enabled": False,
                    "reason": "Semantic analysis disabled or failed"
                },
                "field_analysis": {},
                "warnings": [],
                "constraint_enforcement": {
                    "enforced": False,
                    "violations_count": 0
                }
            }
        
        constraint_violations = constraint_violations or []
        
        # Collect statistics
        total_fields = 0
        source_counts = {
            "lexical": 0,
            "pattern": 0,
            "context": 0,
            "llm": 0,
            "fallback": 0
        }
        confidences = []
        low_confidence_fields = []
        field_analysis = {}
        
        # Track constraint enforcement per field
        field_violations = {}
        for violation in constraint_violations:
            key = f"{violation['entity']}.{violation['field']}"
            if key not in field_violations:
                field_violations[key] = []
            field_violations[key].append(violation)
        
        for entity_name, fields in semantic_info.items():
            field_analysis[entity_name] = {}
            for field_info in fields:
                total_fields += 1
                
                # Count by source
                source_counts[field_info.source] = source_counts.get(field_info.source, 0) + 1
                
                # Track confidence
                confidences.append(field_info.confidence)
                
                # Flag low confidence
                if field_info.confidence < 0.7:
                    low_confidence_fields.append({
                        "field": f"{entity_name}.{field_info.field_name}",
                        "confidence": field_info.confidence,
                        "semantic_type": field_info.semantic_type,
                        "source": field_info.source
                    })
                
                # Check if constraints were actually enforced
                key = f"{entity_name}.{field_info.field_name}"
                has_violations = key in field_violations
                
                # Invariant 7: Metadata Truthfulness
                # constraints_respected must strictly equal (violations == 0)
                # Regardless of whether constraints were detected or not.
                constraints_respected = not has_violations
                
                # Per-field details
                field_analysis[entity_name][field_info.field_name] = {
                    "semantic_type": field_info.semantic_type,
                    "source": field_info.source,
                    "confidence": round(field_info.confidence, 3),
                    "constraints_respected": constraints_respected,  # Actual enforcement status
                    "constraints_detected": bool(field_info.constraints),
                    "violations": len(field_violations.get(key, []))
                }
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Build warnings
        warnings = []
        for field in low_confidence_fields:
            warnings.append({
                "type": "low_confidence_classification",
                "field": field["field"],
                "confidence": field["confidence"],
                "semantic_type": field["semantic_type"],
                "message": (
                    f"Field '{field['field']}' has low confidence classification "
                    f"({field['confidence']:.2f}). Consider adding to lexical_dict.py "
                    f"or providing explicit type hints."
                )
            })
        
        # Add constraint violation warnings
        if constraint_violations:
            warnings.append({
                "type": "constraint_violations",
                "count": len(constraint_violations),
                "message": f"Found {len(constraint_violations)} constraint violations in generated data"
            })
        
        return {
            "semantic_analysis_summary": {
                "enabled": True,
                "total_fields": total_fields,
                "classified_by_lexical": source_counts.get("lexical", 0),
                "classified_by_pattern": source_counts.get("pattern", 0),
                "classified_by_context": source_counts.get("context", 0),
                "classified_by_llm": source_counts.get("llm", 0),
                "fallback_used": source_counts.get("fallback", 0),
                "avg_confidence": round(avg_confidence, 3),
                "llm_call_rate": round(
                    source_counts.get("llm", 0) / total_fields * 100, 1
                ) if total_fields > 0 else 0.0
            },
            "field_analysis": field_analysis,
            "warnings": warnings,
            "constraint_enforcement": {
                "enforced": len(constraint_violations) == 0,
                "violations_count": len(constraint_violations)
            }
        }
    
    def format_output(
        self,
        data: dict[str, list],
        output_format: Literal["json", "csv"] = "json"
    ) -> dict[str, Any]:
        """
        Format data as JSON (native arrays) or CSV (strings).
        
        Args:
            data: Dictionary of entity_name -> list of records
            output_format: "json" or "csv"
            
        Returns:
            For JSON: dict[str, list] (native arrays)
            For CSV: dict[str, str] (stringified CSV)
        """
        formatted = {}
        
        for entity_name, records in data.items():
            if output_format == "json":
                # Return native arrays for JSON, not stringified
                formatted[entity_name] = records
            else:  # CSV
                if records:
                    df = pd.DataFrame(records)
                    formatted[entity_name] = df.to_csv(index=False)
                else:
                    formatted[entity_name] = ""
        
        return formatted


async def generate_advanced_data_v2(
    prompt: Optional[str] = None,
    domain: Optional[Literal["ecommerce", "saas", "iot_devices"]] = None,
    realism_level: Literal["basic", "medium", "high"] = "basic",
    default_rows: int = 100,
    output_format: Literal["json", "csv"] = "json",
    enable_semantic_generation: bool = True,
    progress_callback: Optional[Any] = None,
    tenant_id: str = "unknown",
    integration_name: str = "unknown",
    user_id: Optional[str] = None  # NEW: Phase 4 analytics support
) -> dict[str, Any]:
    """
    Generate advanced synthetic data using Phase 1 components.
    Drop-in replacement for legacy generate_advanced_data.
    """
    try:
        # Input validation
        if default_rows is not None and (not isinstance(default_rows, int) or default_rows < 1 or default_rows > 100000):
            return {
                "success": False,
                "error": f"Invalid rows parameter: {default_rows}. Must be integer between 1 and 100000",
                "data": {},
                "schema": {},
                "rows_generated": 0
            }
        
        if output_format not in ["json", "csv"]:
            return {
                "success": False,
                "error": f"Unsupported output format: {output_format}. Supported: json, csv",
                "data": {},
                "schema": {},
                "rows_generated": 0
            }
        
        # Step 1: Design Schema
        if prompt or domain:
            try:
                schema = await schema_designer.design_schema(
                    prompt=prompt or f"Generate {domain} data",
                    domain=domain,
                    default_rows=default_rows,
                    tenant_id=tenant_id,
                    integration_name=integration_name,
                    user_id=user_id  # NEW: Pass user_id to schema_designer
                )
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Schema design failed: {str(e)}",
                    "data": {},
                    "schema": {},
                    "rows_generated": 0
                }
        else:
            schema = create_minimal_schema(default_rows)
        
        # Convert Pydantic schema to dict for V2 generator
        # AdvancedGeneratorV2 expects dict: {entity: {fields: ...}}
        # SchemaDesign has .entities which is dict of EntitySchema
        # EntitySchema has .fields which is list of FieldSchema
        
        schema_dict = {}
        for entity_name, entity in schema.entities.items():
            fields_dict = {}
            for field in entity.fields:
                fields_dict[field.name] = {
                    "type": field.type,
                    "nullable": field.nullable
                }
                if field.constraints:
                    fields_dict[field.name]["constraints"] = field.constraints
            
            schema_dict[entity_name] = {
                "fields": fields_dict
            }
            
        # Step 2: Initialize Generator V2
        llm_client = None
        if enable_semantic_generation:
            try:
                # Use 'routing' or 'complex_reasoning' task for classification
                model_name = model_router.select_model_by_task("routing") 
                llm_client = model_router.get_chat_model(model_name)
            except Exception as e:
                logger.warning(f"Could not get LLM client for semantic analysis: {e}")
        
        generator = AdvancedGeneratorV2(
            llm_client=llm_client,
            enable_semantic=enable_semantic_generation
        )
        
        # Step 3: Generate with relationship awareness
        result = await generator.generate(
            schema=schema_dict,
            schema_design=schema,  # Pass SchemaDesign for FK integrity
            row_count=default_rows,
            user_prompt=prompt,
            realism_level=realism_level,
            progress_callback=progress_callback,
            tenant_id=tenant_id,
            integration_name=integration_name
        )
        
        # Step 4: Format output (JSON returns native arrays, CSV returns strings)
        formatted_data = generator.format_output(result["data"], output_format)
        
        # Step 5: Determine success based on metadata and violations.
        # Fail-closed on any upstream pipeline error: the inner generate()
        # returns {success: False, metadata: {error: True}} on exceptions, and
        # earlier the success calc here ignored both signals and reported
        # success=True with empty data. Check the upstream failure flags
        # first, then fall through to the constraint/FK checks.
        upstream_failed = (
            result.get("success") is False
            or result.get("metadata", {}).get("error") is True
        )
        if upstream_failed:
            success = False
        else:
            success = (
                len(result.get("constraint_violations", [])) == 0
                and result.get("fk_integrity", {}).get("valid", True)
                and result["metadata"].get("constraint_enforcement", {}).get("enforced", True)
            )
        
        return {
            "entities": list(result["data"].keys()),
            "schema": {
                "domain": schema.domain,
                "entity_count": len(schema.entities),
                "relationship_count": len(schema.relationships)
            },
            "data": formatted_data,
            "semantic_generation_used": enable_semantic_generation,
            "metadata": result["metadata"],
            "constraint_violations": result.get("constraint_violations", []),
            "fk_integrity": result.get("fk_integrity", {}),
            "_internal_success": success  # Internal flag for agent to check
        }
        
    except Exception as e:
        logger.error(f"Advanced data generation failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Data generation failed: {str(e)}",
            "data": {},
            "schema": {},
            "entities": [],
            "semantic_generation_used": False,
            "metadata": {},
            "constraint_violations": [],
            "fk_integrity": {"valid": False, "error": str(e)},
            "_internal_success": False
        }

