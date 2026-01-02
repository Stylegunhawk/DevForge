"""Test semantic router value generation."""

import pytest
from src.tools.datagen.semantic_router import SemanticRouter


class TestSemanticRouter:
    """Test value generation from semantic types."""
    
    @pytest.fixture
    def router(self):
        return SemanticRouter()
    
    def test_person_name_generation(self, router):
        """Should generate realistic person names."""
        name = router.generate_value("person_full_name", "customers")
        
        assert isinstance(name, str)
        assert len(name) > 0
        # No LLM prose
        assert "Agent every" not in name
        assert "development" not in name
    
    def test_email_generation(self, router):
        """Should generate valid email format."""
        email = router.generate_value("email_address", "users")
        
        assert isinstance(email, str)
        assert "@" in email
        assert "." in email.split("@")[1]
    
    def test_bank_account_number_generation(self, router):
        """Should generate numeric account numbers."""
        account = router.generate_value("bank_account_number", "accounts")
        
        assert isinstance(account, str)
        assert account.isdigit()
        assert 10 <= len(account) <= 12
    
    def test_money_amount_with_constraints(self, router):
        """Should respect min/max constraints."""
        amount = router.generate_value(
            "money_amount", 
            "transactions",
            constraints={"min": 100, "max": 500}
        )
        
        assert isinstance(amount, (int, float))
        assert 100 <= amount <= 500
    
    def test_enum_constraint_override(self, router):
        """Enum constraints should override default generator."""
        value = router.generate_value(
            "enum_value",
            "orders",
            constraints={"enum": ["pending", "active", "closed"]}
        )
        
        assert value in ["pending", "active", "closed"]
    
    def test_uuid_generation(self, router):
        """Should generate valid UUID format."""
        uid = router.generate_value("uuid", "records")
        
        assert isinstance(uid, str)
        assert len(uid) == 36  # UUID v4 format
        assert uid.count("-") == 4
    
    def test_boolean_generation(self, router):
        """Should generate boolean values."""
        value = router.generate_value("boolean_flag", "users")
        
        assert isinstance(value, bool)
    
    def test_unknown_type_fallback(self, router):
        """Unknown types should fallback gracefully."""
        value = router.generate_value("unknown", "test")
        
        assert isinstance(value, str)
        # Should be a word, not empty
        assert len(value) > 0
    
    def test_timestamp_generation(self, router):
        """Should generate ISO format timestamps."""
        ts = router.generate_value("timestamp", "events")
        
        assert isinstance(ts, str)
        # Should have ISO format indicators
        assert "T" in ts or "-" in ts
    
    def test_date_generation(self, router):
        """Should generate ISO format dates."""
        date = router.generate_value("date", "events")
        
        assert isinstance(date, str)
        assert "-" in date  # YYYY-MM-DD format
    
    def test_transaction_id_generation(self, router):
        """Should generate transaction IDs with prefix."""
        txn_id = router.generate_value("transaction_id", "transactions")
        
        assert isinstance(txn_id, str)
        assert txn_id.startswith("TXN")
        assert len(txn_id) > 5
    
    def test_order_code_generation(self, router):
        """Should generate order codes."""
        code = router.generate_value("order_code", "orders")
        
        assert isinstance(code, str)
        assert "ORD" in code or "-" in code
    
    def test_percentage_generation(self, router):
        """Should generate percentage values."""
        pct = router.generate_value("percentage", "discounts")
        
        assert isinstance(pct, (int, float))
        assert 0 <= pct <= 100
    
    def test_phone_number_generation(self, router):
        """Should generate phone numbers."""
        phone = router.generate_value("phone_number", "contacts")
        
        assert isinstance(phone, str)
        assert len(phone) > 0
    
    def test_company_name_generation(self, router):
        """Should generate company names."""
        company = router.generate_value("company_name", "companies")
        
        assert isinstance(company, str)
        assert len(company) > 0
    
    def test_city_name_generation(self, router):
        """Should generate city names."""
        city = router.generate_value("city_name", "locations")
        
        assert isinstance(city, str)
        assert len(city) > 0
    
    def test_country_name_generation(self, router):
        """Should generate country names."""
        country = router.generate_value("country_name", "locations")
        
        assert isinstance(country, str)
        assert len(country) > 0


class TestSemanticRouterWithCatalog:
    """Test semantic router with catalog factory."""
    
    @pytest.fixture
    def router_with_catalog(self):
        from src.tools.datagen.catalog_factory import CatalogFactory
        catalog = CatalogFactory(llm_client=None)  # Uses fallback
        return SemanticRouter(catalog_factory=catalog)
    
    def test_flower_name_from_catalog(self, router_with_catalog):
        """Should get flower names from catalog."""
        name = router_with_catalog.generate_value("flower_name", "flowers")
        
        assert isinstance(name, str)
        assert len(name) > 0
        # Should be from fallback catalog
        known_flowers = ["Rose", "Tulip", "Lily", "Daisy", "Orchid", "Sunflower"]
        # At least one run should get a known flower
    
    def test_institution_name_from_catalog(self, router_with_catalog):
        """Should get institution names from catalog."""
        name = router_with_catalog.generate_value("institution_name", "universities")
        
        assert isinstance(name, str)
        assert len(name) > 0
    
    def test_product_name_from_catalog(self, router_with_catalog):
        """Should get product names from catalog."""
        name = router_with_catalog.generate_value("product_name", "products")
        
        assert isinstance(name, str)
        assert len(name) > 0
