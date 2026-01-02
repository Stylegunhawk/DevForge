"""Relationship engine for generating multi-entity data with valid foreign keys.

Handles 1:N relationships by generating parent entities first, then sampling
parent IDs for child entity foreign key assignment. Ensures no orphaned records.

Phase 8.6: Enhanced with semantic-aware field generation support.
"""

import logging
import random
from typing import Any, Optional

from src.tools.datagen.schema_models import SchemaDesign, EntitySchema, FieldSchema
from src.tools.datagen.tools import _generate_field_data
from faker import Faker

# Optional import for semantic-aware generation
try:
    from src.tools.datagen.field_value_generator import FieldValueGenerator
    SEMANTIC_GENERATION_AVAILABLE = True
except ImportError:
    SEMANTIC_GENERATION_AVAILABLE = False

logger = logging.getLogger(__name__)


class RelationshipEngine:
    """Generates multi-entity data respecting 1:N relationships.
    
    Ensures:
    - Parents are generated before children
    - All foreign keys reference valid parent IDs
    - No orphaned records
    - Realistic FK distribution (some parents may have 0 children)
    """
    
    def __init__(self, schema: SchemaDesign, field_generator: Optional['FieldValueGenerator'] = None):
        """Initialize relationship engine with schema.
        
        Args:
            schema: Validated SchemaDesign with entities and relationships
            field_generator: Optional FieldValueGenerator for semantic-aware value generation
                           If None, uses default Faker-based generation (backward compatible)
        """
        self.schema = schema
        self.field_generator = field_generator
        self.generated_entities: dict[str, list[dict[str, Any]]] = {}
        self.fake = Faker()
        Faker.seed(42)  # Reproducible for tests
    
    def generate_all_entities(self) -> dict[str, list[dict[str, Any]]]:
        """Generate data for all entities respecting relationships.
        
        Returns:
            Dictionary mapping entity name -> list of generated records
        """
        # Get generation order (topologically sorted)
        generation_order = self.schema.get_generation_order()
        
        logger.info(
            f"Generating entities in order: {generation_order}",
            extra={"order": generation_order}
        )
        
        # Generate each entity in order
        for entity_name in generation_order:
            entity_schema = self.schema.entities[entity_name]
            records = self._generate_entity(entity_name, entity_schema)
            self.generated_entities[entity_name] = records
            
            logger.info(
                f"Generated {len(records)} records for entity '{entity_name}'",
                extra={"entity": entity_name, "count": len(records)}
            )
        
        return self.generated_entities
    
    def _generate_entity(
        self, 
        entity_name: str, 
        entity_schema: EntitySchema
    ) -> list[dict[str, Any]]:
        """Generate records for a single entity.
        
        Args:
            entity_name: Name of entity to generate
            entity_schema: Entity schema definition
            
        Returns:
            List of generated records
        """
        records = []
        
        # Find FK fields for this entity
        fk_fields = self._get_foreign_key_fields(entity_name)
        
        for i in range(entity_schema.count):
            record = {}
            
            # Generate each field
            for field in entity_schema.fields:
                # Handle foreign key fields specially
                if field.name in fk_fields:
                    parent_entity = fk_fields[field.name]
                    record[field.name] = self._sample_parent_id(parent_entity)
                else:
                    # Regular field - generate value
                    record[field.name] = self._generate_field_value(entity_name, field)
            
            records.append(record)
        
        return records
    
    def _get_foreign_key_fields(self, entity_name: str) -> dict[str, str]:
        """Get foreign key fields for an entity.
        
        Args:
            entity_name: Entity to check
            
        Returns:
            Dictionary mapping FK field name -> parent entity name
        """
        fk_map = {}
        
        for rel in self.schema.relationships:
            if rel.from_entity == entity_name:
                # This entity is the child, so it has the FK
                fk_map[rel.from_field] = rel.to_entity
        
        return fk_map
    
    def _sample_parent_id(self, parent_entity: str) -> Any:
        """Sample a random parent ID from already-generated parent entity.
        
        Args:
            parent_entity: Name of parent entity
            
        Returns:
            A valid ID from the parent entity
            
        Raises:
            ValueError: If parent entity not yet generated
        """
        if parent_entity not in self.generated_entities:
            raise ValueError(
                f"Parent entity '{parent_entity}' not yet generated. "
                f"Check generation order."
            )
        
        parent_records = self.generated_entities[parent_entity]
        if not parent_records:
            raise ValueError(f"Parent entity '{parent_entity}' has no records")
        
        # Find primary key field for parent
        parent_schema = self.schema.entities[parent_entity]
        pk_field = parent_schema.primary_key
        
        # Randomly sample a parent record
        parent_record = random.choice(parent_records)
        return parent_record[pk_field]
    
    def _generate_field_value(self, entity_name: str, field: FieldSchema) -> Any:
        """Generate value for a single field.
        
        Args:
            entity_name: Name of entity (for semantic context)
            field: Field schema
            
        Returns:
            Generated field value
            
        Uses semantic-aware generator if available, otherwise falls back to Faker.
        """
        # Handle nullable fields (some chance of null)
        if field.nullable and random.random() < 0.1:  # 10% null rate for nullable fields
            return None

        # Use semantic-aware generator if available
        if self.field_generator and SEMANTIC_GENERATION_AVAILABLE:
            try:
                generator_func = self.field_generator.get_generator(entity_name, field.name)
                return generator_func()
            except Exception as e:
                logger.warning(
                    f"Semantic generator failed for {entity_name}.{field.name}: {e}. "
                    "Falling back to Faker."
                )
                # Fall through to Faker fallback
        
        # Fallback to original Faker-based generation
        if field.faker_provider:
            try:
                return getattr(self.fake, field.faker_provider)()
            except (AttributeError, TypeError) as e:
                logger.warning(
                    f"Faker provider '{field.faker_provider}' failed for {entity_name}.{field.name}: {e}. "
                    "Falling back to type-based generation."
                )
        
        # Final fallback based on type
        if field.type == "uuid":
            return str(self.fake.uuid4())
        elif field.type == "string":
            return self.fake.text(max_nb_chars=50)
        elif field.type == "int":
            return self.fake.random_int(min=1, max=1000)
        elif field.type == "float":
            return round(self.fake.random.uniform(1.0, 1000.0), 2)
        elif field.type == "date":
            return self.fake.date()
        elif field.type == "datetime":
            return self.fake.date_time().isoformat()
        elif field.type == "boolean":
            return self.fake.boolean()
        else:
            # Fallback
            return self.fake.text(max_nb_chars=50)
    
    def validate_relationships(self) -> dict[str, Any]:
        """Validate that all relationships are satisfied.
        
        Checks:
        - All FKs reference valid parent IDs
        - No orphaned records
        - Returns statistics about FK distributions
        
        Returns:
            Validation report with statistics
        """
        report = {
            "valid": True,
            "errors": [],
            "statistics": {}
        }
        
        for rel in self.schema.relationships:
            child_entity = rel.from_entity
            parent_entity = rel.to_entity
            fk_field = rel.from_field
            pk_field = rel.to_field
            
            # Get data
            child_records = self.generated_entities.get(child_entity, [])
            parent_records =self.generated_entities.get(parent_entity, [])
            
            # Extract parent IDs
            parent_ids = {rec[pk_field] for rec in parent_records}
            
            # Check all FKs are valid
            orphaned_count = 0
            for child_rec in child_records:
                fk_value = child_rec.get(fk_field)
                if fk_value not in parent_ids:
                    orphaned_count += 1
                    report["valid"] = False
                    report["errors"].append(
                        f"Orphaned FK in {child_entity}.{fk_field}: {fk_value}"
                    )
            
            # Calculate distribution stats
            fk_counts = {}
            for child_rec in child_records:
                fk_value = child_rec.get(fk_field)
                fk_counts[fk_value] = fk_counts.get(fk_value, 0) + 1
            
            parents_with_zero_children = len(parent_ids - set(fk_counts.keys()))
            
            report["statistics"][f"{child_entity}->{parent_entity}"] = {
                "total_children": len(child_records),
                "total_parents": len(parent_records),
                "parents_with_children": len(fk_counts),
                "parents_with_zero_children": parents_with_zero_children,
                "orphaned_children": orphaned_count,
                "max_children_per_parent": max(fk_counts.values()) if fk_counts else 0,
                "min_children_per_parent": min(fk_counts.values()) if fk_counts else 0,
            }
        
        return report


def generate_relational_data(schema: SchemaDesign) -> dict[str, list[dict[str, Any]]]:
    """Convenience function to generate relational data from schema.
    
    Args:
        schema: Validated SchemaDesign
        
    Returns:
        Dictionary mapping entity name -> list of records
    """
    engine = RelationshipEngine(schema)
    return engine.generate_all_entities()
