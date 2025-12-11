"""Semantic field analyzer using LLM for intelligent field type inference.

Analyzes entity fields to infer:
- Semantic type (what the field represents in the real world)
- Generator strategy (how to generate realistic values)
- Constraints (value ranges, patterns, examples)

Phase 8.6: Fixes "Daniel Doyle flower" bug by understanding context.
"""

import json
import logging
import re
from typing import Optional

from src.core.model_router import model_router
from src.tools.datagen.schema_models import SchemaDesign
from src.tools.datagen.semantic_models import (
    SemanticPlan,
    FieldSemanticInfo,
)

logger = logging.getLogger(__name__)


# System prompt for LLM semantic analysis
SEMANTIC_ANALYSIS_SYSTEM_PROMPT = """You are a data schema analyzer. Analyze entity fields and infer:

1. **semantic_type**: The real-world meaning of the field
   Examples: "flower_name", "university_name", "botanical_family", "person_email"

2. **generator_strategy**: Best method to generate values:
   - "faker": Use Faker library (email, phone, person name, address, etc.)
   - "numeric_distribution": Use statistical distributions (price, count, rating)
   - "datetime_range": Use temporal patterns (timestamps, dates)
   - "uuid": Generate unique IDs
   - "mongo_object_id": Generate MongoDB ObjectIds
   - "value_catalog": Need LLM-generated catalog of domain-specific values
   - "generic_text": Random text fallback

3. **constraints**: Ranges, formats, examples (optional)

OUTPUT FORMAT: Return ONLY valid JSON array (no markdown, no explanations):

[
  {
    "entity_name": "flowers",
    "field_name": "name",
    "db_type": "string",
    "semantic_type": "flower_name",
    "generator_strategy": "value_catalog",
    "constraints": {"examples": ["Rose", "Tulip"]},
    "notes": "Botanical flower names, not person names"
  }
]

CRITICAL RULES:
- For domain-specific fields (flower names, university names, tool types), ALWAYS use "value_catalog"
- For generic fields (email, phone), use "faker"
- Understand context: "name" in "flowers" ≠ "name" in "users"
- Be precise: botanical family ≠ company name"""


