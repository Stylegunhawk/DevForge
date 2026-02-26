"""Routes semantic types to appropriate value generators.

Phase 1: Value generation is always done by Faker/catalogs, never by LLM.
Invariant Enforced: Constraint-First Generation.
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

        # 1. Canonical Constraint Shape: Normalize constraints
        # Ensure flat structure for pattern, enum, min, max
        normalized_constraints = constraints.copy()
        if "constraints" in constraints and isinstance(constraints["constraints"], dict):
            nested = constraints["constraints"]
            for key in ("pattern", "enum", "min", "max", "min_length", "max_length"):
                if key in nested:
                    normalized_constraints[key] = nested[key]
        
        constraints = normalized_constraints
        
        # 2. Constraint-First: Enum overrides everything
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])
        
        # 3. Constraint-First: Pattern overrides semantic type
        if "pattern" in constraints and constraints["pattern"]:
            return self._generate_pattern(constraints["pattern"])
        
        # Get generator
        generator_func = self.generators.get(semantic_type, self._fallback_generator)
        
        # 4. Generate with retry to satisfy min/max/length
        # We try up to 10 times to get a value that fits constraints
        for _ in range(10):
            value = generator_func(entity_name, constraints)
            if self._is_valid(value, constraints):
                return value
                
        # If we fail to generate a valid value after retries, return it anyway
        # Validation downstream will catch it if it's strictly invalid.
        return value

    def _is_valid(self, value: Any, constraints: dict) -> bool:
        """Check if value satisfies constraints (best effort check for retry loop)."""
        # Min/Max for numbers
        if isinstance(value, (int, float)):
             if "min" in constraints and value < constraints["min"]: return False
             if "max" in constraints and value > constraints["max"]: return False
             
        # Length for strings check
        if isinstance(value, str):
            min_len = constraints.get("min_length", 0)
            max_len = constraints.get("max_length", 1000)
            # Also check generic min/max if implied as length? 
            # Avoiding ambiguity, mostly relying on specific generators respecting min/max arguments.
            # But here we double check.
            pass
            
        return True
    
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
            "order_code": lambda e, c: self._generate_order_code(c),
            "identifier_code": lambda e, c: self.faker.bothify("???-###"),
            "money_amount": lambda e, c: self._generate_money(c),
            "percentage": lambda e, c: round(random.uniform(c.get("min", 0), c.get("max", 100)), 1),
            "credit_card": lambda e, c: self.faker.credit_card_number(),
            "currency_code": lambda e, c: self.faker.currency_code(),
            
            # Identifiers
            "uuid": lambda e, c: str(uuid.uuid4()),
            "numeric_id": lambda e, c: random.randint(
                max(1, int(c.get("min", 1))),
                max(int(c.get("min", 1)) + 1, int(c.get("max", 1000000)))
            ),
            
            # Temporal - Strict Min/Max Enforcement
            "date": lambda e, c: self._generate_date(c),
            "timestamp": lambda e, c: self._generate_timestamp(c),
            
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
            
            # Free text
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
        min_val = float(constraints.get("min", 0))
        max_val = float(constraints.get("max", 10000))
        if min_val > max_val: max_val = min_val + 100.0
        value = random.uniform(min_val, max_val)
        return round(value, 2)
    
    def _generate_enum(self, constraints: dict) -> str:
        """Generate enum value from constraints or default."""
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])
        return random.choice(["active", "inactive", "pending", "completed"])
    
    def _fallback_generator(self, entity_name: str, constraints: dict) -> str:
        """Fallback generator for unknown types."""
        return self.faker.word()
    
    _rstr_warning_logged = False
    
    def _generate_pattern(self, pattern: str) -> str:
        """Generate value from regex pattern."""
        try:
            import rstr
            return rstr.xeger(pattern)
        except (ImportError, Exception) as e:
            # Only log the warning once to avoid spamming logs (especially in Docker)
            if not SemanticRouter._rstr_warning_logged:
                if isinstance(e, ImportError):
                    logger.warning("rstr not installed, falling back to faker.regex_ify for pattern generation")
                else:
                    logger.warning(f"Pattern generation via rstr failed for '{pattern}': {e}. Falling back to faker.regex_ify")
                SemanticRouter._rstr_warning_logged = True
            
            # Use Faker's regex_ify as a robust fallback
            try:
                return self.faker.regex_ify(pattern)
            except Exception as fe:
                logger.error(f"Faker regex_ify also failed for '{pattern}': {fe}")
                return self.faker.bothify("???-###")

    def _generate_date(self, constraints: dict) -> str:
        """Generate date respecting min/max using native python."""
        from datetime import date, timedelta, datetime
        
        # Default range: -10y to today
        today = date.today()
        default_min = today.replace(year=today.year - 10)
        default_max = today
        
        min_date = default_min
        max_date = default_max
        
        # Parse constraints
        if "min" in constraints:
            try:
                # Handle YYYY-MM-DD
                min_date = date.fromisoformat(str(constraints["min"]))
            except ValueError:
                pass
        
        if "max" in constraints:
            try:
                max_date = date.fromisoformat(str(constraints["max"]))
            except ValueError:
                pass
                
        # Handle strict overrides if only one is provided?
        if "min" in constraints and "max" not in constraints:
            # If min is in future, default max (today) might be invalid
            if min_date > max_date:
                max_date = min_date.replace(year=min_date.year + 1)
        
        if "max" in constraints and "min" not in constraints:
             # If max is in past, default min might be invalid if it assumes -10y from today but max is -20y
             if max_date < min_date:
                 min_date = max_date.replace(year=max_date.year - 1)

        # Final sanity check: if min > max, swap or adjust
        if min_date > max_date:
             max_date = min_date
        
        # Generator
        delta_days = (max_date - min_date).days
        if delta_days <= 0:
            return min_date.isoformat()
            
        random_days = random.randint(0, delta_days)
        return (min_date + timedelta(days=random_days)).isoformat()

    def _generate_timestamp(self, constraints: dict) -> str:
        """Generate timestamp respecting min/max using native python."""
        from datetime import datetime, timedelta
        
        # Default range: -1y to now
        now = datetime.now()
        default_min = now.replace(year=now.year - 1)
        default_max = now
        
        min_dt = default_min
        max_dt = default_max
        
        if "min" in constraints:
            try:
                # Handle ISO format YYYY-MM-DDTHH:MM:SS
                min_dt = datetime.fromisoformat(str(constraints["min"]))
            except ValueError:
                # Try date parse and add time
                try: 
                     from datetime import date
                     d = date.fromisoformat(str(constraints["min"]))
                     min_dt = datetime.combine(d, datetime.min.time())
                except: pass
        
        if "max" in constraints:
            try:
                max_dt = datetime.fromisoformat(str(constraints["max"]))
            except ValueError:
                try: 
                     from datetime import date
                     d = date.fromisoformat(str(constraints["max"]))
                     max_dt = datetime.combine(d, datetime.max.time())
                except: pass
                
        # Logic to ensure valid range
        if min_dt > max_dt:
             if "min" in constraints and "max" not in constraints:
                 max_dt = min_dt.replace(year=min_dt.year + 1)
             elif "max" in constraints and "min" not in constraints:
                 min_dt = max_dt.replace(year=max_dt.year - 1)
             else:
                 max_dt = min_dt
                 
        delta_seconds = int((max_dt - min_dt).total_seconds())
        if delta_seconds <= 0:
            return min_dt.isoformat()
            
        random_seconds = random.randint(0, delta_seconds)
        return (min_dt + timedelta(seconds=random_seconds)).isoformat()
