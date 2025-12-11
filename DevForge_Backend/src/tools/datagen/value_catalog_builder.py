"""Value catalog builder using LLM to generate domain-specific value lists.

Generates catalogs of realistic values for semantic types like:
- flower_name → ["Rose", "Tulip", "Orchid", ...]
- university_name → ["Harvard", "MIT", "Stanford", ...]
- botanical_family → ["Rosaceae", "Liliaceae", ...]

Phase 8.6: Fixes "Daniel Doyle flower" bug by understanding field semantics.
"""

import hashlib
import json
import logging
import re
from typing import Optional

from src.core.model_router import model_router
from src.tools.datagen.semantic_models import (
    SemanticPlan,
    ValueCatalog,
    FieldSemanticInfo,
)

logger = logging.getLogger(__name__)


class CatalogBuilder:
    """LLM-powered value catalog generator.
    
    Generates lists of realistic values for domain-specific fields.
    Uses caching to avoid redundant LLM calls.
    """
    
    def __init__(self, model_task: str = "routing"):
        """Initialize catalog builder.
        
        Args:
            model_task: Task type for model selection
        """
        self.model_task = model_task
        self.timeout = 15  # Faster timeout for catalog generation
        self.max_retries = 2
        self.cache = {}  # In-memory cache: key → ValueCatalog
        self.default_size = 50
        self.min_size = 20
        self.max_size = 200
    
    async def build_catalogs(
        self,
        semantic_plan: SemanticPlan,
        prompt: str,
        catalog_max_values: Optional[int] = None
    ) -> dict[str, ValueCatalog]:
        """Generate value catalogs for fields needing them.
        
        Args:
            semantic_plan: Semantic analysis result
            prompt: User's original prompt (for context)
            catalog_max_values: Override default catalog size
            
        Returns:
            Dictionary mapping catalog_key → ValueCatalog
            
        Only generates catalogs for fields with generator_strategy="value_catalog"
        """
        catalog_size = catalog_max_values or self.default_size
        catalog_size = max(self.min_size, min(self.max_size, catalog_size))
        
        catalogs = {}
        
        # Find all fields needing catalogs
        catalog_fields = semantic_plan.fields_needing_catalogs()
        
        logger.info(f"Building {len(catalog_fields)} value catalogs (size={catalog_size})")
        
        for field_info in catalog_fields:
            # Generate cache key
            cache_key = self._generate_cache_key(field_info, prompt)
            
            # Check cache
            if cache_key in self.cache:
                logger.info(f"Cache hit for {field_info.semantic_type}")
                catalogs[cache_key] = self.cache[cache_key]
                continue
            
            # Generate catalog via LLM
            try:
                catalog = await self._generate_catalog(
                    field_info,
                    prompt,
                    catalog_size
                )
                
                if catalog and len(catalog.values) > 0:
                    # Cache it
                    self.cache[cache_key] = catalog
                    catalogs[cache_key] = catalog
                    logger.info(
                        f"Generated catalog for {field_info.semantic_type}: "
                        f"{len(catalog.values)} values"
                    )
                else:
                    logger.warning(
                        f"Empty catalog for {field_info.semantic_type}, "
                        "will fallback to Faker"
                    )
                    
            except Exception as e:
                logger.warning(
                    f"Failed to generate catalog for {field_info.semantic_type}: {e}. "
                    "Will fallback to Faker."
                )
                # Skip this catalog (generator will fallback)
        
        # Update semantic plan with generated catalogs
        semantic_plan.value_catalogs = catalogs
        
        return catalogs
    
    def _generate_cache_key(
        self,
        field_info: FieldSemanticInfo,
        prompt: str
    ) -> str:
        """Generate cache key for a field.
        
        Key includes: semantic_type, field_name, entity_name, prompt_hash
        """
        # Hash prompt to keep key short
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        
        return f"{field_info.entity_name}.{field_info.field_name}.{prompt_hash}"
    
    async def _generate_catalog(
        self,
        field_info: FieldSemanticInfo,
        prompt: str,
        size: int
    ) -> Optional[ValueCatalog]:
        """Generate catalog via LLM.
        
        Args:
            field_info: Field semantic information
            prompt: User's original prompt
            size: Number of values to generate
            
        Returns:
            ValueCatalog if successful, None if failed
        """
        # Build prompt
        catalog_prompt = self._build_catalog_prompt(field_info, prompt, size)
        
        # Call LLM with retry
        for attempt in range(self.max_retries):
            try:
                # Get model
                model_name = model_router.select_model_by_task(self.model_task)
                chat_model = model_router.get_chat_model(model_name)
                
                logger.info(
                    f"Calling LLM for catalog (model: {model_name}, "
                    f"semantic_type: {field_info.semantic_type}, attempt: {attempt + 1})"
                )
                
                # Invoke LLM
                response = await chat_model.ainvoke([
                    {"role": "user", "content": catalog_prompt}
                ])
                
                # Parse response
                content = response.content if hasattr(response, "content") else str(response)
                values = self._parse_catalog_response(content, size)
                
                if not values:
                    logger.warning(f"Empty catalog from LLM for {field_info.semantic_type}")
                    if attempt < self.max_retries - 1:
                        continue
                    return None
                
                # Create catalog
                catalog = ValueCatalog(
                    key=f"{field_info.entity_name}.{field_info.field_name}",
                    semantic_type=field_info.semantic_type,
                    values=values,
                    source="llm"
                )
                
                return catalog
                
            except TimeoutError:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Catalog LLM timeout, retry {attempt + 1}/{self.max_retries}")
                    continue
                raise
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Catalog LLM error: {e}, retry {attempt + 1}/{self.max_retries}")
                    continue
                raise
        
        return None
    
    def _build_catalog_prompt(
        self,
        field_info: FieldSemanticInfo,
        prompt: str,
        size: int
    ) -> str:
        """Build prompt for catalog generation."""
        
        # Extract constraints/examples if available
        examples_str = ""
        if field_info.constraints and "examples" in field_info.constraints:
            examples = field_info.constraints["examples"]
            examples_str = f"\nExamples: {', '.join(str(e) for e in examples[:3])}"
        
        return f"""Generate {size} realistic values for this field:

User's request: "{prompt}"
Entity: {field_info.entity_name}
Field: {field_info.field_name}
Semantic type: {field_info.semantic_type}
Database type: {field_info.db_type}{examples_str}

CRITICAL REQUIREMENTS:
1. Return ONLY a JSON array of strings
2. Values must be realistic and diverse for the semantic type
3. No duplicates
4. No explanations, no markdown code fences
5. Match the semantic type exactly

WRONG (generic/unrelated): ["John Doe", "Manager LLC", "Technical brewer"]
RIGHT (domain-specific): ["Rose", "Tulip", "Orchid", "Lily", "Sunflower"]

Generate {size} realistic values as JSON array:"""
    
    def _parse_catalog_response(
        self,
        response: str,
        expected_size: int
    ) -> list[str]:
        """Parse LLM response into list of values.
        
        Args:
            response: Raw LLM response
            expected_size: Expected number of values
            
        Returns:
            List of unique string values
        """
        # Strip markdown code fences
        response = re.sub(r'```json\s*|\s*```', '', response).strip()
        response = re.sub(r'```\s*|\s*```', '', response).strip()
        
        try:
            # Parse JSON
            values = json.loads(response)
            
            if not isinstance(values, list):
                raise ValueError(f"Response is not a list: {type(values)}")
            
            # Convert all to strings
            values = [str(v).strip() for v in values if v]
            
            # Deduplicate while preserving order
            seen = set()
            unique_values = []
            for v in values:
                v_lower = v.lower()
                if v_lower not in seen and v:
                    seen.add(v_lower)
                    unique_values.append(v)
            
            if len(unique_values) < expected_size * 0.5:
                logger.warning(
                    f"Catalog has only {len(unique_values)} values "
                    f"(expected ~{expected_size})"
                )
            
            return unique_values
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse catalog response: {e}")
            logger.debug(f"Response was: {response[:200]}")
            return []
