"""LLM-based field classification (classification only, never value generation)."""

import json
import logging
from typing import Optional
from .semantic_types import SemanticFieldInfo, FieldContext
from src.core.model_router import model_router

logger = logging.getLogger(__name__)


class LLMClassifier:
    """Uses LLM to classify ambiguous fields. NEVER generates values."""
    
    CLASSIFICATION_PROMPT = """You are a strict data schema classifier.
Your job is to classify fields into semantic types and constraints.
You must return ONLY valid JSON matching the provided schema.
Do NOT generate example values. Do NOT write explanations or prose.

Classify the following field. Return ONLY JSON matching this schema:

{{
  "semantic_type": "one of: person_full_name, email_address, phone_number, 
                    company_name, institution_name, flower_name, 
                    bank_account_number, money_amount, date, timestamp,
                    boolean_flag, enum_value, free_text, unknown",
  "data_type": "string | number | boolean | date | timestamp",
  "constraints": {{
    "min": number or null,
    "max": number or null,
    "pattern": string or null,
    "enum": array or null
  }},
  "confidence": float between 0 and 1
}}

Field context:
- Entity name: {entity_name}
- Field name: {field_name}
- Raw type: {raw_type}
- Nearby fields: {nearby_fields}
- User prompt: {user_prompt_truncated}

Return ONLY the JSON object. No markdown, no backticks, no explanations."""

    def __init__(self, llm_client=None):
        """
        Initialize with LLM client.
        
        Args:
            llm_client: LangChain LLM instance or similar. If None, classification will fail gracefully.
        """
        self.llm = llm_client
    async def classify(
        self, 
        ctx: FieldContext,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None
    ) -> Optional[SemanticFieldInfo]:
        """
        Classify field using LLM.
        
        Returns:
            SemanticFieldInfo with LLM classification, or None if LLM fails
        """
        if self.llm is None:
            logger.warning(f"LLM classifier called but no LLM client configured for field: {ctx.field_name}")
            return None
            
        prompt = self._build_prompt(ctx)
        
        try:
            # Phase 2: Use ModelRouter.invoke_with_usage for token tracking
            usage_result = await model_router.invoke_with_usage(
                prompt=prompt,
                tenant_id=tenant_id,
                integration_name=integration_name,
                task_type="datagen_field_classification"
            )
            text = usage_result.content
            
            # Parse JSON
            result = self._parse_response(text)
            if not result:
                logger.warning(f"Failed to parse LLM response for field: {ctx.field_name}")
                return None
            
            # Build SemanticFieldInfo
            return SemanticFieldInfo(
                entity_name=ctx.entity_name,
                field_name=ctx.field_name,
                raw_type=ctx.raw_type,
                semantic_type=result["semantic_type"],
                data_type=result["data_type"],
                constraints=result.get("constraints", {}),
                source="llm",
                confidence=min(max(result.get("confidence", 0.5), 0.0), 1.0)
            )
        
        except Exception as e:
            logger.warning(f"LLM classification failed for {ctx.field_name}: {e}")
            return None
    
    def _build_prompt(self, ctx: FieldContext) -> str:
        """Build classification prompt from context."""
        nearby = ", ".join(ctx.nearby_fields) if ctx.nearby_fields else "none"
        prompt_truncated = (ctx.user_prompt[:200] + "...") if ctx.user_prompt else "none"
        
        return self.CLASSIFICATION_PROMPT.format(
            entity_name=ctx.entity_name,
            field_name=ctx.field_name,
            raw_type=ctx.raw_type or "unknown",
            nearby_fields=nearby,
            user_prompt_truncated=prompt_truncated
        )
    
    def _parse_response(self, text: str) -> Optional[dict]:
        """Parse LLM response, handling common formatting issues and prose."""
        import re
        
        # 1. Strip <thought>...</thought> tags if present (DeepSeek common behavior)
        text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL).strip()
        
        # 2. Extract content between first { and last }
        # This handles cases where the LLM adds prose before or after the JSON
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            text = match.group(1)
        
        # 3. Final attempt at cleaning markdown code blocks if re.search didn't catch it
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        
        try:
            result = json.loads(text)
            
            # Validate required fields
            if "semantic_type" not in result:
                logger.warning(f"LLM response missing 'semantic_type': {result}")
                return None
                
            if "data_type" not in result:
                result["data_type"] = "string"  # Default
            
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse error: {e}. Raw text snippet: {text[:100]}...")
            return None
