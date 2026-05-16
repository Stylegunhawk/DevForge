"""LLM-powered schema designer for advanced data generation.

Uses the ModelRouter to call an LLM for designing data schemas
from natural language prompts. Includes robust fallback logic.
"""

import json
import logging
import re
from typing import Any, Optional

from src.core.model_router import model_router
from src.tools.datagen.schema_models import (
    EntitySchema,
    FieldSchema,
    RelationshipSchema,
    SchemaDesign,
    create_minimal_schema,
)

logger = logging.getLogger(__name__)


# System prompt for LLM schema generation
SCHEMA_DESIGN_PROMPT = """You are a data schema designer. Given a natural language description, 
design a data schema for synthetic data generation.

Output ONLY valid JSON matching this exact structure:

{
  "entities": {
    "entity_name": {
      "name": "entity_name",
      "fields": [
        {
          "name": "field_name", 
          "type": "string|int|float|date|datetime|boolean|uuid", 
          "nullable": false, 
          "faker_provider": "email|name|phone_number|etc",
          "constraints": {"enum": ["A", "B"], "min": 0, "max": 100, "pattern": "^regex$"}
        }
      ],
      "count": 100,
      "primary_key": "id"
    }
  },
  "relationships": [
    {"from_entity": "child", "from_field": "parent_id", "to_entity": "parent", "to_field": "id", "cardinality": "1:N"}
  ],
  "domain": "optional_domain_hint"
}

Rules:
1. Use snake_case for all names
2. Allowed types: string, int, float, date, datetime, boolean, uuid
3. faker_provider options: name, email, phone_number, address, company, job, city, country, url, text, uuid4, date, date_time
4. Mark `nullable: true` for fields that represent optional or often-missing information in real production data.
   Always nullable: middle_name, address_line_2, description, comment, last_login, deleted_at, deactivation_reason, suffix, extension, error_message, notes
   Often nullable (mark true if the domain suggests it): phone, alternate_email, referral_code, promo_code, attachment_url, cancellation_reason
   Never nullable: id, primary_key, the primary email when it is the contact key, created_at, foreign keys
5. Use "constraints" for enums, numeric ranges (min/max), and regex patterns
6. For relationships: from_entity is the child (has FK), to_entity is the parent
7. Add appropriate primary keys (default: "id" with uuid type)
8. Be realistic with counts (10-1000 typical, max 10000)

Now design a schema for this request:
"""


