"""Field value generator using semantic-aware strategies.

Routes field value generation based on semantic type:
- value_catalog: Sample from LLM-generated catalogs
- faker: Use Faker providers
- numeric_distribution: Use statistical distributions
- datetime_range: Use temporal patterns
- uuid/mongo_object_id: Generate IDs
- generic_text: Fallback

Phase 8.6: Ensures "flower.name" generates flower names, not person names.
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from faker import Faker

from src.tools.datagen.semantic_models import SemanticPlan, FieldSemanticInfo
from src.tools.datagen.simple_distributions import (
    normal,
    lognormal,
    pareto,
    categorical,
    random_timestamps,
    business_hours_timestamps,
)

fake = Faker()


class FieldValueGenerator:
    """Generate field values using semantic-aware strategies.
    
    Routes generation based on field semantic information:
    - Understands context (flower.name vs user.name)
    - Samples from domain-specific catalogs
    - Falls back gracefully when catalogs unavailable
    """
    
    def __init__(self, semantic_plan: SemanticPlan):
        """Initialize field value generator.
        
        Args:
            semantic_plan: Semantic analysis with field info and value catalogs
        """
        self.semantic_plan = semantic_plan
        self.catalogs = semantic_plan.value_catalogs
    
    def get_generator(
        self,
        entity_name: str,
        field_name: str
    ) -> Callable[[], Any]:
        """Get generator function for a specific field.
        
        Args:
            entity_name: Name of the entity
            field_name: Name of the field
            
        Returns:
            Callable that generates one value when called
            
        Strategy priority:
            1. Native generators (uuid, ObjectId)
            2. Value catalogs (domain-specific)
            3. Faker providers
            4. Distributions (numeric, datetime)
            5. Generic fallback
        """
        # Find field semantic info
        field_info = self.semantic_plan.get_field_info(entity_name, field_name)
        
        if not field_info:
            # Unknown field → generic fallback
            return lambda: fake.text(max_nb_chars=50)
        
        # Route by strategy
        strategy = field_info.generator_strategy
        
        if strategy == "uuid":
            return self._get_uuid_generator()
        
        elif strategy == "mongo_object_id":
            return self._get_object_id_generator()
        
        elif strategy == "value_catalog":
            return self._get_catalog_generator(field_info)
        
        elif strategy == "faker":
            return self._get_faker_generator(field_info)
        
        elif strategy == "numeric_distribution":
            return self._get_numeric_generator(field_info)
        
        elif strategy == "datetime_range":
            return self._get_datetime_generator(field_info)
        
        else:  # "generic_text"
            return self._get_generic_generator(field_info)
    
    def _get_uuid_generator(self) -> Callable:
        """Get UUID generator."""
        return lambda: str(uuid.uuid4())
    
    def _get_object_id_generator(self) -> Callable:
        """Get MongoDB ObjectId generator."""
        try:
            from bson import ObjectId
            return lambda: str(ObjectId())
        except ImportError:
            # Fallback to UUID if bson not available
            return lambda: str(uuid.uuid4())
    
    def _get_catalog_generator(self, field_info: FieldSemanticInfo) -> Callable:
        """Get catalog-based generator.
        
        Samples from LLM-generated value catalog.
        Falls back to Faker if catalog not available.
        """
        # Try to find catalog
        catalog = self.semantic_plan.get_catalog(
            field_info.entity_name,
            field_info.field_name
        )
        
        if catalog and len(catalog.values) > 0:
            # Sample from catalog
            return lambda: random.choice(catalog.values)
        
        # No catalog found → fallback to Faker
        return self._get_faker_generator(field_info)
    
    def _get_faker_generator(self, field_info: FieldSemanticInfo) -> Callable:
        """Get Faker-based generator.
        
        Maps semantic types to appropriate Faker providers.
        """
        semantic_type = field_info.semantic_type
        
        # Map semantic types to Faker providers
        faker_map = {
            "email_address": fake.email,
            "phone_number": fake.phone_number,
            "person_name": fake.name,
            "company_name": fake.company,
            "street_address": fake.street_address,
            "city_name": fake.city,
            "country_name": fake.country,
            "url": fake.url,
            "ipv4_address": fake.ipv4,
            "user_name": fake.user_name,
            "password": fake.password,
            "job_title": fake.job,
        }
        
        if semantic_type in faker_map:
            return faker_map[semantic_type]
        
        # Fallback to generic text
        return lambda: fake.text(max_nb_chars=50)
    
    def _get_numeric_generator(self, field_info: FieldSemanticInfo) -> Callable:
        """Get numeric distribution generator.
        
        Chooses distribution based on semantic type.
        """
        constraints = field_info.constraints or {}
        semantic_type = field_info.semantic_type
        db_type = field_info.db_type
        
        # Choose distribution based on semantic type
        if "price" in semantic_type or "amount" in semantic_type or "cost" in semantic_type:
            # Prices: lognormal (most low, few high)
            mean = constraints.get("mean", 3.5)
            std = constraints.get("std", 1.2)
            return lambda: round(lognormal(mean=mean, std=std, n=1)[0], 2)
        
        elif "count" in semantic_type or "quantity" in semantic_type:
            # Counts: pareto (power law)
            alpha = constraints.get("alpha", 1.5)
            scale = constraints.get("scale", 10)
            return lambda: int(pareto(alpha=alpha, n=1, scale=scale)[0])
        
        elif "rating" in semantic_type or "score" in semantic_type:
            # Ratings: categorical
            min_val = constraints.get("min", 1)
            max_val = constraints.get("max", 5)
            values = list(range(min_val, max_val + 1))
            weights = [1.0] * len(values)  # Uniform by default
            return lambda: categorical(values, weights, n=1)[0]
        
        elif "year" in semantic_type:
            # Years: uniform in range
            min_year = constraints.get("min", 1900)
            max_year = constraints.get("max", 2025)
            return lambda: random.randint(min_year, max_year)
        
        elif db_type == "int":
            # Generic int: normal distribution
            mean = constraints.get("mean", 100)
            std = constraints.get("std", 15)
            return lambda: int(normal(mean=mean, std=std, n=1)[0])
        
        elif db_type == "float":
            # Generic float: normal distribution
            mean = constraints.get("mean", 100.0)
            std = constraints.get("std", 15.0)
            return lambda: round(normal(mean=mean, std=std, n=1)[0], 2)
        
        else:
            # Fallback
            return lambda: random.random() * 100
    
    def _get_datetime_generator(self, field_info: FieldSemanticInfo) -> Callable:
        """Get datetime generator.
        
        Uses temporal patterns based on constraints.
        """
        constraints = field_info.constraints or {}
        pattern = constraints.get("pattern", "random")
        
        # Default range: last year to now
        start = datetime.now() - timedelta(days=365)
        end = datetime.now()
        
        if pattern == "business_hours":
            # Business hours timestamps
            timestamps = business_hours_timestamps(start, end, n=1000)
            return lambda: random.choice(timestamps).isoformat()
        
        else:  # "random"
            # Random timestamps
            timestamps = random_timestamps(start, end, n=1000)
            return lambda: random.choice(timestamps).isoformat()
    
    def _get_generic_generator(self, field_info: FieldSemanticInfo) -> Callable:
        """Generic fallback generator.
        
        Uses db_type to determine basic generation strategy.
        """
        db_type = field_info.db_type
        
        if db_type == "int":
            return lambda: random.randint(1, 1000)
        
        elif db_type == "float":
            return lambda: round(random.uniform(1.0, 100.0), 2)
        
        elif db_type == "boolean":
            return lambda: random.choice([True, False])
        
        elif db_type in ["date", "datetime"]:
            base = datetime.now() - timedelta(days=365)
            return lambda: (base + timedelta(days=random.randint(0, 365))).isoformat()
        
        else:  # string
            return lambda: fake.text(max_nb_chars=50)