class SemanticAnalyzer:
    """LLM-powered field semantic analyzer.
    
    Analyzes schema fields to understand what they semantically represent
    and determines the best strategy for generating realistic values.
    """
    
    def __init__(self, model_task: str = "routing"):
        """Initialize semantic analyzer.
        
        Args:
            model_task: Task type for model selection (default: "routing")
        """
        self.model_task = model_task
        self.timeout = 30
        self.max_retries = 2
    
    async def analyze_schema(
        self,
        schema: SchemaDesign,
        prompt: str
    ) -> SemanticPlan:
        """Analyze entity fields and infer semantic types.
        
        Args:
            schema: SchemaDesign with entities + relationships
            prompt: User's natural language description
            
        Returns:
            SemanticPlan with field metadata + strategies
            
        Example:
            Input: universities.name (string)
            Output: semantic_type="university_name", 
                    generator_strategy="value_catalog"
        """
        logger.info(f"Starting semantic analysis for {len(schema.entities)} entities")
        
        try:
            # Call LLM for analysis
            plan = await self._analyze_with_llm(schema, prompt)
            
            logger.info(f"LLM semantic analysis successful: {len(plan.entities)} entities analyzed")
            return plan
            
        except Exception as e:
            # Fallback to heuristics
            logger.warning(f"LLM semantic analysis failed: {e}, using heuristic fallback")
            return self._fallback_heuristic_analysis(schema)
    
    async def _analyze_with_llm(
        self,
        schema: SchemaDesign,
        prompt: str
    ) -> SemanticPlan:
        """Perform LLM-powered semantic analysis."""
        
        # Build user prompt
        user_prompt = self._build_user_prompt(schema, prompt)
        
        #Call LLM with retry
        for attempt in range(self.max_retries):
            try:
                # Get LLM model
                model_name = model_router.select_model_by_task(self.model_task)
                chat_model = model_router.get_chat_model(model_name)
                
                logger.info(f"Calling LLM for semantic analysis (model: {model_name}, attempt: {attempt + 1})")
                
                # Invoke LLM
                response = await chat_model.ainvoke([
                    {"role": "system", "content": SEMANTIC_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ])
                
                # Extract and parse response
                content = response.content if hasattr(response, "content") else str(response)
                plan = self._parse_llm_response(content, schema)
                
                return plan
                
            except TimeoutError:
                if attempt < self.max_retries - 1:
                    logger.warning(f"LLM timeout, retry {attempt + 1}/{self.max_retries}")
                    continue
                raise
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"LLM error: {e}, retry {attempt + 1}/{self.max_retries}")
                    continue
                raise
    
    def _build_user_prompt(self, schema: SchemaDesign, prompt: str) -> str:
        """Build user prompt with schema details."""
        
        # Format entities and fields
        entities_info = []
        for entity_name, entity in schema.entities.items():
            fields_list = []
            for field in entity.fields:
                field_str = f"{field.name} ({field.type})"
                if field.faker_provider:
                    field_str += f" [faker: {field.faker_provider}]"
                fields_list.append(field_str)
            
            entities_info.append(f"- **{entity_name}**: {', '.join(fields_list)}")
        
        entities_str = "\n".join(entities_info)
        
        return f"""Analyze these entities for semantic data generation:

{entities_str}

User's request: "{prompt}"

Return JSON array with semantic analysis for each field.
Remember: Use "value_catalog" for domain-specific fields that need custom values."""
    
    def _parse_llm_response(self, response: str, schema: SchemaDesign) -> SemanticPlan:
        """Parse LLM JSON response into SemanticPlan."""
        
        # Strip markdown code fences
        response = re.sub(r'```json\s*|\s*```', '', response).strip()
        response = re.sub(r'```\s*|\s*```', '', response).strip()
        
        # Parse JSON
        try:
            fields_data = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON from LLM: {e}\nResponse: {response[:200]}")
        
        if not isinstance(fields_data, list):
            raise ValueError(f"Expected JSON array, got: {type(fields_data)}")
        
        # Group by entity
        entities_info = {}
        for field_data in fields_data:
            try:
                # Validate required fields
                if "entity_name" not in field_data or "field_name" not in field_data:
                    logger.warning(f"Skipping invalid field data: {field_data}")
                    continue
                
                entity = field_data["entity_name"]
                if entity not in entities_info:
                    entities_info[entity] = []
                
                # Create FieldSemanticInfo
                field_info = FieldSemanticInfo(
                    entity_name=field_data["entity_name"],
                    field_name=field_data["field_name"],
                    db_type=field_data.get("db_type", "string"),
                    semantic_type=field_data.get("semantic_type", "generic_text"),
                    generator_strategy=field_data.get("generator_strategy", "generic_text"),
                    constraints=field_data.get("constraints"),
                    notes=field_data.get("notes")
                )
                
                entities_info[entity].append(field_info)
                
            except Exception as e:
                logger.warning(f"Error parsing field data: {e}, data: {field_data}")
                continue
        
        return SemanticPlan(
            entities=entities_info,
            value_catalogs={}  # Populated later by CatalogBuilder
        )
    
    def _fallback_heuristic_analysis(self, schema: SchemaDesign) -> SemanticPlan:
        """Fallback: Use field name patterns to guess semantic types.
        
        Used when LLM fails. Provides basic but functional semantic analysis.
        """
        logger.info("Using heuristic fallback for semantic analysis")
        
        entities_info = {}
        
        for entity_name, entity in schema.entities.items():
            fields_info = []
            
            for field in entity.fields:
                # Infer semantic type from field name and entity context
                semantic_type = self._infer_semantic_type(field.name, entity_name, field.type)
                
                # Infer strategy from semantic type and db type
                strategy = self._infer_strategy(field.name, field.type, semantic_type, field.faker_provider)
                
                fields_info.append(FieldSemanticInfo(
                    entity_name=entity_name,
                    field_name=field.name,
                    db_type=field.type,
                    semantic_type=semantic_type,
                    generator_strategy=strategy,
                    constraints=None,
                    notes="Heuristic fallback (LLM unavailable)"
                ))
            
            entities_info[entity_name] = fields_info
        
        return SemanticPlan(entities=entities_info, value_catalogs={})
    
    def _infer_semantic_type(self, field_name: str, entity_name: str, db_type: str) -> str:
        """Infer semantic type from field name and context."""
        
        name_lower = field_name.lower()
        
        # Email patterns (check before generic patterns)
        if "email" in name_lower:
            return "email_address"
        
        # Phone patterns
        if "phone" in name_lower or "mobile" in name_lower:
            return "phone_number"
        
        # Address patterns
        if "address" in name_lower or "street" in name_lower:
            return "street_address"
        
        # Country patterns
        if "country" in name_lower:
            return "country_name"
        
        # City patterns
        if "city" in name_lower:
            return "city_name"
        
        # Price/amount patterns
        if "price" in name_lower or "amount" in name_lower or "cost" in name_lower:
            return "price_amount"
        
        # Date/time patterns (check all variants)
        if any(pattern in name_lower for pattern in ["date", "time", "timestamp", "created_at", "updated_at"]):
            return "timestamp"
        
        # Name fields - use entity context (check before ID)
        if name_lower in ["name", "title"]:
            return f"{entity_name}_name"
        
        # Type/category fields - use entity context (check before ID)
        if name_lower in ["type", "category", "kind"]:
            return f"{entity_name}_type"
        
        # Family/group fields - use entity context (check before ID)
        if "family" in name_lower:
            return f"{entity_name}_family"
        
        # ID patterns (check last to avoid matching too broadly)
        if name_lower == "id" or name_lower.endswith("_id"):
            return "identifier"
        
        # Default
        return "generic_text"
    
    def _infer_strategy(
        self,
        field_name: str,
        db_type: str,
        semantic_type: str,
        faker_provider: Optional[str]
    ) -> str:
        """Infer generator strategy from field metadata."""
        
        # If faker provider already specified, use it
        if faker_provider:
            return "faker"
        
        # Email addresses
        if semantic_type == "email_address":
            return "faker"
        
        # Phone numbers
        if semantic_type == "phone_number":
            return "faker"
        
        # Addresses
        if semantic_type in ["street_address", "city_name", "country_name"]:
            return "faker"
        
        # Timestamps
        if semantic_type == "timestamp" or db_type in ["date", "datetime"]:
            return "datetime_range"
        
        # IDs
        if semantic_type == "identifier":
            if "_id" in field_name.lower():
                return "uuid"  # Foreign keys
            return "uuid"
        
        # Prices
        if semantic_type == "price_amount":
            return "numeric_distribution"
        
        # Numeric types
        if db_type in ["int", "float"]:
            return "numeric_distribution"
        
        # Domain-specific (_name, _type, _family suffixes suggest custom values)
        if semantic_type.endswith("_name") and semantic_type != "generic_text":
            # Entity-specific names likely need catalogs
            return "value_catalog"
        
        if semantic_type.endswith("_type") or semantic_type.endswith("_family"):
            return "value_catalog"
        
        # Default
        return "generic_text"
