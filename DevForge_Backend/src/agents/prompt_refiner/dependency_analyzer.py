"""Dependency analyzer for identifying project tech stack.

Parses requirements.txt and package.json to detect frameworks and libraries.
"""

import json
import re
import logging
from typing import Dict, List, Any
from src.agents.prompt_refiner.context_types import Evidence

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """Analyzes project dependencies to detect tech stack."""

    # Mapping of package names to technology identifiers with weights
    PACKAGE_MAP = {
        # Python
        "fastapi": {"name": "FastAPI", "type": "framework", "language": "python", "weight": 0.9},
        "flask": {"name": "Flask", "type": "framework", "language": "python", "weight": 0.9},
        "django": {"name": "Django", "type": "framework", "language": "python", "weight": 0.9},
        "sqlalchemy": {"name": "SQLAlchemy", "type": "library", "language": "python", "weight": 0.7},
        "pandas": {"name": "Pandas", "type": "library", "language": "python", "weight": 0.6},
        "pytest": {"name": "Pytest", "type": "library", "language": "python", "weight": 0.5},
        
        # JavaScript/Node
        "react": {"name": "React", "type": "framework", "language": "javascript", "weight": 0.9},
        "vue": {"name": "Vue.js", "type": "framework", "language": "javascript", "weight": 0.9},
        "next": {"name": "Next.js", "type": "framework", "language": "javascript", "weight": 0.9},
        "express": {"name": "Express.js", "type": "framework", "language": "javascript", "weight": 0.9},
        "typescript": {"name": "TypeScript", "type": "language", "language": "typescript", "weight": 0.8},
    }

    def analyze(self, files: Dict[str, str]) -> List[Evidence]:
        """Analyze dependency files to extract tech stack evidence.
        
        Args:
            files: Dictionary of filename -> content
            
        Returns:
            List of Evidence objects
        """
        evidence_list = []

        for filename, content in files.items():
            if filename.endswith("requirements.txt"):
                evidence_list.extend(self._parse_requirements(content, filename))
            elif filename.endswith("package.json"):
                evidence_list.extend(self._parse_package_json(content, filename))

        return evidence_list

    def _parse_requirements(self, content: str, filename: str) -> List[Evidence]:
        """Parse Python requirements.txt content."""
        evidence_list = []
        lines = content.splitlines()
        
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            # Extract package name (ignore version specifiers)
            match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
            if match:
                pkg_name = match.group(1).lower()
                info = self.PACKAGE_MAP.get(pkg_name)
                
                if info:
                    evidence_list.append(Evidence(
                        source="dependency_analysis",
                        file=filename,
                        line=line_num,
                        excerpt=line[:50],
                        match=info["name"],
                        weight=info["weight"],
                        confidence_hint="strong"
                    ))
        
        return evidence_list

    def _parse_package_json(self, content: str, filename: str) -> List[Evidence]:
        """Parse Node.js package.json content."""
        evidence_list = []
        
        try:
            data = json.loads(content)
            
            # Check dependencies and devDependencies
            for section in ["dependencies", "devDependencies"]:
                if section in data:
                    for pkg_name in data[section].keys():
                        info = self.PACKAGE_MAP.get(pkg_name.lower())
                        
                        if info:
                            evidence_list.append(Evidence(
                                source="dependency_analysis",
                                file=filename,
                                line=None,  # JSON doesn't have meaningful line numbers
                                excerpt=f'"{pkg_name}": "{data[section][pkg_name]}"',
                                match=info["name"],
                                weight=info["weight"],
                                confidence_hint="strong"
                            ))
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse {filename}")
        
        return evidence_list
