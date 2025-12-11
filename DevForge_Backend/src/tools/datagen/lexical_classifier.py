"""Lexical dictionary-based field classification."""

from typing import Optional
from .semantic_types import SemanticFieldInfo, FieldContext
from .lexical_dict import lookup_lexical, SemanticType


class LexicalClassifier:
    """Classifies fields using a dictionary of known field names."""
    
    def __init__(self):
        """Initialize lexical classifier using the Python lexical_dict module."""
        pass  # Uses lookup_lexical function from lexical_dict.py
    
    def classify(self, ctx: FieldContext) -> Optional[SemanticFieldInfo]:
        """
        Classify field using lexical dictionary.
        
        Returns:
            SemanticFieldInfo if exact match found, else None
        """
        semantic_type = lookup_lexical(ctx.field_name)
        
        if semantic_type is not None:
            return SemanticFieldInfo(
                entity_name=ctx.entity_name,
                field_name=ctx.field_name,
                raw_type=ctx.raw_type,
                semantic_type=semantic_type.value,
                data_type=self._infer_data_type(semantic_type),
                constraints=ctx.schema_constraints or {},
                source="lexical",
                confidence=0.95  # High confidence for exact matches
            )
        
        return None
    
    def _infer_data_type(self, semantic_type: SemanticType) -> str:
        """Infer data type from semantic type."""
        type_map = {
            SemanticType.MONEY_AMOUNT: "number",
            SemanticType.PERCENTAGE: "number",
            SemanticType.DATE: "date",
            SemanticType.TIMESTAMP: "timestamp",
            SemanticType.BOOLEAN_FLAG: "boolean",
            SemanticType.NUMERIC_ID: "number",
        }
        return type_map.get(semantic_type, "string")
