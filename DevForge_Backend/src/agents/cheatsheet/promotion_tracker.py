"""
Track successful enrichments to identify candidates for template promotion.
"""
import logging
from collections import defaultdict
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class PromotionTracker:
    """
    Tracks frequency of specific (library, section) enrichments.
    High frequency indicates a candidate for promoting to a permanent template.
    """
    
    def __init__(self):
        # Key: (library, section_title), Value: count
        self._counts: Dict[Tuple[str, str], int] = defaultdict(int)
        self.PROMOTION_THRESHOLD = 3  # Configurable threshold
        
    def record_enrichment(self, library: str, section_title: str) -> None:
        """Record a successful enrichment event."""
        key = (library, section_title)
        self._counts[key] += 1
        
        if self.should_promote(library, section_title):
            logger.info(f"PROMOTION CANDIDATE: Library '{library}', Section '{section_title}' "
                       f"has been enriched {self._counts[key]} times.")

    def should_promote(self, library: str, section_title: str) -> bool:
        """Check if a section has been enriched enough to warrant promotion."""
        return self._counts[(library, section_title)] >= self.PROMOTION_THRESHOLD
        
    def get_statistics(self) -> Dict:
        """Return all enrichment counts and candidates."""
        stats = {
            "total_enrichments": sum(self._counts.values()),
            "candidates": []
        }
        
        for (lib, sec), count in self._counts.items():
            entry = {
                "library": lib,
                "section": sec,
                "count": count,
                "promote": count >= self.PROMOTION_THRESHOLD
            }
            stats["candidates"].append(entry)
            
        # Sort by count desc
        stats["candidates"].sort(key=lambda x: x["count"], reverse=True)
        return stats

# Global instance
tracker = PromotionTracker()

def should_promote(library: str, section_title: str) -> bool:
    """Helper for external use"""
    return tracker.should_promote(library, section_title)

def get_promotion_stats() -> Dict:
    """Helper to get stats"""
    return tracker.get_statistics()
