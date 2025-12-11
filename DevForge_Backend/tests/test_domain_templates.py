"""Tests for domain templates.

Tests cover:
- Template validation (converts to valid SchemaDesign)
- All required entities present
- Relationships are valid
- Distribution hints are present
- Template registry access
"""

import pytest
from src.tools.datagen.domain_templates import (
    get_ecommerce_template,
    get_saas_template,
    get_template,
    list_domains,
)
from src.tools.datagen.schema_models import SchemaDesign


class TestEcommerceTemplate:
    """Tests for e-commerce domain template."""

    def test_ecommerce_basic(self):
        """Test basic e-commerce template structure."""
        schema = get_ecommerce_template()
        
        assert isinstance(schema, SchemaDesign)
        assert schema.domain == "ecommerce"
        
        # Check entities
        assert "customers" in schema.entities
        assert "products" in schema.entities
        assert "orders" in schema.entities

    def test_ecommerce_entity_counts(self):
        """Test e-commerce default entity counts."""
        schema = get_ecommerce_template()
        
        assert schema.entities["customers"].count == 100
        assert schema.entities["products"].count == 50
        assert schema.entities["orders"].count == 500

    def test_ecommerce_custom_counts(self):
        """Test e-commerce with custom counts."""
        schema = get_ecommerce_template(
            customer_count=200,
            product_count=100,
            order_count=1000
        )
        
        assert schema.entities["customers"].count == 200
        assert schema.entities["products"].count == 100
        assert schema.entities["orders"].count == 1000

    def test_ecommerce_relationships(self):
        """Test e-commerce relationships."""
        schema = get_ecommerce_template()
        
        assert len(schema.relationships) == 2
        
        # Check order -> customer relationship
        rel1 = schema.relationships[0]
        assert rel1.from_entity == "orders"
        assert rel1.from_field == "customer_id"
        assert rel1.to_entity == "customers"
        
        # Check order -> product relationship
        rel2 = schema.relationships[1]
        assert rel2.from_entity == "orders"
        assert rel2.from_field == "product_id"
        assert rel2.to_entity == "products"

    def test_ecommerce_distribution_hints(self):
        """Test e-commerce has distribution hints."""
        schema = get_ecommerce_template()
        
        # Check product price has lognormal distribution
        product_fields = {f.name: f for f in schema.entities["products"].fields}
        assert "price" in product_fields
        assert product_fields["price"].distribution == "lognormal"
        
        # Check order total_amount has distribution
        order_fields = {f.name: f for f in schema.entities["orders"].fields}
        assert "total_amount" in order_fields
        assert order_fields["total_amount"].distribution == "lognormal"


class TestSaasTemplate:
    """Tests for SaaS domain template."""

    def test_saas_basic(self):
        """Test basic SaaS template structure."""
        schema = get_saas_template()
        
        assert isinstance(schema, SchemaDesign)
        assert schema.domain == "saas"
        
        # Check entities
        assert "users" in schema.entities
        assert "subscriptions" in schema.entities
        assert "usage_logs" in schema.entities

    def test_saas_entity_counts(self):
        """Test SaaS default entity counts."""
        schema = get_saas_template()
        
        assert schema.entities["users"].count == 100
        assert schema.entities["subscriptions"].count == 120
        assert schema.entities["usage_logs"].count == 1000

    def test_saas_custom_counts(self):
        """Test SaaS with custom counts."""
        schema = get_saas_template(
            user_count=200,
            subscription_count=250,
            usage_log_count=2000
        )
        
        assert schema.entities["users"].count == 200
        assert schema.entities["subscriptions"].count == 250
        assert schema.entities["usage_logs"].count == 2000

    def test_saas_relationships(self):
        """Test SaaS relationships."""
        schema = get_saas_template()
        
        assert len(schema.relationships) == 2
        
        # Check subscription -> user relationship
        rel1 = schema.relationships[0]
        assert rel1.from_entity == "subscriptions"
        assert rel1.from_field == "user_id"
        assert rel1.to_entity == "users"
        
        # Check usage_log -> subscription relationship
        rel2 = schema.relationships[1]
        assert rel2.from_entity == "usage_logs"
        assert rel2.from_field == "subscription_id"
        assert rel2.to_entity == "subscriptions"

    def test_saas_distribution_hints(self):
        """Test SaaS has distribution hints."""
        schema = get_saas_template()
        
        # Check subscription plan has categorical distribution
        sub_fields = {f.name: f for f in schema.entities["subscriptions"].fields}
        assert "plan" in sub_fields
        assert sub_fields["plan"].distribution == "categorical"
        
        # Check usage_logs has pareto for API calls
        usage_fields = {f.name: f for f in schema.entities["usage_logs"].fields}
        assert "api_calls" in usage_fields
        assert usage_fields["api_calls"].distribution == "pareto"


class TestTemplateRegistry:
    """Tests for template registry and access."""

    def test_get_template_ecommerce(self):
        """Test getting ecommerce template via registry."""
        schema = get_template("ecommerce")
        
        assert schema.domain == "ecommerce"
        assert "customers" in schema.entities

    def test_get_template_saas(self):
        """Test getting saas template via registry."""
        schema = get_template("saas")
        
        assert schema.domain == "saas"
        assert "users" in schema.entities

    def test_get_template_case_insensitive(self):
        """Test template lookup is case-insensitive."""
        schema1 = get_template("ECOMMERCE")
        schema2 = get_template("Ecommerce")
        schema3 = get_template("ecommerce")
        
        # All should return valid schemas
        assert schema1.domain == "ecommerce"
        assert schema2.domain == "ecommerce"
        assert schema3.domain == "ecommerce"

    def test_get_template_invalid_domain(self):
        """Test getting invalid domain raises error."""
        with pytest.raises(ValueError, match="Unknown domain"):
            get_template("healthcare")

    def test_list_domains(self):
        """Test listing available domains."""
        domains = list_domains()
        
        assert len(domains) == 2
        assert "ecommerce" in domains
        assert "saas" in domains


class TestSchemaValidation:
    """Tests that templates produce valid schemas."""

    def test_ecommerce_schema_valid(self):
        """Test ecommerce template is valid SchemaDesign."""
        schema = get_ecommerce_template()
        
        # Should not raise validation error
        assert schema.domain == "ecommerce"
        
        # Should be able to get generation order
        order = schema.get_generation_order()
        assert "customers" in order
        assert "products" in order
        assert "orders" in order

    def test_saas_schema_valid(self):
        """Test saas template is valid SchemaDesign."""
        schema = get_saas_template()
        
        # Should not raise validation error
        assert schema.domain == "saas"
        
        # Should be able to get generation order
        order = schema.get_generation_order()
        assert "users" in order
        assert "subscriptions" in order
        assert "usage_logs" in order

    def test_generation_order_correct(self):
        """Test templates have correct generation order."""
        # E-commerce
        ecom_schema = get_ecommerce_template()
        ecom_order = ecom_schema.get_generation_order()
        assert ecom_order.index("customers") < ecom_order.index("orders")
        assert ecom_order.index("products") < ecom_order.index("orders")
        
        # SaaS
        saas_schema = get_saas_template()
        saas_order = saas_schema.get_generation_order()
        assert saas_order.index("users") < saas_order.index("subscriptions")
        assert saas_order.index("subscriptions") < saas_order.index("usage_logs")
