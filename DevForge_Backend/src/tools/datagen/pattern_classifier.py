"""Pattern-based field classification using regex rules."""

import re
from typing import Optional
from .semantic_types import SemanticFieldInfo, FieldContext, SemanticType


class PatternClassifier:
    """Classifies fields based on naming patterns (suffixes, prefixes)."""
    
    # Suffix patterns: (pattern, semantic_type, confidence)
    SUFFIX_PATTERNS = [
        (r"_id$", SemanticType.NUMERIC_ID, 0.85),
        (r"_uuid$", SemanticType.UUID, 0.90),
        (r"_at$", SemanticType.TIMESTAMP, 0.85),
        (r"_date$", SemanticType.DATE, 0.85),
        (r"_time$", SemanticType.TIMESTAMP, 0.80),
        (r"_amount$", SemanticType.MONEY_AMOUNT, 0.85),
        (r"_price$", SemanticType.MONEY_AMOUNT, 0.85),
        (r"_total$", SemanticType.MONEY_AMOUNT, 0.80),
        (r"_percent$", SemanticType.PERCENTAGE, 0.85),
        (r"_percentage$", SemanticType.PERCENTAGE, 0.90),
        (r"_code$", SemanticType.ORDER_CODE, 0.75),
        (r"_number$", SemanticType.NUMERIC_ID, 0.70),
        (r"_email$", SemanticType.EMAIL_ADDRESS, 0.90),
        (r"_phone$", SemanticType.PHONE_NUMBER, 0.85),
    ]
    
    # Prefix patterns
    PREFIX_PATTERNS = [
        (r"^is_", SemanticType.BOOLEAN_FLAG, 0.85),
        (r"^has_", SemanticType.BOOLEAN_FLAG, 0.85),
        (r"^can_", SemanticType.BOOLEAN_FLAG, 0.85),
        (r"^should_", SemanticType.BOOLEAN_FLAG, 0.80),
    ]
    
    def classify(self, ctx: FieldContext) -> Optional[SemanticFieldInfo]:
        """
        Classify field based on patterns.
        
        Returns:
            SemanticFieldInfo if pattern matches with sufficient confidence, else None
        """
        normalized = self._normalize_field_name(ctx.field_name)
        
        # Check suffix patterns first (more specific)
        for pattern, sem_type, confidence in self.SUFFIX_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SemanticFieldInfo(
                    entity_name=ctx.entity_name,
                    field_name=ctx.field_name,
                    raw_type=ctx.raw_type,
                    semantic_type=sem_type.value,
                    data_type=self._infer_data_type(sem_type),
                    constraints=ctx.schema_constraints or {},
                    source="pattern",
                    confidence=confidence
                )
        
        # Check prefix patterns
        for pattern, sem_type, confidence in self.PREFIX_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SemanticFieldInfo(
                    entity_name=ctx.entity_name,
                    field_name=ctx.field_name,
                    raw_type=ctx.raw_type,
                    semantic_type=sem_type.value,
                    data_type=self._infer_data_type(sem_type),
                    constraints=ctx.schema_constraints or {},
                    source="pattern",
                    confidence=confidence
                )
        
        return None
    
    def _normalize_field_name(self, name: str) -> str:
        """Convert camelCase/PascalCase to snake_case, lowercase."""
        name = name.strip()
        # Insert underscore before uppercase letters
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()
    
    def _infer_data_type(self, sem_type: SemanticType) -> str:
        """Map semantic type to data type."""
        type_map = {
            SemanticType.MONEY_AMOUNT: "number",
            SemanticType.PERCENTAGE: "number",
            SemanticType.DATE: "date",
            SemanticType.TIMESTAMP: "timestamp",
            SemanticType.BOOLEAN_FLAG: "boolean",
            SemanticType.UUID: "string",
            SemanticType.NUMERIC_ID: "number",
        }
        return type_map.get(sem_type, "string")
