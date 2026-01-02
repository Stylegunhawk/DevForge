import pytest
from src.tools.datagen.lexical_dict import lookup_lexical, SemanticType
from src.tools.datagen.semantic_router import SemanticRouter

def test_lexical_expansion():
    """Verify new lexical mappings and generators."""
    
    # Test new mappings
    assert lookup_lexical("username") == SemanticType.USERNAME
    assert lookup_lexical("job_title") == SemanticType.JOB_TITLE
    assert lookup_lexical("street") == SemanticType.STREET_ADDRESS
    assert lookup_lexical("credit_card") == SemanticType.CREDIT_CARD
    assert lookup_lexical("currency") == SemanticType.CURRENCY_CODE
    assert lookup_lexical("ip_v6") == SemanticType.IP_V6
    assert lookup_lexical("mac_address") == SemanticType.MAC_ADDRESS
    
    # Test generators
    router = SemanticRouter()
    
    # Username
    val = router.generate_value("username", "user", {})
    assert isinstance(val, str) and len(val) > 0
    
    # Job Title
    val = router.generate_value("job_title", "employee", {})
    assert isinstance(val, str) and len(val) > 0
    
    # Street Address
    val = router.generate_value("street_address", "address", {})
    assert any(char.isdigit() for char in val) # Should contain numbers
    
    # Credit Card
    val = router.generate_value("credit_card", "payment", {})
    assert isinstance(val, str) and len(val) >= 13
    
    # Currency
    val = router.generate_value("currency_code", "order", {})
    assert len(val) == 3 and val.isupper()
    
    # IP v6
    val = router.generate_value("ip_v6", "log", {})
    assert ":" in val
    
    # MAC Address
    val = router.generate_value("mac_address", "device", {})
    assert ":" in val and len(val) == 17
