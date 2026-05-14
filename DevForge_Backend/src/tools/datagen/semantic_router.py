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
        constraints: dict = None,
        field_name: str = "",
    ) -> Any:
        """
        Generate a value for a semantic type.

        Args:
            semantic_type: Semantic type (e.g., "person_full_name")
            entity_name: Entity context (for catalog generation)
            constraints: Min/max/enum/pattern constraints
            field_name: Field name (used to make free_text / unknown
                routing field-aware — e.g. ``instrument_name`` → product-like
                value rather than lorem ipsum). Optional; falls back to the
                old behaviour when empty.

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

        # Get generator (registry signature: (entity, constraints, field_name))
        generator_func = self.generators.get(semantic_type, self._fallback_generator)

        # 4. Generate with retry to satisfy min/max/length
        # We try up to 10 times to get a value that fits constraints
        try:
            for _ in range(10):
                value = generator_func(entity_name, constraints, field_name)
                if self._is_valid(value, constraints):
                    return value

            # If we fail to generate a valid value after retries, return it anyway
            return value
        except Exception as e:
            logger.error(f"Error in generation for {semantic_type}: {e}")
            return self._fallback_generator(entity_name, constraints, field_name)

    def _is_valid(self, value: Any, constraints: dict) -> bool:
        """Check if value satisfies constraints (best effort check for retry loop)."""
        # Min/Max for numbers
        if isinstance(value, (int, float)):
             if "min" in constraints and constraints["min"] is not None and value < constraints["min"]: return False
             if "max" in constraints and constraints["max"] is not None and value > constraints["max"]: return False
             
        # Length for strings check
        if isinstance(value, str):
            min_len = constraints.get("min_length")
            if min_len is not None and len(value) < int(min_len): return False
            
            max_len = constraints.get("max_length")
            if max_len is not None and len(value) > int(max_len): return False
            
        return True
    
    def _build_generator_registry(self) -> dict[str, Callable]:
        """Build mapping of semantic types to generator functions.

        Every entry is a callable ``(entity_name, constraints, field_name)``.
        Only ``free_text``, ``enum_value`` and ``unknown`` use ``field_name``
        today; the rest accept it for signature uniformity.
        """
        return {
            # People
            "person_full_name": lambda e, c, f: self.faker.name(),
            "person_first_name": lambda e, c, f: self.faker.first_name(),
            "person_last_name": lambda e, c, f: self.faker.last_name(),
            "email_address": lambda e, c, f: self.faker.email(),
            "phone_number": lambda e, c, f: self.faker.phone_number(),
            "job_title": lambda e, c, f: self.faker.job(),
            "username": lambda e, c, f: self.faker.user_name(),

            # Organizations
            "company_name": lambda e, c, f: self.faker.company(),
            "product_name": lambda e, c, f: self._catalog_or_faker(
                "product_name", e, lambda: self.faker.catch_phrase()
            ),
            "institution_name": lambda e, c, f: self._catalog_or_faker(
                "institution_name", e, lambda: self.faker.company() + " University"
            ),
            "flower_name": lambda e, c, f: self._catalog_or_faker(
                "flower_name", e, lambda: self.faker.word().capitalize()
            ),

            # Geographic
            "country_name": lambda e, c, f: self.faker.country(),
            "city_name": lambda e, c, f: self.faker.city(),
            "street_address": lambda e, c, f: self.faker.street_address(),
            "zip_code": lambda e, c, f: self.faker.zipcode(),
            "geo_coordinate": lambda e, c, f: f"{self.faker.latitude()}, {self.faker.longitude()}",

            # Financial
            "bank_account_number": lambda e, c, f: self._generate_account_number(c),
            "transaction_id": lambda e, c, f: self._generate_transaction_id(c),
            "order_code": lambda e, c, f: self._generate_order_code(c),
            "identifier_code": lambda e, c, f: self.faker.bothify("???-###"),
            "money_amount": lambda e, c, f: self._generate_money(c),
            "percentage": lambda e, c, f: round(random.uniform(
                float(c.get("min")) if c.get("min") is not None else 0.0,
                float(c.get("max")) if c.get("max") is not None else 100.0
            ), 1),
            "credit_card": lambda e, c, f: self.faker.credit_card_number(),
            "currency_code": lambda e, c, f: self.faker.currency_code(),

            # Identifiers
            "uuid": lambda e, c, f: str(uuid.uuid4()),
            "numeric_id": lambda e, c, f: random.randint(
                max(1, int(c.get("min")) if c.get("min") is not None else 1),
                max(int(c.get("min")) + 1 if c.get("min") is not None else 2,
                    int(c.get("max")) if c.get("max") is not None else 1000000)
            ),

            # Temporal - Strict Min/Max Enforcement
            "date": lambda e, c, f: self._generate_date(c),
            "timestamp": lambda e, c, f: self._generate_timestamp(c),

            # Boolean
            "boolean_flag": lambda e, c, f: random.choice([True, False]),

            # Enum (uses _generate_enum which falls back safely if no values)
            "enum_value": lambda e, c, f: self._generate_enum(c, e, f),

            # Tech/Web
            "ip_address": lambda e, c, f: self.faker.ipv4(),
            "ip_v6": lambda e, c, f: self.faker.ipv6(),
            "mac_address": lambda e, c, f: self.faker.mac_address(),
            "user_agent": lambda e, c, f: self.faker.user_agent(),
            "url": lambda e, c, f: self.faker.url(),
            "color_name": lambda e, c, f: self.faker.color_name(),
            "file_extension": lambda e, c, f: self.faker.file_extension(),
            "mime_type": lambda e, c, f: self.faker.mime_type(),

            # Free text — field-name-aware routing (avoid lorem ipsum)
            "free_text": lambda e, c, f: self._smart_free_text(e, f, c),

            # Fallback for unrecognized semantic types
            "unknown": lambda e, c, f: self._smart_free_text(e, f, c),
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
        raw_len = constraints.get("length")
        length = int(raw_len) if raw_len is not None else random.randint(10, 12)
        return ''.join([str(random.randint(0, 9)) for _ in range(length)])
    
    def _generate_transaction_id(self, constraints: dict) -> str:
        """Generate transaction ID."""
        raw_prefix = constraints.get("prefix")
        prefix = str(raw_prefix) if raw_prefix is not None else "TXN"
        return f"{prefix}{random.randint(100000000, 999999999)}"
    
    def _generate_order_code(self, constraints: dict) -> str:
        """Generate order code."""
        raw_prefix = constraints.get("prefix")
        prefix = str(raw_prefix) if raw_prefix is not None else "ORD"
        return f"{prefix}-{random.randint(10000, 99999)}"
    
    def _generate_money(self, constraints: dict) -> float:
        """Generate money amount respecting constraints."""
        min_val = float(constraints.get("min")) if constraints.get("min") is not None else 0.0
        max_val = float(constraints.get("max")) if constraints.get("max") is not None else 10000.0
        if min_val > max_val: max_val = min_val + 100.0
        value = random.uniform(min_val, max_val)
        return round(value, 2)
    
    # Field-name suffixes / substrings that hint at the right Faker provider
    # when the classifier returns the loose ``free_text`` semantic type.
    _NAME_FIELD_HINTS = ("_name", "name_of", "title", "label", "product", "model")
    _NUMERIC_FIELD_HINTS = (
        # Cardinality / quantity
        "_count", "_qty", "quantity", "_num", "_total",
        # Time durations / cadences
        "_days", "_hours", "_minutes", "_seconds", "_weeks", "_months",
        "_year", "_age", "interval", "duration", "ttl",
        # Sizes / physical measurements (the square_feet / sqft case)
        "_size", "_length", "_width", "_height", "_depth", "_weight",
        "_feet", "_ft", "_sqft", "square_feet", "_inches", "_in",
        "_meters", "_m2", "_m3", "_km",
        # Engineering units commonly seen in domain prompts
        "_cc", "_mm", "_kg", "_ml", "_lb", "_oz", "_l", "_hp",
        "_voltage", "_watts", "_amps",
        # Rates / percentages
        "_percent", "_pct", "_rate", "_ratio",
        # Money / price (numeric but money_amount usually handles these — kept
        # here as a safety net for novel suffixes the classifier may miss)
        "_price", "_cost", "_fee", "_balance",
    )
    _DESCRIPTION_FIELD_HINTS = ("description", "comment", "note", "notes",
                                "details", "summary", "bio", "biography",
                                "remarks", "feedback")

    def _smart_free_text(self, entity_name: str, field_name: str,
                         constraints: dict) -> Any:
        """Field-aware free-text generation.

        Avoids the v0.8 "Agent every development say." problem by routing
        the loose ``free_text`` / ``unknown`` semantic types based on the
        field name shape instead of always returning ``faker.sentence()``
        (lorem ipsum).

        Rules:
            * ``_name`` / title-like field  → ``faker.catch_phrase()``
              (short, product-flavoured phrase)
            * ``description`` / comment    → short sentence (6 words)
            * numeric-suffix field (``_days``, ``_count``, ``_cc``,
              ``_percent`` …)            → random int respecting min/max
              (defaults to 1..1000)
            * anything else                → ``faker.word()`` (single noun)

        Field name matching is lowercase substring; empty field_name falls
        back to ``faker.word()`` so the legacy code path is unchanged.
        """
        fn = (field_name or "").lower()
        if not fn:
            return self.faker.word()

        if any(h in fn for h in self._NAME_FIELD_HINTS):
            return self.faker.catch_phrase()

        if any(h in fn for h in self._DESCRIPTION_FIELD_HINTS):
            return self.faker.sentence(nb_words=6)

        if any(h in fn for h in self._NUMERIC_FIELD_HINTS):
            lo = int(constraints.get("min")) if constraints.get("min") is not None else 1
            hi = int(constraints.get("max")) if constraints.get("max") is not None else 1000
            if hi <= lo:
                hi = lo + 1
            return random.randint(lo, hi)

        return self.faker.word()

    def _generate_enum(self, constraints: dict,
                       entity_name: str = "",
                       field_name: str = "") -> Any:
        """Generate enum value from constraints or fall back safely.

        v0.8 fabricated ``{"active", "inactive", "pending", "completed"}`` whenever
        the LLM classifier picked ``enum_value`` without supplying any actual enum
        choices. That misled callers — the genre field in the doc's stress test
        ended up with status-like values. Fall back to ``_smart_free_text`` so the
        field at least looks plausible, and log a warning so the upstream miss is
        visible.
        """
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])
        logger.warning(
            "Classifier picked enum_value for %s.%s but no enum values were supplied; "
            "falling back to smart free-text routing.",
            entity_name or "<entity>",
            field_name or "<field>",
        )
        return self._smart_free_text(entity_name, field_name, constraints)

    def _fallback_generator(self, entity_name: str, constraints: dict,
                            field_name: str = "") -> str:
        """Fallback generator for unknown types."""
        return self._smart_free_text(entity_name, field_name, constraints)
    
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
            
            # Use Faker's regex_ify if available, otherwise fallback to bothify
            try:
                # Some versions of Faker place regex_ify differently or it might be missing from proxy
                if hasattr(self.faker, 'regex_ify'):
                    return self.faker.regex_ify(pattern)
                # Last resort: convert major regex tokens to bothify tokens
                # Very basic but prevents crash
                simple_pattern = pattern.replace('\\d', '#').replace('.', '?')
                return self.faker.bothify(simple_pattern)
            except Exception as fe:
                logger.error(f"Faker fallback generation failed for '{pattern}': {fe}")
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
        if "min" in constraints and constraints["min"] is not None:
            try:
                # Handle YYYY-MM-DD
                min_date = date.fromisoformat(str(constraints["min"]))
            except ValueError:
                pass
        
        if "max" in constraints and constraints["max"] is not None:
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
        
        if "min" in constraints and constraints["min"] is not None:
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
        
        if "max" in constraints and constraints["max"] is not None:
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
