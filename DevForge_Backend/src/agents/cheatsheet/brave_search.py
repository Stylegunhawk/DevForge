"""Brave Search API client for retrieving up-to-date documentation.

Used by the LLM path to ground responses in current documentation,
solving the "staleness" problem.
"""

import os
import httpx
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    title: str
    url: str
    description: str
    age: Optional[str] = None


class BraveSearchClient:
    """Async client for Brave Search API."""
    
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self, api_key: Optional[str] = None):
        # Prefer dependency injection or env var
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        if not self.api_key:
            logger.warning("BRAVE_SEARCH_API_KEY not set. Search provided will fail or return empty.")
            
    async def search_docs(self, query: str, count: int = 3) -> List[SearchResult]:
        """
        Search for documentation.
        
        Args:
            query: Search query
            count: Number of results (max 20)
            
        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            return []
            
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": min(count, 10),  # Limit to 10 for cost/performance
            "text_decorations": 0,
            "result_filter": "web",
            "freshness": "pd"  # Prefer newer content if possible? "pd" is past day, "pm" past month, "py" past year. 
                               # Actually for docs we usually want relevance over strict recency unless it's a "latest" query.
                               # Leaving freshness out for general relevance, or maybe "py" (past year) to avoid ancient docs?
                               # Let's stick to default relevance for now.
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.BASE_URL, 
                    headers=headers, 
                    params=params
                )
                
                if response.status_code == 403:
                    logger.error("Brave API Key invalid or quota exceeded.")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                results = []
                if "web" in data and "results" in data["web"]:
                    for item in data["web"]["results"]:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            description=item.get("description", ""),
                            age=item.get("age", "")
                        ))
                
                return results
                
        except httpx.HTTPError as e:
            logger.error(f"Brave Search API failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in search: {e}")
            return []

    async def verify_availability(self) -> bool:
        """Check if search is available (api key valid)."""
        if not self.api_key:
            return False
        # Do a lightweight search to test
        results = await self.search_docs("test", count=1)
        return True # if no exception raised
