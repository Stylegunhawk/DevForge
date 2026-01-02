"""Comprehensive test suite for Phase 1 semantic analyzer components."""

import pytest
from src.tools.datagen.semantic_analyzer_v2 import SemanticAnalyzer
from src.tools.datagen.semantic_types import FieldContext, SemanticType
from src.tools.datagen.lexical_classifier import LexicalClassifier
from src.tools.datagen.pattern_classifier import PatternClassifier
from src.tools.datagen.context_classifier import ContextClassifier


class TestLexicalClassifier:
    """Test lexical dictionary-based classification."""
    
    def test_exact_match_email(self):
        """Email field should be classified as email_address."""
        classifier = LexicalClassifier()
        ctx = FieldContext(entity_name="users", field_name="email")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "email_address"
        assert result.source == "lexical"
        assert result.confidence == 0.95
    
    def test_exact_match_account_number(self):
        """Account_number should map to bank_account_number."""
        classifier = LexicalClassifier()
        ctx = FieldContext(entity_name="accounts", field_name="account_number")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "bank_account_number"
        assert result.confidence == 0.95
    
    def test_case_insensitive(self):
        """Should match regardless of case."""
        classifier = LexicalClassifier()
        ctx = FieldContext(entity_name="users", field_name="EMAIL")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "email_address"
    
    def test_no_match_returns_none(self):
        """Unknown field should return None."""
        classifier = LexicalClassifier()
        ctx = FieldContext(entity_name="test", field_name="unknown_field_xyz")
        result = classifier.classify(ctx)
        
        assert result is None
    
    def test_phone_number_match(self):
        """Phone field should be classified as phone_number."""
        classifier = LexicalClassifier()
        ctx = FieldContext(entity_name="contacts", field_name="phone")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "phone_number"
    
    def test_money_fields(self):
        """Money-related fields should be classified as money_amount."""
        classifier = LexicalClassifier()
        for field in ["balance", "amount", "price", "total"]:
            ctx = FieldContext(entity_name="transactions", field_name=field)
            result = classifier.classify(ctx)
            assert result is not None
            assert result.semantic_type == "money_amount"


class TestPatternClassifier:
    """Test pattern-based classification."""
    
    def test_at_suffix_timestamp(self):
        """Fields ending in _at should be timestamp."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="posts", field_name="created_at")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "timestamp"
        assert result.source == "pattern"
    
    def test_amount_suffix(self):
        """Fields ending in _amount should be money_amount."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="transactions", field_name="total_amount")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "money_amount"
    
    def test_is_prefix_boolean(self):
        """Fields starting with is_ should be boolean_flag."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="users", field_name="is_active")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "boolean_flag"
    
    def test_has_prefix_boolean(self):
        """Fields starting with has_ should be boolean_flag."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="users", field_name="has_subscription")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "boolean_flag"
    
    def test_camelcase_normalization(self):
        """Should handle camelCase field names."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="orders", field_name="createdAt")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "timestamp"
    
    def test_date_suffix(self):
        """Fields ending in _date should be date."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="orders", field_name="ship_date")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "date"
    
    def test_email_suffix(self):
        """Fields ending in _email should be email_address."""
        classifier = PatternClassifier()
        ctx = FieldContext(entity_name="users", field_name="work_email")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "email_address"


class TestContextClassifier:
    """Test context-based classification."""
    
    def test_flower_name_field(self):
        """flowers.name should be flower_name."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="flowers", field_name="name")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "flower_name"
        assert result.source == "context"
    
    def test_university_name_field(self):
        """universities.name should be institution_name."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="universities", field_name="name")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "institution_name"
    
    def test_customer_name_field(self):
        """customers.name should be person_full_name."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="customers", field_name="name")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "person_full_name"
    
    def test_product_name_field(self):
        """products.name should be product_name."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="products", field_name="name")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "product_name"
    
    def test_plural_entity_name(self):
        """Should handle plural entity names."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="flowers", field_name="name")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "flower_name"
    
    def test_non_name_field_returns_none(self):
        """Only handles 'name' or 'title' fields."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="flowers", field_name="color")
        result = classifier.classify(ctx)
        
        assert result is None
    
    def test_title_field_same_as_name(self):
        """title field should behave like name."""
        classifier = ContextClassifier()
        ctx = FieldContext(entity_name="flowers", field_name="title")
        result = classifier.classify(ctx)
        
        assert result is not None
        assert result.semantic_type == "flower_name"


