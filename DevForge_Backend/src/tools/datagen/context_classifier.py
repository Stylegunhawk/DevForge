"""Context-based field classification using entity and field relationships."""

from typing import Optional
from .semantic_types import SemanticFieldInfo, FieldContext


class ContextClassifier:
    """Classifies fields based on entity name and field context."""
    
    # Entity hints: normalized entity term → domain + preferred type for "name" field
    ENTITY_HINTS = {
        "flower": {"domain": "botanical", "name_type": "flower_name"},
        "plant": {"domain": "botanical", "name_type": "flower_name"},
        "university": {"domain": "education", "name_type": "institution_name"},
        "college": {"domain": "education", "name_type": "institution_name"},
        "school": {"domain": "education", "name_type": "institution_name"},
        "institution": {"domain": "education", "name_type": "institution_name"},
        "customer": {"domain": "business", "name_type": "person_full_name"},
        "user": {"domain": "business", "name_type": "person_full_name", "title_type": "job_title"},
        "person": {"domain": "business", "name_type": "person_full_name", "title_type": "job_title"},
        "employee": {"domain": "business", "name_type": "person_full_name", "title_type": "job_title"},
        "account": {"domain": "banking", "name_type": "bank_account_number", "id_type": "bank_account_number"},
        "transaction": {"domain": "banking", "id_type": "transaction_id"},
        "payment": {"domain": "banking", "id_type": "transaction_id"},
        "product": {"domain": "commerce", "name_type": "product_name", "id_type": "identifier_code"},
        "item": {"domain": "commerce", "name_type": "product_name", "id_type": "identifier_code"},
        "company": {"domain": "business", "name_type": "company_name"},
        "organization": {"domain": "business", "name_type": "company_name"},
        "order": {"domain": "commerce", "id_type": "order_code"},
        "invoice": {"domain": "commerce", "id_type": "order_code"},
        
        # Media
        "book": {"domain": "media", "name_type": "product_name", "title_type": "product_name"},
        "movie": {"domain": "media", "name_type": "product_name", "title_type": "product_name"},
        "song": {"domain": "media", "name_type": "product_name", "title_type": "product_name"},
        "article": {"domain": "media", "name_type": "product_name", "title_type": "product_name"},
        
        # Location
        "city": {"domain": "geo", "name_type": "city_name"},
        "location": {"domain": "geo", "name_type": "city_name"},
        "venue": {"domain": "geo", "name_type": "city_name"},
        "station": {"domain": "geo", "name_type": "city_name"},
    }
    
    def classify(self, ctx: FieldContext) -> Optional[SemanticFieldInfo]:
        """
        Classify field based on entity context.
        
        Focuses on "name" fields that vary by entity type:
        - flowers.name → flower_name
        - universities.name → institution_name
        - customers.name → person_full_name
        """

        # Check for "name" fields
        if ctx.field_name.lower() in ["name", "title"]:
            return self._classify_name_field(ctx)
            
        # Check for ID fields
        if ctx.field_name.lower() in ["id", "code", "number"] or ctx.field_name.lower().endswith("_id"):
            return self._classify_id_field(ctx)
            
        return None

    def _classify_name_field(self, ctx: FieldContext) -> Optional[SemanticFieldInfo]:
        """Classify name/title fields."""
        
        # Extract entity hint
        entity_hint = self._get_entity_hint(ctx.entity_name)
        if not entity_hint:
            return None
            
        # Determine semantic type based on field name (name vs title)
        if ctx.field_name.lower() == "title" and "title_type" in entity_hint:
            semantic_type = entity_hint["title_type"]
        elif "name_type" in entity_hint:
            semantic_type = entity_hint["name_type"]
        else:
            return None
        
        return SemanticFieldInfo(
            entity_name=ctx.entity_name,
            field_name=ctx.field_name,
            raw_type=ctx.raw_type,
            semantic_type=semantic_type,
            data_type="string",
            constraints=ctx.schema_constraints or {},
            source="context",
            confidence=0.80  # Medium-high confidence
        )
        
    def _classify_id_field(self, ctx: FieldContext) -> Optional[SemanticFieldInfo]:
        """Classify ID/code fields."""
        entity_hint = self._get_entity_hint(ctx.entity_name)
        if not entity_hint or "id_type" not in entity_hint:
            return None
            
        return SemanticFieldInfo(
            entity_name=ctx.entity_name,
            field_name=ctx.field_name,
            raw_type=ctx.raw_type,
            semantic_type=entity_hint["id_type"],
            data_type="string",
            constraints=ctx.schema_constraints or {},
            source="context",
            confidence=0.80
        )
    
    def _get_entity_hint(self, entity_name: str) -> Optional[dict]:
        """Extract entity hint from entity name."""
        normalized = entity_name.lower()
        
        # Direct match
        if normalized in self.ENTITY_HINTS:
            return self.ENTITY_HINTS[normalized]
        
        # Try singular form (remove trailing 's')
        if normalized.endswith('ies'):
            # universities → university
            singular = normalized[:-3] + 'y'
            if singular in self.ENTITY_HINTS:
                return self.ENTITY_HINTS[singular]
        elif normalized.endswith('s'):
            singular = normalized[:-1]
            if singular in self.ENTITY_HINTS:
                return self.ENTITY_HINTS[singular]
        
        # Try to find substring match
        for key, hint in self.ENTITY_HINTS.items():
            if key in normalized or normalized in key:
                return hint
        
        return None
