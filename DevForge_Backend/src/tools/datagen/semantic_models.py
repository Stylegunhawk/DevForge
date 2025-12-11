"""Semantic models for intelligent field value generation.

Defines Pydantic models for:
- FieldSemanticInfo: Metadata about what a field semantically represents
- ValueCatalog: LLM-generated lists of realistic values
- SemanticPlan: Complete semantic analysis for a schema

Phase 8.6: Fixes "Daniel Doyle flower" bug by understanding field context.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any


class FieldSemanticInfo(BaseModel):
    """Semantic metadata for a single field.
    
    Describes what a field semantically represents and how to generate values.
    
    Example:
        For "name" field in "flowers" entity:
        - semantic_type: "flower_name" (not "person_name")
        - generator_strategy: "value_catalog" (use LLM-generated flower names)
    """
    
    entity_name: str = Field(..., description="Entity this field belongs to")
    field_name: str = Field(..., description="Name of the field")
    db_type: str = Field(..., description="Database type: string, int, float, date, etc.")
    
    semantic_type: str = Field(
        ...,
        description="Semantic meaning: 'flower_name', 'university_name', 'botanical_family', etc."
    )
    
    generator_strategy: Literal[
        "faker",              # Use existing Faker provider (e.g., email, phone)
        "numeric_distribution",  # Use statistical distributions (normal, lognormal, pareto)
        "datetime_range",     # Use temporal patterns (business_hours, seasonal)
        "uuid",               # Generate UUIDs
        "mongo_object_id",    # Generate MongoDB ObjectIds
        "value_catalog",      # Sample from LLM-generated catalog
        "generic_text"        # Fallback to random text
    ] = Field(..., description="Strategy for generating values")
    
    constraints: Optional[dict[str, Any]] = Field(
        None,
        description="Generation constraints like min/max, examples, patterns"
    )
    
    notes: Optional[str] = Field(
        None,
        description="Human-readable notes about this field"
    )


class ValueCatalog(BaseModel):
    """LLM-generated catalog of realistic values for a semantic type.
    
    Generated once at planning time, sampled from during generation.
    
    Example:
        For semantic_type="flower_name":
        values=["Rose", "Tulip", "Orchid", "Lily", "Sunflower", ...]
    """
    
    key: str = Field(
        ...,
        description="Unique key: 'entity.field' or 'entity.field.prompt_hash'"
    )
    
    semantic_type: str = Field(
        ...,
        description="Semantic type this catalog is for"
    )
    
    values: list[str] = Field(
        ...,
        description="List of realistic values",
        min_length=1
    )
    
    source: Literal["llm", "builtin"] = Field(
        "llm",
        description="How this catalog was generated"
    )
    
    max_sample_size: Optional[int] = Field(
        None,
        description="Maximum times to sample before cycling"
    )


class SemanticPlan(BaseModel):
    """Complete semantic analysis for a schema.
    
    Contains:
    - Field semantic info for each entity
    - Value catalogs for fields needing them
    
    Generated once per schema, used throughout generation.
    """
    
    entities: dict[str, list[FieldSemanticInfo]] = Field(
        ...,
        description="Map of entity_name -> list of field semantic info"
    )
    
    value_catalogs: dict[str, ValueCatalog] = Field(
        default_factory=dict,
        description="Map of catalog_key -> ValueCatalog"
    )
    
    def get_field_info(
        self, 
        entity_name: str, 
        field_name: str
    ) -> Optional[FieldSemanticInfo]:
        """Get semantic info for a specific field.
        
        Args:
            entity_name: Name of entity
            field_name: Name of field
            
        Returns:
            FieldSemanticInfo if found, None otherwise
        """
        if entity_name not in self.entities:
            return None
        
        for field_info in self.entities[entity_name]:
            if field_info.field_name == field_name:
                return field_info
        
        return None
    
    def get_catalog(
        self,
        entity_name: str,
        field_name: str
    ) -> Optional[ValueCatalog]:
        """Get value catalog for a specific field.
        
        Args:
            entity_name: Name of entity
            field_name: Name of field
            
        Returns:
            ValueCatalog if found, None otherwise
        """
        # Try exact key match
        key = f"{entity_name}.{field_name}"
        
        if key in self.value_catalogs:
            return self.value_catalogs[key]
        
        # Try by semantic type
        field_info = self.get_field_info(entity_name, field_name)
        if field_info:
            for catalog in self.value_catalogs.values():
                if catalog.semantic_type == field_info.semantic_type:
                    return catalog
        
        return None
    
    def fields_needing_catalogs(self) -> list[FieldSemanticInfo]:
        """Get all fields that need value catalogs.
        
        Returns:
            List of FieldSemanticInfo with generator_strategy="value_catalog"
        """
        catalog_fields = []
        
        for entity_fields in self.entities.values():
            for field_info in entity_fields:
                if field_info.generator_strategy == "value_catalog":
                    catalog_fields.append(field_info)
        
        return catalog_fields
