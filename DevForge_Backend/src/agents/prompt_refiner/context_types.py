"""Data structures for context-aware code refinement.

Type definitions for conversation context, code structure, evidence, and chosen stack.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class Evidence:
    """Evidence for a detected technology or framework.
    
    Attributes:
        source: Where the evidence came from (file, conversation, code)
        file: Optional filename
        line: Optional line number
        excerpt: Brief text excerpt showing the match
        match: What was matched (e.g., "fastapi", "React")
        weight: Confidence weight (0.0-1.0)
        confidence_hint: Optional descriptor (e.g., "strong", "weak")
    """
    source: str
    match: str
    weight: float
    file: Optional[str] = None
    line: Optional[int] = None
    excerpt: Optional[str] = None
    confidence_hint: Optional[str] = None


@dataclass
class ChosenStack:
    """The definitively selected tech stack with provenance.
    
    Attributes:
        language: Detected language (e.g., "python", "javascript")
        frameworks: List of detected frameworks
        database: Detected database (if any)
        source: Primary source of detection (dependency_analysis, code_analysis, conversation, none)
        confidence: Deterministic confidence score (0.0-1.0)
        evidence: List of Evidence objects supporting the selection
    """
    language: str = "unknown"
    frameworks: List[str] = field(default_factory=list)
    database: str = "unknown"
    source: str = "none"
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "language": self.language,
            "frameworks": self.frameworks,
            "database": self.database,
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "evidence": [
                {
                    "source": e.source,
                    "match": e.match,
                    "weight": e.weight,
                    "file": e.file,
                    "line": e.line,
                    "excerpt": e.excerpt,
                    "confidence_hint": e.confidence_hint
                }
                for e in self.evidence
            ]
        }


@dataclass
class ConversationContext:
    """Context extracted from conversation history.
    
    Attributes:
        project_type: Type of project (e.g., "FastAPI REST API", "React SPA")
        technologies: List of detected technologies/frameworks
        recent_work: Summary of recent work mentioned
        preferences: User preferences (async, testing, style)
    """
    project_type: str = "Unknown"
    technologies: List[str] = field(default_factory=list)
    recent_work: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeStructure:
    """Structure extracted from code files.
    
    Attributes:
        language: Detected programming language
        classes: List of class names
        functions: List of function names
        imports: List of import statements
        patterns: Detected code patterns (e.g., "async", "decorators")
        conventions: Coding conventions (naming, style)
    """
    language: str = "python"
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    conventions: Dict[str, str] = field(default_factory=dict)


@dataclass
class CodeContext:
    """Unified context combining all analysis results.
    
    Attributes:
        conversation: Context from conversation history
        code_structure: Structure from code files
        detected_language: Primary programming language
        frameworks: Detected frameworks
        recent_context: Summary of recent conversation
    """
    conversation: ConversationContext = field(default_factory=ConversationContext)
    code_structure: CodeStructure = field(default_factory=CodeStructure)
    detected_language: str = "python"
    frameworks: List[str] = field(default_factory=list)
    recent_context: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM prompts."""
        return {
            "project_type": self.conversation.project_type,
            "technologies": self.conversation.technologies,
            "recent_work": self.conversation.recent_work,
            "preferences": self.conversation.preferences,
            "language": self.detected_language,
            "frameworks": self.frameworks,
            "classes": self.code_structure.classes,
            "functions": self.code_structure.functions,
            "imports": self.code_structure.imports[:10],  # Limit to first 10
            "patterns": self.code_structure.patterns,
            "conventions": self.code_structure.conventions,
            "recent_context": self.recent_context,
        }
    
    def has_context(self) -> bool:
        """Check if meaningful context was gathered."""
        return (
            len(self.conversation.technologies) > 0 or
            len(self.code_structure.classes) > 0 or
            len(self.code_structure.functions) > 0 or
            len(self.frameworks) > 0
        )
