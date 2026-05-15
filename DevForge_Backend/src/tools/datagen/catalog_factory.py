"""LLM-based catalog generation for domain-specific values.

Phase 1: Catalog factory generates value lists using LLM, then
the generator samples from these lists (LLM never produces actual data values).

v0.9: Adds CatalogFactory.get_entity_catalogs — a batched per-entity
LLM call that returns {field_name: [50 realistic values]}. Used by
AdvancedGeneratorV2 to power the catalog-sandbox for every string field.
"""

import asyncio
import hashlib
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from src.core.model_router import model_router

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
    
    # =====================================================================
    # v0.9 — Batched per-entity catalogs (catalog-sandbox)
    # =====================================================================

    ENTITY_CATALOG_PROMPT = (
        "You are a data catalog generator.\n"
        "Generate {count} realistic sample values for each string field of "
        "the `{entity_name}` entity. Return ONLY a single JSON object — one "
        "key per field, each value an array of EXACTLY {count} strings.\n\n"
        "Context: {user_prompt}\n\n"
        "Fields:\n{field_lines}\n\n"
        "Rules:\n"
        "1. Differentiate by field name. `customer.name` is a person; "
        "`product.name` is a product/title; `flower.name` is a flower species.\n"
        "2. All values must be plausible for production data in this domain.\n"
        "3. No prose, no markdown, no explanations — only the JSON object.\n\n"
        'Example: {{"field_a": ["v1", "v2", ..., "v{count}"], '
        '"field_b": ["v1", ..., "v{count}"]}}\n'
    )

    async def get_entity_catalogs(
        self,
        entity_name: str,
        fields: List[Tuple[str, str]],
        user_prompt: str,
        count: int = 50,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Generate domain-realistic value catalogs for all string fields of
        one entity in a single LLM call.

        Args:
            entity_name: Logical entity name (used for LLM context + cache key).
            fields: List of (field_name, data_type) tuples. Only data_type
                == "string" entries are included in the catalog request.
            user_prompt: The original user prompt (used for LLM context +
                cache key). Truncated to 500 chars for the cache key hash.
            count: Number of values per field (default 50). Catalog is
                rejected and fallback used if any field receives < 40.
            tenant_id, integration_name, user_id: Forwarded to
                model_router.invoke_with_usage for analytics.

        Returns:
            Dict mapping string-typed field name to a list of `count`
            realistic values. Empty dict if `fields` has no string entries.
        """
        # Skip work if no string fields.
        string_fields = [(n, t) for n, t in fields if t == "string"]
        if not string_fields:
            return {}

        # Cache key — entity + sorted-fields-hash + prompt-hash.
        fields_hash = self._hash_fields(string_fields)
        prompt_hash = self._hash_text(user_prompt or "")
        cache_key = f"entity_catalog:{entity_name}:{fields_hash}:{prompt_hash}"

        # L1 cache.
        if cache_key in self.l1_cache:
            logger.debug(f"Entity catalog L1 hit: {cache_key}")
            return self.l1_cache[cache_key].values  # type: ignore[return-value]

        # L2 cache (TTL check).
        if cache_key in self.l2_cache:
            cat = self.l2_cache[cache_key]
            if time.time() - cat.generated_at < self.cache_ttl:
                logger.debug(f"Entity catalog L2 hit: {cache_key}")
                self.l1_cache[cache_key] = cat
                return cat.values  # type: ignore[return-value]

        # Generate via LLM with fallback.
        catalogs = await self._generate_entity_catalogs(
            entity_name=entity_name,
            string_fields=string_fields,
            user_prompt=user_prompt,
            count=count,
            tenant_id=tenant_id,
            integration_name=integration_name,
            user_id=user_id,
        )

        # Wrap in Catalog dataclass for cache uniformity. The `values`
        # field on Catalog is List[str]; we store the dict directly to
        # avoid a parallel cache type — accept the type:ignore.
        cat = Catalog(
            semantic_type=f"entity:{entity_name}",
            domain="general",
            values=catalogs,  # type: ignore[arg-type]
            generated_at=time.time(),
        )
        self.l1_cache[cache_key] = cat
        self.l2_cache[cache_key] = cat

        if len(self.l2_cache) > 1000:
            oldest_key = min(self.l2_cache.keys(), key=lambda k: self.l2_cache[k].generated_at)
            del self.l2_cache[oldest_key]

        return catalogs

    async def _generate_entity_catalogs(
        self,
        entity_name: str,
        string_fields: List[Tuple[str, str]],
        user_prompt: str,
        count: int,
        tenant_id: Optional[str],
        integration_name: Optional[str],
        user_id: Optional[str],
    ) -> Dict[str, List[str]]:
        """Single LLM call. Falls back per-field on any failure."""
        field_lines = "\n".join(f"- {n} ({t})" for n, t in string_fields)
        prompt = self.ENTITY_CATALOG_PROMPT.format(
            count=count,
            entity_name=entity_name,
            user_prompt=(user_prompt or "")[:500],
            field_lines=field_lines,
        )

        try:
            model_name = model_router.select_model_by_task("routing")
            usage_result = await model_router.invoke_with_usage(
                prompt=prompt,
                model_name=model_name,
                tenant_id=tenant_id,
                integration_name=integration_name,
                task_type="datagen_catalog_generation",
                user_id=user_id,
            )
            text = usage_result.content if hasattr(usage_result, "content") else str(usage_result)
            parsed = self._parse_entity_catalogs(text, [n for n, _ in string_fields])
        except Exception as e:
            logger.warning(f"Entity catalog LLM call failed for {entity_name}: {e}")
            parsed = None

        # If parsing failed or any field has < 40 entries, fall back per-field.
        result: Dict[str, List[str]] = {}
        for name, _type in string_fields:
            llm_values = (parsed or {}).get(name) or []
            if len(llm_values) >= 40:
                # Top up to `count` by sampling with replacement from the LLM list
                values = list(llm_values)
                while len(values) < count:
                    values.append(values[len(values) % len(llm_values)])
                result[name] = values[:count]
            else:
                result[name] = self._smart_field_fallback(name, count)
        return result

    def _parse_entity_catalogs(
        self,
        text: str,
        expected_fields: List[str],
    ) -> Optional[Dict[str, List[str]]]:
        """Extract a JSON object of {field: [values]} from LLM output.

        Tolerant of markdown fences and extra prose. Returns None if no
        valid object found.
        """
        import re as _re
        text = (text or "").strip()
        # Strip markdown code fences if present.
        fence = _re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        candidate = fence.group(1) if fence else text
        # Otherwise: locate first { ... last }
        if not fence:
            first = candidate.find("{")
            last = candidate.rfind("}")
            if first == -1 or last == -1 or last < first:
                return None
            candidate = candidate[first:last + 1]
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        # Coerce values: keep only lists of strings (or things stringifiable).
        cleaned: Dict[str, List[str]] = {}
        for name in expected_fields:
            v = obj.get(name)
            if isinstance(v, list):
                cleaned[name] = [str(item) for item in v if item is not None]
        return cleaned

    def _smart_field_fallback(
        self,
        field_name: str,
        count: int,
    ) -> List[str]:
        """Field-name-aware Faker fallback. Returns `count` plausible values
        based on field-name shape — never placeholder garbage like
        `<field>_value_1`.

        Mirrors the logic of SemanticRouter._smart_free_text so the per-row
        fallback path and the catalog fallback path stay consistent.
        """
        from faker import Faker
        fk = Faker()
        fn = (field_name or "").lower()

        if not fn:
            return [fk.word() for _ in range(count)]

        # Detect name-like fields → catch_phrase (product-flavoured)
        name_hints = ("_name", "name_of", "title", "label", "product", "model")
        desc_hints = ("description", "comment", "note", "details", "summary", "bio")

        if any(h in fn for h in name_hints):
            return [fk.catch_phrase() for _ in range(count)]
        if any(h in fn for h in desc_hints):
            return [fk.sentence(nb_words=6) for _ in range(count)]
        if "email" in fn:
            return [fk.email() for _ in range(count)]
        if "phone" in fn:
            return [fk.phone_number() for _ in range(count)]
        if "city" in fn:
            return [fk.city() for _ in range(count)]
        if "country" in fn:
            return [fk.country() for _ in range(count)]
        return [fk.word() for _ in range(count)]

    @staticmethod
    def _hash_fields(string_fields: List[Tuple[str, str]]) -> str:
        body = "|".join(f"{n}:{t}" for n, t in sorted(string_fields))
        return hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha1((text or "")[:500].encode("utf-8")).hexdigest()[:8]

    def clear_cache(self):
        """Clear all caches."""
        self.l1_cache.clear()
        self.l2_cache.clear()
        logger.info("Catalog caches cleared")
