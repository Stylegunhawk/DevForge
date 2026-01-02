"""Realism engine for injecting realistic data quality issues.

Adds nulls, duplicates, and outliers based on realism level.
Makes generated data more realistic by mimicking real-world imperfections.
"""

import random
from typing import Any, Literal


# Realism level configurations
REALISM_CONFIGS = {
    "basic": {
        "null_rate": 0.0,       # 0% nulls
        "duplicate_rate": 0.0,  # 0% duplicates
        "outlier_rate": 0.0,    # 0% outliers
    },
    "medium": {
        "null_rate": 0.05,      # 5% nulls on nullable fields
        "duplicate_rate": 0.0,  # 0% duplicates
        "outlier_rate": 0.0,    # 0% outliers
    },
    "high": {
        "null_rate": 0.10,      # 10% nulls on nullable fields
        "duplicate_rate": 0.02, # 2% duplicates on key-like fields
        "outlier_rate": 0.01,   # 1% numeric outliers
    },
}


class RealismEngine:
    """Injects realistic data quality issues into generated data.
    
    Applies three types of imperfections:
    1. Null injection: Random nulls in nullable fields
    2. Duplicate injection: Duplicates in key-like fields (email, phone)
    3. Outlier injection: Extreme values in numeric fields
    """
    
    def __init__(self, realism_level: Literal["basic", "medium", "high"] = "basic"):
        """Initialize realism engine.
        
        Args:
            realism_level: Level of realism to apply
        """
        if realism_level not in REALISM_CONFIGS:
            raise ValueError(
                f"Invalid realism_level: '{realism_level}'. "
                f"Must be one of: {list(REALISM_CONFIGS.keys())}"
            )
        
        self.level = realism_level
        self.config = REALISM_CONFIGS[realism_level]
    
    def apply_realism(
        self,
        data: list[dict[str, Any]],
        entity_name: str,
        nullable_fields: set[str],
        key_fields: set[str],
        numeric_fields: set[str]
    ) -> list[dict[str, Any]]:
        """Apply realism to generated data.
        
        Args:
            data: List of records to modify
            entity_name: Name of entity (for logging)
            nullable_fields: Fields that can be null
            key_fields: Fields that should have few duplicates (email, phone, etc.)
            numeric_fields: Numeric fields for outlier injection
            
        Returns:
            Modified data with realism applied
        """
        if not data:
            return data
        
        # Apply null injection
        if self.config["null_rate"] > 0:
            data = self._inject_nulls(data, nullable_fields)
        
        # Apply duplicate injection
        if self.config["duplicate_rate"] > 0:
            data = self._inject_duplicates(data, key_fields)
        
        # Apply outlier injection
        if self.config["outlier_rate"] > 0:
            data = self._inject_outliers(data, numeric_fields)
        
        return data
    
    def _inject_nulls(
        self,
        data: list[dict[str, Any]],
        nullable_fields: set[str]
    ) -> list[dict[str, Any]]:
        """Inject nulls into nullable fields.
        
        Args:
            data: Records to modify
            nullable_fields: Fields that can be null
            
        Returns:
            Modified data
        """
        null_rate = self.config["null_rate"]
        
        for record in data:
            for field in nullable_fields:
                if field in record and random.random() < null_rate:
                    record[field] = None
        
        return data
    
    def _inject_duplicates(
        self,
        data: list[dict[str, Any]],
        key_fields: set[str]
    ) -> list[dict[str, Any]]:
        """Inject duplicates into key-like fields.
        
        Randomly picks existing values and reuses them to create duplicates.
        
        Args:
            data: Records to modify
            key_fields: Fields that should have few duplicates
            
        Returns:
            Modified data
        """
        duplicate_rate = self.config["duplicate_rate"]
        
        if not data or not key_fields:
            return data
        
        # For each key field, collect existing values
        for field in key_fields:
            # Get all non-null values for this field
            values = [rec[field] for rec in data if field in rec and rec[field] is not None]
            
            if not values:
                continue
            
            # Inject duplicates
            for record in data:
                if field in record and random.random() < duplicate_rate:
                    # Replace with a random existing value
                    record[field] = random.choice(values)
        
        return data
    
    def _inject_outliers(
        self,
        data: list[dict[str, Any]],
        numeric_fields: set[str]
    ) -> list[dict[str, Any]]:
        """Inject outliers into numeric fields.
        
        Creates extreme values (10x or 0.1x the original value).
        
        Args:
            data: Records to modify
            numeric_fields: Numeric fields for outlier injection
            
        Returns:
            Modified data
        """
        outlier_rate = self.config["outlier_rate"]
        
        for record in data:
            for field in numeric_fields:
                if field in record and random.random() < outlier_rate:
                    value = record[field]
                    
                    # Skip if null or zero
                    if value is None or value == 0:
                        continue
                    
                    # Randomly make it 10x larger or 0.1x smaller
                    if random.random() < 0.5:
                        record[field] = value * 10
                    else:
                        record[field] = value * 0.1
        
        return data


def apply_realism_to_data(
    data: dict[str, list[dict[str, Any]]],
    schema_design,
    realism_level: Literal["basic", "medium", "high"] = "basic"
) -> dict[str, list[dict[str, Any]]]:
    """Apply realism to multi-entity data.
    
    Args:
        data: Dictionary of entity_name -> list of records
        schema_design: SchemaDesign object with entity metadata
        realism_level: Level of realism to apply
        
    Returns:
        Modified data with realism applied
    """
    engine = RealismEngine(realism_level)
    
    # Apply realism to each entity
    for entity_name, records in data.items():
        if entity_name not in schema_design.entities:
            continue
        
        entity_schema = schema_design.entities[entity_name]
        
        # Identify field types
        nullable_fields = {f.name for f in entity_schema.fields if f.nullable}
        
        # Key-like fields: email, phone, username, etc.
        key_fields = {
            f.name for f in entity_schema.fields
            if any(kw in f.name.lower() for kw in ["email", "phone", "username"])
        }
        
        # Numeric fields
        numeric_fields = {
            f.name for f in entity_schema.fields
            if f.type in ["int", "float"]
        }
        
        # Apply realism
        data[entity_name] = engine.apply_realism(
            records,
            entity_name,
            nullable_fields,
            key_fields,
            numeric_fields
        )
    
    return data
