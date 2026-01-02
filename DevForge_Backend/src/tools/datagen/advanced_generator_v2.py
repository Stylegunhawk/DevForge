"""Advanced data generator v2 with Phase 1 semantic architecture.

Clean 3-layer architecture:
- Layer 1: Semantic Understanding (LLM confined here for classification only)
- Layer 2: Generator Selection (semantic_type → generator mapping)
- Layer 3: Value Production (Faker, catalogs - never LLM)
"""

import json
import logging
from typing import Any, Literal, Optional, List
from dataclasses import dataclass

import pandas as pd
from faker import Faker

from src.tools.datagen.semantic_analyzer_v2 import SemanticAnalyzer
from src.tools.datagen.catalog_factory import CatalogFactory
from src.tools.datagen.semantic_router import SemanticRouter
from src.tools.datagen.semantic_types import SemanticFieldInfo, FieldContext
from src.tools.datagen.schema_designer import schema_designer
from src.tools.datagen.schema_models import create_minimal_schema
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
    
    async def generate(
        self,
        schema: dict,
        row_count: int = 100,
        user_prompt: str = None,
        realism_level: str = "basic"
    ) -> dict:
        """
        Generate data with semantic awareness.
        
        Args:
            schema: Entity schema (entity_name -> {fields: {field_name: field_config}})
            row_count: Number of rows per entity
            user_prompt: Original user prompt for context
            realism_level: "basic", "medium", or "high"
            
        Returns:
            {
                "data": {entity_name: [rows]},
                "metadata": GenerationMetadata
            }
        """
        import time
        start_time = time.time()
        
        logger.info(f"Starting generation: entities={list(schema.keys())}, rows={row_count}")
        
        # Step 1: Semantic analysis
        semantic_info = await self._analyze_schema_semantically(schema, user_prompt)
        analysis_end_time = time.time()
        
        # Step 2: Generate data per entity
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
                            constraints=sem_info.constraints
                        )
                    else:
                        # Fallback to simple generation
                        row[field_name] = self._fallback_generate_field(
                            field_name, field_config
                        )
                
                entity_rows.append(row)
            
            generated_data[entity_name] = entity_rows
            logger.info(f"Generated {len(entity_rows)} rows for {entity_name}")
        
        # Step 3: Apply realism (if needed)
        if realism_level != "basic":
            generated_data = self._apply_realism(generated_data, realism_level, semantic_info)
        
        # Step 4: Build metadata
        metadata = self._build_metadata(semantic_info)
        
        # Add performance metrics
        total_time = time.time() - start_time
        analysis_time = analysis_end_time - start_time
        generation_time = total_time - analysis_time
        
        metadata["performance"] = {
            "analysis_ms": int(analysis_time * 1000),
            "generation_ms": int(generation_time * 1000),
            "total_ms": int(total_time * 1000)
        }
        
        return {
            "data": generated_data,
            "metadata": metadata,
            "semantic_generation_used": self.enable_semantic
        }
    
    async def _analyze_schema_semantically(
        self, 
        schema: dict, 
        user_prompt: str = None
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
            result = self.semantic_analyzer.analyze_schema(schema, user_prompt)
            
            # Log analysis results
            total_fields = sum(len(fields) for fields in result.values())
            logger.info(f"Semantic analysis complete: {total_fields} fields analyzed")
            
            return result
        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            logger.info("Falling back to non-semantic generation")
            return {}
    
    def _fallback_generate_field(self, field_name: str, field_config: dict) -> Any:
        """Fallback to simple generation if semantic analysis unavailable."""
        field_type = field_config.get("type", "string") if isinstance(field_config, dict) else "string"
        
        if field_type == "string":
            return self.faker.word()
        elif field_type in ("number", "integer", "float"):
            min_val = field_config.get("minimum", 0) if isinstance(field_config, dict) else 0
            max_val = field_config.get("maximum", 1000) if isinstance(field_config, dict) else 1000
            return round(self.faker.pyfloat(min_value=min_val, max_value=max_val), 2)
        elif field_type == "boolean":
            return self.faker.boolean()
        elif field_type == "date":
            return self.faker.date_this_decade().isoformat()
        elif field_type == "timestamp":
            return self.faker.date_time_this_year().isoformat()
        else:
            return self.faker.word()
    
    def _apply_realism(self, data: dict, level: str, semantic_info: dict = None) -> dict:
        """Apply data quality realism (nulls, duplicates, outliers)."""
        # Simplified realism for this v2 implementation
        import random
        
        null_rate = {"medium": 0.05, "high": 0.10}.get(level, 0)
        
        for entity_name, rows in data.items():
            # Get semantic map for this entity
            entity_semantic = semantic_info.get(entity_name, []) if semantic_info else []
            semantic_map = {info.field_name: info for info in entity_semantic}
            
            for row in rows:
                for field_name in list(row.keys()):
                    # Skip IDs
                    if field_name == "id" or field_name.endswith("_id"):
                        continue
                    
                    # Skip fields with enum constraints
                    if field_name in semantic_map:
                        info = semantic_map[field_name]
                        if info.constraints.get("enum"):
                            continue
                            
                    if random.random() < null_rate:
                        row[field_name] = None
        
        return data
    
    def _build_metadata(
        self, 
        semantic_info: dict[str, List[SemanticFieldInfo]]
    ) -> dict:
        """
        Build metadata for transparency and debugging.
        
        Args:
            semantic_info: Semantic analysis results
            
        Returns:
            Metadata dict with analysis summary and warnings
        """
        if not semantic_info:
            return {
                "semantic_analysis_summary": {
                    "enabled": False,
                    "reason": "Semantic analysis disabled or failed"
                },
                "field_analysis": {},
                "warnings": []
            }
        
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
        
        for entity_name, fields in semantic_info.items():
            field_analysis[entity_name] = {} # Initialize entity for field_analysis
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
                
                # Per-field details
                field_analysis[entity_name][field_info.field_name] = {
                    "semantic_type": field_info.semantic_type,
                    "source": field_info.source,
                    "confidence": round(field_info.confidence, 3),
                    "constraints_respected": bool(field_info.constraints)  # Flag if constraints were detected
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
            "warnings": warnings
        }
    
    def format_output(
        self,
        data: dict[str, list],
        output_format: Literal["json", "csv"] = "json"
    ) -> dict[str, str]:
        """Format data as JSON or CSV strings."""
        formatted = {}
        
        for entity_name, records in data.items():
            if output_format == "json":
                formatted[entity_name] = json.dumps(records, indent=2, default=str)
            else:  # CSV
                if records:
                    df = pd.DataFrame(records)
                    formatted[entity_name] = df.to_csv(index=False)
                else:
                    formatted[entity_name] = ""
        
        return formatted
        return formatted


async def generate_advanced_data_v2(
    prompt: Optional[str] = None,
    domain: Optional[Literal["ecommerce", "saas"]] = None,
    realism_level: Literal["basic", "medium", "high"] = "basic",
    default_rows: int = 100,
    output_format: Literal["json", "csv"] = "json",
    enable_semantic_generation: bool = True
) -> dict[str, Any]:
    """
    Generate advanced synthetic data using Phase 1 components.
    Drop-in replacement for legacy generate_advanced_data.
    """
    # Step 1: Design Schema
    if prompt or domain:
        schema = await schema_designer.design_schema(
            prompt=prompt or f"Generate {domain} data",
            domain=domain,
            default_rows=default_rows
        )
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
    
    # Step 3: Generate
    result = await generator.generate(
        schema=schema_dict,
        row_count=default_rows,
        user_prompt=prompt,
        realism_level=realism_level
    )
    
    # Step 4: Format output
    formatted_data = generator.format_output(result["data"], output_format)
    
    return {
        "entities": list(result["data"].keys()),
        "schema": {
            "domain": schema.domain,
            "entity_count": len(schema.entities),
            "relationship_count": len(schema.relationships)
        },
        "data": formatted_data,
        "semantic_generation_used": enable_semantic_generation,
        "metadata": result["metadata"]
    }