class TestSemanticAnalyzer:
    """Test full semantic analyzer pipeline."""
    
    def test_lexical_priority(self):
        """Lexical match should take priority for most fields."""
        analyzer = SemanticAnalyzer()
        ctx = FieldContext(entity_name="users", field_name="email")
        result = analyzer.analyze_field(ctx)
        
        assert result.semantic_type == "email_address"
        assert result.source == "lexical"
    
    def test_pattern_fallback(self):
        """Pattern should trigger if lexical doesn't match."""
        analyzer = SemanticAnalyzer()
        ctx = FieldContext(entity_name="posts", field_name="published_at")
        result = analyzer.analyze_field(ctx)
        
        assert result.semantic_type == "timestamp"
        assert result.source == "pattern"
    
    def test_context_for_title(self):
        """Context should trigger for entity-specific title fields."""
        analyzer = SemanticAnalyzer()
        ctx = FieldContext(entity_name="flowers", field_name="title")
        result = analyzer.analyze_field(ctx)
        
        assert result.semantic_type == "flower_name"
        assert result.source == "context"
    
    def test_fallback_for_unknown(self):
        """Unknown fields should fallback with confidence 0."""
        analyzer = SemanticAnalyzer()
        ctx = FieldContext(entity_name="test", field_name="xyz_unknown_field")
        result = analyzer.analyze_field(ctx)
        
        assert result.semantic_type == "unknown"
        assert result.source == "fallback"
        assert result.confidence == 0.0
    
    def test_schema_analysis(self):
        """Should analyze full schema."""
        analyzer = SemanticAnalyzer()
        schema = {
            "customers": {
                "fields": {
                    "email": {"type": "string"},
                    "created_at": {"type": "timestamp"},
                    "balance": {"type": "number"}
                }
            }
        }
        
        results = analyzer.analyze_schema(schema, user_prompt="banking")
        
        assert "customers" in results
        assert len(results["customers"]) == 3
        
        # Check each field was analyzed
        field_map = {f.field_name: f for f in results["customers"]}
        assert "email" in field_map
        assert "created_at" in field_map
        assert "balance" in field_map
    
    def test_always_returns_result(self):
        """Analyzer should never return None - always fallback."""
        analyzer = SemanticAnalyzer()
        ctx = FieldContext(entity_name="random", field_name="qwerty123")
        result = analyzer.analyze_field(ctx)
        
        assert result is not None
        assert isinstance(result.semantic_type, str)
        assert isinstance(result.confidence, float)


class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def generator(self):
        """Create generator without LLM for testing."""
        from src.tools.datagen.advanced_generator_v2 import AdvancedGeneratorV2
        return AdvancedGeneratorV2(llm_client=None, enable_semantic=True)
    
    def test_banking_example_no_llm_prose(self, generator):
        """
        CRITICAL TEST: Banking example should NOT produce LLM prose.
        This is the bug we're fixing.
        """
        schema = {
            "bank_accounts": {
                "fields": {
                    "account_number": {"type": "string"},
                    "holder_name": {"type": "string"},
                    "balance": {"type": "number", "minimum": -500, "maximum": 100000}
                }
            }
        }
        
        result = generator.generate(
            schema=schema,
            row_count=50,
            user_prompt="Generate realistic bank account data"
        )
        
        # Extract all generated data as string
        data_str = str(result["data"])
        
        # CRITICAL: No LLM prose should appear
        assert "Agent every" not in data_str
        assert "development say" not in data_str
        assert "Choice whatever" not in data_str
        
        # Verify structure
        accounts = result["data"]["bank_accounts"]
        assert len(accounts) == 50
        
        # Check first account
        account = accounts[0]
        
        # account_number should be numeric
        assert "account_number" in account
        assert isinstance(account["account_number"], str)
        assert len(account["account_number"]) >= 10
        assert account["account_number"].isdigit()
        
        # balance should be in range
        assert "balance" in account
        assert -500 <= account["balance"] <= 100000
    
    def test_metadata_present(self, generator):
        """Metadata should be included in response."""
        schema = {
            "users": {
                "fields": {
                    "email": {"type": "string"},
                    "created_at": {"type": "timestamp"}
                }
            }
        }
        
        result = generator.generate(schema, row_count=10)
        
        assert "metadata" in result
        assert "semantic_analysis_summary" in result["metadata"]
        
        summary = result["metadata"]["semantic_analysis_summary"]
        assert summary["enabled"] == True
        assert summary["total_fields"] == 2
        assert summary["avg_confidence"] > 0
    
    def test_multi_entity_generation(self, generator):
        """Should generate data for multiple entities."""
        schema = {
            "users": {
                "fields": {
                    "email": {"type": "string"},
                    "name": {"type": "string"}
                }
            },
            "orders": {
                "fields": {
                    "total": {"type": "number"},
                    "created_at": {"type": "timestamp"}
                }
            }
        }
        
        result = generator.generate(schema, row_count=10)
        
        assert "users" in result["data"]
        assert "orders" in result["data"]
        assert len(result["data"]["users"]) == 10
        assert len(result["data"]["orders"]) == 10
    
    def test_disabled_semantic_fallback(self):
        """Should work with semantic disabled."""
        from src.tools.datagen.advanced_generator_v2 import AdvancedGeneratorV2
        generator = AdvancedGeneratorV2(llm_client=None, enable_semantic=False)
        
        schema = {
            "test": {
                "fields": {
                    "value": {"type": "string"}
                }
            }
        }
        
        result = generator.generate(schema, row_count=5)
        
        assert "data" in result
        assert len(result["data"]["test"]) == 5
        assert result["metadata"]["semantic_analysis_summary"]["enabled"] == False
