"""
Safety verification for Admin Promotion Endpoint.
Ensures the endpoint is strictly read-only and idempotent.
"""
import pytest
from src.agents.cheatsheet.promotion_tracker import tracker

def test_get_statistics_is_readonly_and_idempotent():
    """
    Verify that get_statistics():
    1. Returns correct data
    2. Does NOT change internal state (counts remain same)
    3. Is idempotent (returns same result on multiple calls)
    """
    # Setup: Record some enrichments
    tracker._counts.clear() # Reset for test
    tracker.record_enrichment("lib_a", "section_1")
    tracker.record_enrichment("lib_a", "section_1") # count = 2
    tracker.record_enrichment("lib_b", "section_2") # count = 1
    
    # Snapshot internal state
    initial_internal_state = tracker._counts.copy()
    
    # Action: Call get_statistics multiple times
    stats_1 = tracker.get_statistics()
    stats_2 = tracker.get_statistics()
    
    # Assertion 1: Returns correct data
    assert stats_1["total_enrichments"] == 3
    assert len(stats_1["candidates"]) == 2
    assert stats_1["candidates"][0]["library"] == "lib_a"
    assert stats_1["candidates"][0]["count"] == 2
    
    # Assertion 2: Idempotency (Results identical)
    assert stats_1 == stats_2
    
    # Assertion 3: No Mutation (Internal state unchanged)
    assert tracker._counts == initial_internal_state
    
    # Assertion 4: No side effects (counts didn't increment/reset)
    assert tracker._counts[("lib_a", "section_1")] == 2
