"""Main semantic analyzer orchestrating all classification methods.

Phase 1 refactor: LLM confined to classification only, never value generation.
"""

import logging
from typing import Optional, List
from .semantic_types import SemanticFieldInfo, FieldContext
from .lexical_classifier import LexicalClassifier
from .pattern_classifier import PatternClassifier
from .context_classifier import ContextClassifier
from .llm_classifier import LLMClassifier

logger = logging.getLogger(__name__)


class SemanticAnalyzer:
    """
    Main semantic analyzer using multi-tier classification.
    
    Pipeline:
    1. Lexical dictionary (fast, high confidence)
    2. Pattern matching (fast, medium confidence)
    3. Context heuristics (fast, medium confidence)
    4. LLM classification (slow, variable confidence)
    5. Fallback (always succeeds, zero confidence)
    """
    
    # Confidence thresholds for early exit
    LEXICAL_THRESHOLD = 0.90
    PATTERN_THRESHOLD = 0.80
    CONTEXT_THRESHOLD = 0.75
    LLM_THRESHOLD = 0.60
    
    def __init__(self, llm_client=None):
        self.lexical = LexicalClassifier()
        self.pattern = PatternClassifier()
        self.context = ContextClassifier()
        self.llm = LLMClassifier(llm_client) if llm_client else None
    
    async def analyze_field(
        self, 
        ctx: FieldContext,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None  # NEW: Phase 4 analytics support
    ) -> SemanticFieldInfo:
        """
        Analyze a single field using multi-tier pipeline.
        
        Returns:
            SemanticFieldInfo (always returns something, never None)
        """
        # Tier 1: Lexical
        result = self.lexical.classify(ctx)
        if result and result.confidence >= self.LEXICAL_THRESHOLD:
            logger.debug(f"Field {ctx.entity_name}.{ctx.field_name} classified via lexical: {result.semantic_type}")
            return result
        
        # Tier 2: Pattern
        result = self.pattern.classify(ctx)
        if result and result.confidence >= self.PATTERN_THRESHOLD:
            logger.debug(f"Field {ctx.entity_name}.{ctx.field_name} classified via pattern: {result.semantic_type}")
            return result
        
        # Tier 3: Context
        result = self.context.classify(ctx)
        if result and result.confidence >= self.CONTEXT_THRESHOLD:
            logger.debug(f"Field {ctx.entity_name}.{ctx.field_name} classified via context: {result.semantic_type}")
            return result
        
        # Tier 4: LLM (if available)
        if self.llm:
            result = await self.llm.classify(
                ctx,
                tenant_id=tenant_id,
                integration_name=integration_name,
                user_id=user_id  # NEW: Pass user_id to LLM classifier
            )
            if result and result.confidence >= self.LLM_THRESHOLD:
                logger.debug(f"Field {ctx.entity_name}.{ctx.field_name} classified via LLM: {result.semantic_type}")
                return result
        
        # Tier 5: Fallback
        return self._fallback_classification(ctx)
    
    async def analyze_schema(
        self, 
        schema: dict, 
        user_prompt: str = None,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None  # NEW: Phase 4 analytics support
    ) -> dict[str, List[SemanticFieldInfo]]:
        """
        Analyze all fields in a schema.
        
        Args:
            schema: Dict with entity names as keys, field definitions as values
            user_prompt: Original user prompt for context
            
        Returns:
            Dict mapping entity names to lists of SemanticFieldInfo
        """
        results = {}
        
        for entity_name, entity_schema in schema.items():
            results[entity_name] = []
            
            # Extract fields (handle different schema formats)
            fields = entity_schema.get("fields", entity_schema.get("properties", {}))
            field_names = list(fields.keys())
            
            for field_name, field_def in fields.items():
                # Build context
                ctx = FieldContext(
                    entity_name=entity_name,
                    field_name=field_name,
                    raw_type=self._extract_type(field_def),
                    nearby_fields=[f for f in field_names if f != field_name],
                    user_prompt=user_prompt,
                    schema_constraints=self._extract_constraints(field_def)
                )
                
                # Analyze
                result = await self.analyze_field(
                    ctx,
                    tenant_id=tenant_id,
                    integration_name=integration_name,
                    user_id=user_id  # NEW: Pass user_id to analyze_field
                )
                results[entity_name].append(result)
        
        return results
    
    def _fallback_classification(self, ctx: FieldContext) -> SemanticFieldInfo:
        """Fallback classification when all other methods fail."""
        logger.warning(
            f"Field '{ctx.entity_name}.{ctx.field_name}' classified as 'unknown' (confidence 0.0). "
            "Using fallback generator."
        )
        
        return SemanticFieldInfo(
            entity_name=ctx.entity_name,
            field_name=ctx.field_name,
            raw_type=ctx.raw_type,
            semantic_type="unknown",
            data_type=ctx.raw_type or "string",
            constraints=ctx.schema_constraints or {},
            source="fallback",
            confidence=0.0
        )
    
    def _extract_type(self, field_def: dict) -> Optional[str]:
        """Extract type from field definition."""
        if isinstance(field_def, dict):
            return field_def.get("type", "string")
        return "string"
    
    def _extract_constraints(self, field_def: dict) -> dict:
        """Extract constraints from field definition."""
        if not isinstance(field_def, dict):
            return {}
        
        constraints = {}
        
        # Check explicit "constraints" dict (from Schema Designer V2)
        if "constraints" in field_def and isinstance(field_def["constraints"], dict):
            constraints.update(field_def["constraints"])
        
        # Check direct keys (Legacy/Direct Schema)
        if "minimum" in field_def:
            constraints["min"] = field_def["minimum"]
        if "maximum" in field_def:
            constraints["max"] = field_def["maximum"]
        if "pattern" in field_def:
            constraints["pattern"] = field_def["pattern"]
        if "enum" in field_def:
            constraints["enum"] = field_def["enum"]
        
        return constraints
