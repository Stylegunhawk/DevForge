"""LLM-based catalog generation for domain-specific values.

Phase 1: Catalog factory generates value lists using LLM, then
the generator samples from these lists (LLM never produces actual data values).
"""

import json
import time
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Catalog:
    """A catalog of domain-specific values."""
    semantic_type: str
    domain: str
    values: List[str]
    generated_at: float


class CatalogFactory:
    """Generates domain-specific value catalogs using LLM."""
    
    CATALOG_PROMPT = """You are a data catalog generator.
Your job is to produce lists of realistic values for a given semantic type.
You must return ONLY a JSON array of strings. No explanations.

Generate a catalog of realistic values for this field.

Semantic type: {semantic_type}
Domain context: {domain}
Entity name: {entity_name}

Requirements:
- Return ONLY a JSON array of strings. Example: ["Rose", "Tulip", "Orchid"]
- Provide EXACTLY 50 items if possible.
- All items must be realistic examples of {semantic_type}.
- No person names unless the semantic type is person_full_name.
- No explanations, no markdown, no trailing comments.

Generate the JSON array now:"""

    def __init__(self, llm_client=None, cache_ttl_seconds=3600):
        self.llm = llm_client
        self.cache_ttl = cache_ttl_seconds
        
        # L1: Request-scope cache
        self.l1_cache: dict[str, Catalog] = {}
        
        # L2: Process-scope cache with TTL
        self.l2_cache: dict[str, Catalog] = {}
    
    def get_catalog(
        self, 
        semantic_type: str, 
        entity_name: str,
        domain: str = "general"
    ) -> List[str]:
        """
        Get or generate catalog for semantic type.
        
        Returns:
            List of realistic values
        """
        cache_key = f"catalog:{semantic_type}:{domain}"
        
        # Check L1 cache
        if cache_key in self.l1_cache:
            logger.debug(f"Catalog cache hit (L1): {cache_key}")
            return self.l1_cache[cache_key].values
        
        # Check L2 cache (with TTL)
        if cache_key in self.l2_cache:
            catalog = self.l2_cache[cache_key]
            if time.time() - catalog.generated_at < self.cache_ttl:
                logger.debug(f"Catalog cache hit (L2): {cache_key}")
                self.l1_cache[cache_key] = catalog
                return catalog.values
        
        # Generate new catalog
        logger.info(f"Generating catalog for {semantic_type} (domain: {domain})")
        catalog = self._generate_catalog(semantic_type, entity_name, domain)
        
        # Cache
        self.l1_cache[cache_key] = catalog
        self.l2_cache[cache_key] = catalog
        
        # Evict old L2 entries if too many (max 1000)
        if len(self.l2_cache) > 1000:
            oldest_key = min(self.l2_cache.keys(), 
                           key=lambda k: self.l2_cache[k].generated_at)
            del self.l2_cache[oldest_key]
        
        return catalog.values
    
    def _generate_catalog(
        self, 
        semantic_type: str, 
        entity_name: str,
        domain: str
    ) -> Catalog:
        """Generate catalog using LLM."""
        if self.llm is None:
            logger.warning(f"No LLM client configured. Using fallback catalog for {semantic_type}")
            return self._fallback_catalog(semantic_type, domain)
        
        prompt = self.CATALOG_PROMPT.format(
            semantic_type=semantic_type,
            domain=domain,
            entity_name=entity_name
        )
        
        try:
            # First attempt
            response = self.llm.invoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)
            values = self._parse_catalog(text)
            
            if values and len(values) >= 40:
                logger.info(f"Generated catalog for {semantic_type}: {len(values)} values")
                return Catalog(
                    semantic_type=semantic_type,
                    domain=domain,
                    values=values,
                    generated_at=time.time()
                )
            
            # Retry with stricter prompt
            logger.warning(f"Catalog generation for {semantic_type} returned {len(values) if values else 0} items. Retrying...")
            
            stricter_prompt = prompt + "\n\nIMPORTANT: Return ONLY a JSON array with EXACTLY 50 string values. No other text."
            response = self.llm.invoke(stricter_prompt)
            text = response.content if hasattr(response, 'content') else str(response)
            values = self._parse_catalog(text)
            
            if values and len(values) >= 40:
                return Catalog(
                    semantic_type=semantic_type,
                    domain=domain,
                    values=values,
                    generated_at=time.time()
                )
            
            # Fallback to generic values
            logger.error(f"Catalog generation failed for {semantic_type}. Using fallback.")
            return self._fallback_catalog(semantic_type, domain)
        
        except Exception as e:
            logger.error(f"Catalog generation failed: {e}")
            return self._fallback_catalog(semantic_type, domain)
    
    def _parse_catalog(self, text: str) -> Optional[List[str]]:
        """Parse LLM response into list of values."""
        # Remove markdown
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Find JSON content between ``` markers
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)
        
        try:
            values = json.loads(text)
            
            if not isinstance(values, list):
                return None
            
            # Filter to strings only, remove empty
            values = [str(v) for v in values if v]
            
            # Deduplicate
            values = list(dict.fromkeys(values))
            
            return values
        except json.JSONDecodeError:
            return None
    
    def _fallback_catalog(self, semantic_type: str, domain: str) -> Catalog:
        """Generate fallback catalog for common types."""
        fallback_catalogs = {
            "flower_name": [
                "Rose", "Tulip", "Lily", "Daisy", "Orchid", "Sunflower", "Carnation",
                "Chrysanthemum", "Daffodil", "Iris", "Peony", "Hibiscus", "Jasmine",
                "Lavender", "Marigold", "Petunia", "Poppy", "Snapdragon", "Violet",
                "Zinnia", "Amaryllis", "Begonia", "Bluebell", "Camellia", "Dahlia",
                "Freesia", "Gardenia", "Geranium", "Gladiolus", "Honeysuckle",
                "Hydrangea", "Lilac", "Magnolia", "Narcissus", "Pansy", "Primrose",
                "Ranunculus", "Sweet Pea", "Tulip", "Wisteria", "Yarrow", "Azalea",
                "Bird of Paradise", "Buttercup", "Crocus", "Delphinium", "Foxglove",
                "Lotus", "Morning Glory", "Plumeria"
            ],
            "country_name": [
                "United States", "United Kingdom", "Canada", "Germany", "France",
                "Japan", "Australia", "Italy", "Spain", "Netherlands", "Sweden",
                "Switzerland", "Belgium", "Austria", "Norway", "Denmark", "Finland",
                "Ireland", "New Zealand", "Singapore", "South Korea", "Brazil",
                "Mexico", "Argentina", "Chile", "India", "China", "Indonesia",
                "Thailand", "Malaysia", "Philippines", "Vietnam", "South Africa",
                "Egypt", "Morocco", "Nigeria", "Kenya", "Israel", "UAE", "Saudi Arabia",
                "Turkey", "Poland", "Czech Republic", "Hungary", "Greece", "Portugal",
                "Romania", "Ukraine", "Russia", "Colombia"
            ],
            "city_name": [
                "New York", "London", "Paris", "Tokyo", "Sydney", "Berlin", "Toronto",
                "Singapore", "Hong Kong", "Dubai", "Los Angeles", "Chicago", "Houston",
                "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "Austin",
                "San Francisco", "Seattle", "Denver", "Boston", "Atlanta", "Miami",
                "Portland", "Las Vegas", "Minneapolis", "Detroit", "Baltimore",
                "Manchester", "Birmingham", "Glasgow", "Edinburgh", "Liverpool",
                "Munich", "Frankfurt", "Hamburg", "Amsterdam", "Rotterdam", "Brussels",
                "Milan", "Rome", "Madrid", "Barcelona", "Lisbon", "Vienna", "Prague",
                "Warsaw", "Budapest"
            ],
            "institution_name": [
                "Harvard University", "MIT", "Stanford University", "Oxford University",
                "Cambridge University", "Yale University", "Princeton University",
                "Columbia University", "University of Chicago", "Duke University",
                "Northwestern University", "Cornell University", "Brown University",
                "Dartmouth College", "University of Pennsylvania", "Johns Hopkins University",
                "California Institute of Technology", "UC Berkeley", "UCLA", "USC",
                "University of Michigan", "NYU", "Boston University", "Georgetown University",
                "Emory University", "Vanderbilt University", "Rice University",
                "University of Notre Dame", "Carnegie Mellon University", "Georgia Tech",
                "University of Virginia", "University of North Carolina", "Wake Forest University",
                "Tufts University", "University of Rochester", "Case Western Reserve",
                "University of Miami", "Tulane University", "Northeastern University",
                "Boston College", "University of Wisconsin", "University of Illinois",
                "Ohio State University", "Penn State", "University of Texas", "Texas A&M",
                "University of Florida", "University of Georgia", "Auburn University",
                "Clemson University"
            ],
            "company_name": [
                "Acme Corporation", "TechVentures Inc", "Global Solutions Ltd",
                "Pinnacle Industries", "Vertex Systems", "Horizon Enterprises",
                "Summit Partners", "Cascade Holdings", "Quantum Innovations",
                "Atlas Group", "Sterling & Associates", "Paramount Services",
                "Apex Technologies", "Frontier Capital", "Nexus Corp",
                "Pacific Dynamics", "Continental Resources", "Mercury Labs",
                "Titan Manufacturing", "Evergreen Partners", "Silverline Consulting",
                "BlueOcean Ventures", "Redwood Financial", "Cornerstone Group",
                "Lighthouse Capital", "Ironclad Security", "SwiftLogistics",
                "Precision Engineering", "Harmony Healthcare", "Vanguard Investments",
                "Elite Consulting", "Prime Logistics", "Catalyst Partners",
                "Beacon Financial", "Northstar Industries", "Eastwood Holdings",
                "Westbridge Enterprises", "Southland Corp", "Riverdale Associates",
                "Highland Group", "Coastal Ventures", "Midland Resources",
                "Trident Systems", "Phoenix Consulting", "Aurora Technologies",
                "Stellar Solutions", "Oasis Partners", "Velocity Ventures",
                "Fusion Dynamics"
            ],
            "product_name": [
                "ProMax 3000", "UltraLite X", "PowerCore Elite", "SwiftDrive Pro",
                "VisionTech HD", "ComfortPlus Deluxe", "EcoSmart 500", "TurboCharge XL",
                "SmartHome Hub", "AquaPure Filter", "FlexFit Trainer", "SilentRun Motor",
                "CrystalClear Display", "MaxProtect Shield", "QuickConnect Adapter",
                "EasyGrip Handle", "PrecisionCut Blade", "DuraLast Battery", "SlimFit Case",
                "RapidHeat Element", "CoolBreeze Fan", "SoftTouch Fabric", "BrightLight LED",
                "SecureLock System", "FreshAir Purifier", "CleanWash Detergent",
                "GentleCare Formula", "StrongBond Adhesive", "QuietZone Panels",
                "SafeGuard Alarm", "SpeedTest Kit", "MultiTool Set", "ErgoPro Chair",
                "UltraView Monitor", "SmartScale Pro", "PowerBank Plus", "WirelessCharge Pad",
                "NoiseCancel Buds", "FitTrack Watch", "HomeAssist Speaker",
                "StreamBox Media", "GamePro Controller", "CloudSync Drive", "SecureVault App",
                "PhotoPro Editor", "DocuScan Mobile", "MeetNow Video", "TaskMaster Planner",
                "BudgetWise Finance"
            ],
            "person_full_name": [
                "James Smith", "Maria Garcia", "Robert Johnson", "Patricia Williams",
                "Michael Brown", "Jennifer Jones", "William Davis", "Linda Miller",
                "David Wilson", "Elizabeth Moore", "Richard Taylor", "Barbara Anderson",
                "Joseph Thomas", "Susan Jackson", "Thomas White", "Jessica Harris",
                "Charles Martin", "Sarah Thompson", "Christopher Garcia", "Karen Martinez",
                "Daniel Robinson", "Nancy Clark", "Matthew Rodriguez", "Betty Lewis",
                "Anthony Lee", "Margaret Walker", "Mark Hall", "Sandra Allen",
                "Donald Young", "Ashley King", "Steven Wright", "Dorothy Scott",
                "Paul Green", "Kimberly Adams", "Andrew Baker", "Emily Nelson",
                "Joshua Hill", "Michelle Ramirez", "Kenneth Campbell", "Amanda Mitchell",
                "Kevin Roberts", "Melissa Carter", "Brian Phillips", "Deborah Evans",
                "George Turner", "Stephanie Torres", "Edward Parker", "Rebecca Collins",
                "Ronald Edwards", "Laura Stewart"
            ],
        }
        
        values = fallback_catalogs.get(
            semantic_type, 
            [f"{semantic_type}_value_{i}" for i in range(1, 51)]
        )
        
        return Catalog(
            semantic_type=semantic_type,
            domain=domain,
            values=values,
            generated_at=time.time()
        )
    
    def clear_cache(self):
        """Clear all caches."""
        self.l1_cache.clear()
        self.l2_cache.clear()
        logger.info("Catalog caches cleared")