class SchemaDesigner:
    """LLM-powered schema designer with fallback support.
    
    Uses the project's ModelRouter to call LLM for schema design.
    Falls back to domain templates or minimal schema on failure.
    """
    
    def __init__(self, model_task: str = "routing"):
        """Initialize schema designer.
        
        Args:
            model_task: Task type for model selection (default: "routing" for deepseek-r1:8b)
        """
        self.model_task = model_task
    
    def get_domain_template(self, domain: str, requested_rows: Optional[int] = None) -> Optional[SchemaDesign]:
        """Get pre-defined template for a domain with optional row scaling.
        
        Args:
            domain: Domain name (e.g., "ecommerce", "saas")
            requested_rows: Optional total row count for scaling
            
        Returns:
            SchemaDesign if domain exists, None otherwise
        """
        from src.tools.datagen.domain_templates import get_template
        try:
            return get_template(domain, requested_rows=requested_rows)
        except ValueError:
            return None
    
    async def design_schema(
        self,
        prompt: str,
        domain: Optional[str] = None,
        default_rows: int = 100,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None  # NEW: Phase 4 analytics support
    ) -> SchemaDesign:
        """Design a schema from natural language prompt.
        
        Uses LLM to generate schema, falls back to templates or minimal schema.
        
        Args:
            prompt: Natural language description of desired data
            domain: Optional domain hint for template fallback
            default_rows: Default row count for entities
            
        Returns:
            Validated SchemaDesign
        """
        # If domain specified and we have a template, use it directly with scaling
        if domain:
            template = self.get_domain_template(domain, requested_rows=default_rows)
            if template:
                logger.info(f"Using domain template for: {domain} (scaled to ~{default_rows} rows)")
                return template
        
        # Try LLM-based schema design
        try:
            schema = await self._design_with_llm(
                prompt, 
                default_rows,
                tenant_id=tenant_id,
                integration_name=integration_name,
                user_id=user_id  # NEW: Pass user_id to _design_with_llm
            )
            if schema:
                logger.info(f"LLM schema design successful: {len(schema.entities)} entities")
                return schema
        except Exception as e:
            logger.warning(f"LLM schema design failed: {e}")
        
        # Fallback: try to infer domain from prompt
        inferred_domain = self._infer_domain(prompt)
        if inferred_domain:
            template = self.get_domain_template(inferred_domain, requested_rows=default_rows)
            if template:
                logger.info(f"Using inferred domain template: {inferred_domain} (scaled to ~{default_rows} rows)")
                return template
        
        # Ultimate fallback: minimal schema
        logger.info("Using minimal fallback schema")
        return create_minimal_schema(default_rows)
    
    async def _design_with_llm(
        self, 
        prompt: str, 
        default_rows: int,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None  # NEW: Phase 4 analytics support
    ) -> Optional[SchemaDesign]:
        """Call LLM to design schema.
        
        Args:
            prompt: User's natural language description
            default_rows: Default row count
            
        Returns:
            SchemaDesign if successful, None if failed
        """
        try:
            # Get model for schema design
            model_name = model_router.select_model_by_task(self.model_task)
            chat_model = model_router.get_chat_model(model_name)
            
            # Build full prompt
            full_prompt = SCHEMA_DESIGN_PROMPT + prompt
            
            logger.info(f"Calling LLM for schema design with model: {model_name}")
            
            # Call LLM with auto-logging
            usage_result = await model_router.invoke_with_usage(
                prompt=full_prompt,
                model_name=model_name,
                tenant_id=tenant_id,
                integration_name=integration_name,
                task_type="datagen_schema_design",
                user_id=user_id  # NEW: Pass user_id to ModelRouter
            )
            
            # Extract content
            content = usage_result.content
            
            # Parse JSON from response
            schema_dict = self._extract_json(content)
            if not schema_dict:
                logger.warning("Could not extract JSON from LLM response")
                return None
            
            # Validate through Pydantic
            schema = SchemaDesign.model_validate(schema_dict)
            
            return schema
            
        except Exception as e:
            logger.error(f"LLM schema design error: {e}", exc_info=True)
            return None
    
    def _extract_json(self, text: str) -> Optional[dict[str, Any]]:
        """Extract JSON object from LLM response text.
        
        Handles responses with markdown code blocks or raw JSON.
        
        Args:
            text: Raw LLM response
            
        Returns:
            Parsed dict or None if extraction failed
        """
        # Try to find JSON in code blocks
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(code_block_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # Try to find raw JSON object
        json_pattern = r"\{[\s\S]*\}"
        match = re.search(json_pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Try parsing the whole text
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None
    
    def _infer_domain(self, prompt: str) -> Optional[str]:
        """Infer domain from prompt keywords.
        
        Args:
            prompt: User's natural language prompt
            
        Returns:
            Domain name if inferred, None otherwise
        """
        prompt_lower = prompt.lower()
        
        # E-commerce keywords
        ecommerce_keywords = ["ecommerce", "e-commerce", "shop", "store", "product", 
                             "order", "cart", "customer", "purchase", "retail"]
        if any(kw in prompt_lower for kw in ecommerce_keywords):
            return "ecommerce"
        
        # SaaS keywords
        saas_keywords = ["saas", "subscription", "user", "plan", "usage", 
                        "billing", "tenant", "api", "dashboard"]
        if any(kw in prompt_lower for kw in saas_keywords):
            return "saas"
        
        return None
    
    def design_schema_sync(
        self,
        prompt: str,
        domain: Optional[str] = None,
        default_rows: int = 100
    ) -> SchemaDesign:
        """Synchronous version for simple use cases (no LLM call).
        
        Only uses domain templates or minimal fallback. No LLM.
        
        Args:
            prompt: Natural language description
            domain: Optional domain hint
            default_rows: Default row count
            
        Returns:
            SchemaDesign from template or minimal fallback
        """
        # Check domain template first
        if domain:
            template = self.get_domain_template(domain, requested_rows=default_rows)
            if template:
                return template
        
        # Try to infer domain
        inferred_domain = self._infer_domain(prompt)
        if inferred_domain:
            template = self.get_domain_template(inferred_domain, requested_rows=default_rows)
            if template:
                return template
        
        # Minimal fallback
        return create_minimal_schema(default_rows)


# Module-level instance for convenience
schema_designer = SchemaDesigner()
