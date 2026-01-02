"""Routes semantic types to appropriate value generators.

Phase 1: Value generation is always done by Faker/catalogs, never by LLM.
"""

from typing import Any, Callable
from faker import Faker
import random
import uuid
import logging

logger = logging.getLogger(__name__)


class SemanticRouter:
    """Maps semantic types to concrete value generators."""
    
    def __init__(self, catalog_factory=None):
        self.faker = Faker()
        self.catalog_factory = catalog_factory
        
        # Generator registry
        self.generators = self._build_generator_registry()
    
    def generate_value(
        self, 
        semantic_type: str,
        entity_name: str = "",
        constraints: dict = None
    ) -> Any:
        """
        Generate a value for a semantic type.
        
        Args:
            semantic_type: Semantic type (e.g., "person_full_name")
            entity_name: Entity context (for catalog generation)
            constraints: Min/max/enum/pattern constraints
            
        Returns:
            Generated value (never LLM text!)
        """
        constraints = constraints or {}
        
        # Check for enum override
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])
        
        # Check for pattern override
        if "pattern" in constraints and constraints["pattern"]:
            return self._generate_pattern(constraints["pattern"])
        
        # Get generator
        generator_func = self.generators.get(semantic_type, self._fallback_generator)
        
        # Generate
        return generator_func(entity_name, constraints)
    
    def _build_generator_registry(self) -> dict[str, Callable]:
        """Build mapping of semantic types to generator functions."""
        return {
            # People
            "person_full_name": lambda e, c: self.faker.name(),
            "person_first_name": lambda e, c: self.faker.first_name(),
            "person_last_name": lambda e, c: self.faker.last_name(),
            "email_address": lambda e, c: self.faker.email(),
            "phone_number": lambda e, c: self.faker.phone_number(),
            "job_title": lambda e, c: self.faker.job(),
            "username": lambda e, c: self.faker.user_name(),
            
            # Organizations
            "company_name": lambda e, c: self.faker.company(),
            "product_name": lambda e, c: self._catalog_or_faker(
                "product_name", e, lambda: self.faker.catch_phrase()
            ),
            "institution_name": lambda e, c: self._catalog_or_faker(
                "institution_name", e, lambda: self.faker.company() + " University"
            ),
            "flower_name": lambda e, c: self._catalog_or_faker(
                "flower_name", e, lambda: self.faker.word().capitalize()
            ),
            
            # Geographic
            "country_name": lambda e, c: self.faker.country(),
            "city_name": lambda e, c: self.faker.city(),
            "street_address": lambda e, c: self.faker.street_address(),
            "zip_code": lambda e, c: self.faker.zipcode(),
            "geo_coordinate": lambda e, c: f"{self.faker.latitude()}, {self.faker.longitude()}",
            
            # Financial
            "bank_account_number": lambda e, c: self._generate_account_number(c),
            "transaction_id": lambda e, c: self._generate_transaction_id(c),
            "order_code": lambda e, c: self.faker.bothify("ORD-####-????"),
            "identifier_code": lambda e, c: self.faker.bothify("???-###"),
            "money_amount": lambda e, c: round(random.uniform(c.get("min", 10), c.get("max", 1000)), 2),
            "percentage": lambda e, c: round(random.uniform(c.get("min", 0), c.get("max", 100)), 1),
            "credit_card": lambda e, c: self.faker.credit_card_number(),
            "currency_code": lambda e, c: self.faker.currency_code(),
            
            # Identifiers
            "uuid": lambda e, c: str(uuid.uuid4()),
            "numeric_id": lambda e, c: random.randint(c.get("min", 1), c.get("max", 1000000)),
            
            # Temporal
            "date": lambda e, c: self.faker.date_between(start_date="-10y", end_date="today").isoformat(),
            "timestamp": lambda e, c: self.faker.date_time_between(start_date="-1y", end_date="now").isoformat(),
            
            # Boolean
            "boolean_flag": lambda e, c: random.choice([True, False]),
            
            # Enum
            "enum_value": lambda e, c: self._generate_enum(c),
            
            # Tech/Web
            "ip_address": lambda e, c: self.faker.ipv4(),
            "ip_v6": lambda e, c: self.faker.ipv6(),
            "mac_address": lambda e, c: self.faker.mac_address(),
            "user_agent": lambda e, c: self.faker.user_agent(),
            "url": lambda e, c: self.faker.url(),
            "color_name": lambda e, c: self.faker.color_name(),
            "file_extension": lambda e, c: self.faker.file_extension(),
            "mime_type": lambda e, c: self.faker.mime_type(),
            
            # Free text (Faker sentence, NOT LLM!)
            "free_text": lambda e, c: self.faker.sentence(),
            
            # Fallback
            "unknown": lambda e, c: self.faker.word(),
        }
    
    def _catalog_or_faker(self, semantic_type: str, entity_name: str, faker_fallback: Callable) -> str:
        """Get value from catalog if available, else use Faker."""
        if self.catalog_factory:
            try:
                catalog = self.catalog_factory.get_catalog(
                    semantic_type, 
                    entity_name,
                    domain="general"
                )
                if catalog:
                    return random.choice(catalog)
            except Exception as e:
                logger.warning(f"Catalog fetch failed for {semantic_type}: {e}")
        
        return faker_fallback()
    
    def _generate_account_number(self, constraints: dict) -> str:
        """Generate bank account number."""
        length = constraints.get("length", random.randint(10, 12))
        return ''.join([str(random.randint(0, 9)) for _ in range(length)])
    
    def _generate_transaction_id(self, constraints: dict) -> str:
        """Generate transaction ID."""
        prefix = constraints.get("prefix", "TXN")
        return f"{prefix}{random.randint(100000000, 999999999)}"
    
    def _generate_order_code(self, constraints: dict) -> str:
        """Generate order code."""
        prefix = constraints.get("prefix", "ORD")
        return f"{prefix}-{random.randint(10000, 99999)}"
    
    def _generate_money(self, constraints: dict) -> float:
        """Generate money amount respecting constraints."""
        min_val = constraints.get("min", 0)
        max_val = constraints.get("max", 10000)
        value = random.uniform(min_val, max_val)
        return round(value, 2)
    
    def _generate_enum(self, constraints: dict) -> str:
        """Generate enum value from constraints or default."""
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])
        # Default status values
        return random.choice(["active", "inactive", "pending", "completed"])
    
    def _fallback_generator(self, entity_name: str, constraints: dict) -> str:
        """Fallback generator for unknown types."""
        logger.debug(f"Using fallback generator for entity: {entity_name}")
        return self.faker.word()
    
    def _generate_pattern(self, pattern: str) -> str:
        """Generate value from regex pattern."""
        try:
            import rstr
            return rstr.xeger(pattern)
        except ImportError:
            logger.warning("rstr not installed, falling back to simple pattern generation")
            return self.faker.bothify("???-###")
        except Exception as e:
            logger.warning(f"Pattern generation failed for '{pattern}': {e}")
            return self.faker.bothify("???-###")
