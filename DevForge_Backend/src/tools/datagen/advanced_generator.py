"""Advanced data generator orchestrating all Phase 8 components.

Integrates:
- Schema Designer (LLM + domain templates)
- Semantic Analyzer (Phase 8.6 - field context understanding)
- Value Catalog Builder (Phase 8.6 - domain-specific values)
- Field Value Generator (Phase 8.6 - semantic-aware generation)
- Relationship Engine (1:N generation)
- Realism Engine (data quality)
"""

import json
import logging
from typing import Any, Literal, Optional

import pandas as pd

from src.tools.datagen.schema_designer import schema_designer
from src.tools.datagen.relationship_engine import RelationshipEngine
from src.tools.datagen.realism_engine import apply_realism_to_data

# Phase 8.6 imports
from src.tools.datagen.semantic_analyzer import SemanticAnalyzer
from src.tools.datagen.value_catalog_builder import CatalogBuilder
from src.tools.datagen.field_value_generator import FieldValueGenerator

logger = logging.getLogger(__name__)


async def generate_advanced_data(
    prompt: Optional[str] = None,
    domain: Optional[Literal["ecommerce", "saas"]] = None,
    realism_level: Literal["basic", "medium", "high"] = "basic",
    default_rows: int = 100,
    output_format: Literal["json", "csv"] = "json",
    enable_semantic_generation: bool = True  # Phase 8.6: Enable semantic-aware generation
) -> dict[str, Any]:
    """Generate advanced synthetic data using all Phase 8 components.
    
    Args:
        prompt: Natural language description for LLM schema design
        domain: Pre-defined domain template
        realism_level: Data quality realism level
        default_rows: Default row count for entities
        output_format: Output format
        enable_semantic_generation: Enable Phase 8.6 semantic-aware generation (default: True)
        
    Returns:
        Dictionary with generated data for all entities
        
    Phase 8.6 Enhancement:
        When enable_semantic_generation=True, understands field semantics and generates
        domain-specific values (e.g., flower.name → "Rose", not "John Doe")
    """
    logger.info(
        f"Generating advanced data: prompt={bool(prompt)}, domain={domain}, "
        f"realism={realism_level}, rows={default_rows}, semantic={enable_semantic_generation}"
    )
    
    # Step 1: Get validated schema
    if prompt or domain:
        schema = await schema_designer.design_schema(
            prompt=prompt or f"Generate {domain} data",
            domain=domain,
            default_rows=default_rows
        )
    else:
        # Fallback to simple schema
        from src.tools.datagen.schema_models import create_minimal_schema
        schema = create_minimal_schema(default_rows)
    
    logger.info(f"Schema generated: {len(schema.entities)} entities")
    
    # Step 2: Semantic analysis (Phase 8.6)
    field_generator = None
    if enable_semantic_generation:
        try:
            logger.info("Starting semantic analysis...")
            
            # Analyze field semantics
            semantic_analyzer = SemanticAnalyzer()
            semantic_plan = await semantic_analyzer.analyze_schema(
                schema=schema,
                prompt=prompt or f"Generate {domain} data" if domain else "Generate data"
            )
            
            logger.info(f"Semantic analysis complete: {len(semantic_plan.fields_needing_catalogs())} catalogs needed")
            
            # Build value catalogs
            catalog_builder = CatalogBuilder()
            await catalog_builder.build_catalogs(
                semantic_plan=semantic_plan,
                prompt=prompt or f"Generate {domain} data" if domain else "Generate data",
                catalog_max_values=50  # Reasonable default
            )
            
            logger.info(f"Value catalogs built: {len(semantic_plan.value_catalogs)} catalogs")
            
            # Create semantic-aware field generator
            field_generator = FieldValueGenerator(semantic_plan)
            logger.info("Semantic field generator created")
            
        except Exception as e:
            logger.warning(f"Semantic generation failed: {e}. Falling back to standard generation.")
            field_generator = None  # Fallback to Faker
    
    # Step 3: Generate multi-entity data respecting relationships
    engine = RelationshipEngine(schema, field_generator=field_generator)
    raw_data = engine.generate_all_entities()
    
    logger.info(f"Data generated for {len(raw_data)} entities")
    
    # Step 4: Apply realism (nulls, duplicates, outliers)
    realistic_data = apply_realism_to_data(raw_data, schema, realism_level)
    
    logger.info(f"Realism applied: level={realism_level}")
    
    # Step 5: Format output
    formatted_output = _format_multi_entity_data(realistic_data, output_format)
    
    return {
        "entities": list(realistic_data.keys()),
        "schema": {
            "domain": schema.domain,
            "entity_count": len(schema.entities),
            "relationship_count": len(schema.relationships)
        },
        "data": formatted_output,
        "semantic_generation_used": field_generator is not None  # Phase 8.6: Report if semantic gen was used
    }


def _format_multi_entity_data(
    data: dict[str, list[dict[str, Any]]],
    output_format: Literal["json", "csv"]
) -> dict[str, str]:
    """Format multi-entity data as JSON or CSV.
    
    Args:
        data: Dictionary of entity_name -> list of records
        output_format: Desired format
        
    Returns:
        Dictionary of entity_name -> formatted string
    """
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
