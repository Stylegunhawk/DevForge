"""Pydantic models for schema-aware data generation.

Defines validated schema structures for entities, fields, relationships,
and the composite SchemaDesign used by the advanced DataGen tool.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class FieldSchema(BaseModel):
    """Schema for a single field within an entity.
    
    Attributes:
        name: Field name (snake_case recommended)
        type: Data type for generation
        nullable: Whether field can contain null values
        faker_provider: Optional Faker method hint (e.g., "email", "phone_number")
        distribution: Optional distribution hint for numeric fields
    """
    
    name: str = Field(..., min_length=1, max_length=64, description="Field name")
    type: Literal["string", "int", "float", "date", "datetime", "boolean", "uuid"] = Field(
        ..., description="Data type"
    )
    nullable: bool = Field(default=False, description="Whether field can be null")
    faker_provider: Optional[str] = Field(
        default=None, 
        description="Faker method hint (e.g., 'email', 'name', 'phone_number')"
    )
    distribution: Optional[Literal["uniform", "normal", "lognormal", "pareto", "categorical"]] = Field(
        default=None,
        description="Distribution for numeric fields"
    )
    constraints: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional constraints (min, max, enum, pattern)"
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure field name is valid identifier-like."""
        v = v.strip()
        if not v:
            raise ValueError("Field name cannot be empty")
        # Allow alphanumeric and underscores
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError(f"Field name must be alphanumeric with underscores: {v}")
        return v.lower()


class EntitySchema(BaseModel):
    """Schema for a single entity (table/collection).
    
    Attributes:
        name: Entity name (e.g., "customers", "orders")
        fields: List of field definitions
        count: Number of rows to generate
        primary_key: Name of the primary key field (auto-generated if not in fields)
    """
    
    name: str = Field(..., min_length=1, max_length=64, description="Entity name")
    fields: list[FieldSchema] = Field(..., min_length=1, description="Entity fields")
    count: int = Field(default=100, gt=0, le=100000, description="Row count")
    primary_key: str = Field(default="id", description="Primary key field name")
    
    @field_validator("name")
    @classmethod
    def validate_entity_name(cls, v: str) -> str:
        """Ensure entity name is valid."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Entity name cannot be empty")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError(f"Entity name must be alphanumeric with underscores: {v}")
        return v
    
    @model_validator(mode="after")
    def ensure_primary_key_field(self) -> "EntitySchema":
        """Ensure primary key field exists in fields list."""
        field_names = {f.name for f in self.fields}
        if self.primary_key not in field_names:
            # Auto-add primary key as UUID field
            pk_field = FieldSchema(name=self.primary_key, type="uuid", nullable=False)
            self.fields = [pk_field] + list(self.fields)
        return self


class RelationshipSchema(BaseModel):
    """Schema for entity relationships (foreign keys).
    
    Defines a relationship from a child entity to a parent entity.
    Currently supports only 1:N (one-to-many) relationships.
    
    Attributes:
        from_entity: Child entity name (the one with the FK)
        from_field: Foreign key field name in child
        to_entity: Parent entity name (the one being referenced)
        to_field: Primary key field name in parent
        cardinality: Relationship cardinality (1:N only for v1)
    """
    
    from_entity: str = Field(..., description="Child entity name")
    from_field: str = Field(..., description="Foreign key field in child")
    to_entity: str = Field(..., description="Parent entity name")
    to_field: str = Field(default="id", description="Primary key field in parent")
    cardinality: Literal["1:N", "1:1", "N:1"] = Field(
        default="1:N", 
        description="Relationship cardinality"
    )


class SchemaDesign(BaseModel):
    """Complete schema design for multi-entity data generation.
    
    Contains all entities, their fields, and relationships between them.
    Validated to ensure referential integrity.
    
    Attributes:
        entities: Dictionary of entity name -> EntitySchema
        relationships: List of relationship definitions
        domain: Optional domain hint (ecommerce, saas, etc.)
    """
    
    entities: dict[str, EntitySchema] = Field(
        ..., 
        min_length=1, 
        description="Entity definitions"
    )
    relationships: list[RelationshipSchema] = Field(
        default_factory=list, 
        description="Entity relationships"
    )
    domain: Optional[str] = Field(
        default=None, 
        description="Domain hint (ecommerce, saas)"
    )
    
    @model_validator(mode="after")
    def validate_relationships(self) -> "SchemaDesign":
        """Ensure all relationship references are valid."""
        entity_names = set(self.entities.keys())
        
        for rel in self.relationships:
            # Validate from_entity exists
            if rel.from_entity not in entity_names:
                raise ValueError(
                    f"Relationship from_entity '{rel.from_entity}' not found in entities: {entity_names}"
                )
            
            # Validate to_entity exists
            if rel.to_entity not in entity_names:
                raise ValueError(
                    f"Relationship to_entity '{rel.to_entity}' not found in entities: {entity_names}"
                )
            
            # Validate to_field exists in parent entity
            parent_entity = self.entities[rel.to_entity]
            parent_field_names = {f.name for f in parent_entity.fields}
            if rel.to_field not in parent_field_names:
                raise ValueError(
                    f"Relationship to_field '{rel.to_field}' not found in entity '{rel.to_entity}'. "
                    f"Available fields: {parent_field_names}"
                )
            
            # Validate from_field exists in child entity (or add it)
            child_entity = self.entities[rel.from_entity]
            child_field_names = {f.name for f in child_entity.fields}
            if rel.from_field not in child_field_names:
                # Auto-add foreign key field
                fk_field = FieldSchema(
                    name=rel.from_field,
                    type="uuid",  # Match parent PK type
                    nullable=False,
                    faker_provider=None
                )
                child_entity.fields.append(fk_field)
        
        return self
    
    def get_generation_order(self) -> list[str]:
        """Get topologically sorted order for entity generation.
        
        Parents must be generated before children to ensure valid FK references.
        
        Returns:
            List of entity names in generation order
        """
        # Build dependency graph: child -> set of parents
        dependencies: dict[str, set[str]] = {name: set() for name in self.entities}
        
        for rel in self.relationships:
            # from_entity (child) depends on to_entity (parent)
            dependencies[rel.from_entity].add(rel.to_entity)
        
        # Kahn's algorithm for topological sort
        result = []
        no_deps = [name for name, deps in dependencies.items() if not deps]
        
        while no_deps:
            # Take entity with no dependencies
            entity = no_deps.pop(0)
            result.append(entity)
            
            # Remove this entity from other dependencies
            for name, deps in dependencies.items():
                deps.discard(entity)
                if not deps and name not in result and name not in no_deps:
                    no_deps.append(name)
        
        # Check for cycles
        if len(result) != len(self.entities):
            remaining = set(self.entities.keys()) - set(result)
            raise ValueError(f"Circular dependency detected involving: {remaining}")
        
        return result


# Convenience function to create minimal fallback schema
def create_minimal_schema(rows: int = 100) -> SchemaDesign:
    """Create a minimal fallback schema with basic fields.
    
    Used when LLM schema generation fails or returns invalid results.
    
    Args:
        rows: Number of rows to generate
        
    Returns:
        Simple SchemaDesign with one entity
    """
    return SchemaDesign(
        entities={
            "records": EntitySchema(
                name="records",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="name"),
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="phone", type="string", faker_provider="phone_number"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=rows,
                primary_key="id"
            )
        },
        relationships=[],
        domain=None
    )
