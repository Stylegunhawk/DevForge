"""Semantic type system for domain-agnostic data generation.

Phase 1: LLM confined to classification only, never value generation.
3-Layer architecture: Semantic Understanding → Generator Selection → Value Production
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Literal


class SemanticType(str, Enum):
    """Semantic field types for domain-agnostic generation."""
    
    # Identifiers
    UUID = "uuid"
    NUMERIC_ID = "numeric_id"
    BANK_ACCOUNT_NUMBER = "bank_account_number"
    TRANSACTION_ID = "transaction_id"
    ORDER_CODE = "order_code"
    IDENTIFIER_CODE = "identifier_code"
    USERNAME = "username"
    MAC_ADDRESS = "mac_address"
    IP_V6 = "ip_v6"
    USER_AGENT = "user_agent"
    
    # People
    PERSON_FULL_NAME = "person_full_name"
    PERSON_FIRST_NAME = "person_first_name"
    PERSON_LAST_NAME = "person_last_name"
    EMAIL_ADDRESS = "email_address"
    PHONE_NUMBER = "phone_number"
    JOB_TITLE = "job_title"
    
    # Organizations & Products
    COMPANY_NAME = "company_name"
    PRODUCT_NAME = "product_name"
    INSTITUTION_NAME = "institution_name"
    
    # Domain Entities
    FLOWER_NAME = "flower_name"
    COUNTRY_NAME = "country_name"
    CITY_NAME = "city_name"
    STREET_ADDRESS = "street_address"
    ZIP_CODE = "zip_code"
    GEO_COORDINATE = "geo_coordinate"
    IP_ADDRESS = "ip_address"
    URL = "url"
    
    # Financial
    MONEY_AMOUNT = "money_amount"
    CREDIT_CARD = "credit_card"
    CURRENCY_CODE = "currency_code"
    PERCENTAGE = "percentage"
    
    # Temporal
    DATE = "date"
    TIMESTAMP = "timestamp"
    
    # Boolean / Category
    BOOLEAN_FLAG = "boolean_flag"
    ENUM_VALUE = "enum_value"
    COLOR_NAME = "color_name"
    FILE_EXTENSION = "file_extension"
    MIME_TYPE = "mime_type"
    
    # Fallback
    FREE_TEXT = "free_text"
    UNKNOWN = "unknown"


@dataclass
class SemanticFieldInfo:
    """Complete semantic analysis result for a field."""
    
    entity_name: str
    field_name: str
    raw_type: Optional[str]  # from schema designer: "string", "number", etc.
    semantic_type: str       # SemanticType enum value
    data_type: str          # "string" | "number" | "boolean" | "date" | "timestamp"
    constraints: dict       # {"min": X, "max": Y, "pattern": "...", "enum": [...]}
    source: Literal["lexical", "pattern", "context", "llm", "fallback"]
    confidence: float       # 0.0 - 1.0
    
    def __post_init__(self):
        """Validate confidence range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")


@dataclass
class FieldContext:
    """Context for classifying a field."""
    
    entity_name: str
    field_name: str
    raw_type: Optional[str] = None
    nearby_fields: list[str] = None
    user_prompt: Optional[str] = None
    schema_constraints: Optional[dict] = None
    
    def __post_init__(self):
        if self.nearby_fields is None:
            self.nearby_fields = []
        if self.schema_constraints is None:
            self.schema_constraints = {}
