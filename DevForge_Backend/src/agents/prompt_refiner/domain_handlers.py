"""Domain configurations for Prompt Refiner Agent."""

from typing import Dict, List, TypedDict


class DomainConfig(TypedDict):
    """Configuration for a specific domain."""
    fields: List[str]
    models: List[str]
    max_tokens: int
    description: str


DOMAIN_CONFIGS: Dict[str, DomainConfig] = {
    "image": {
        "fields": ["style", "lighting", "composition", "quality", "resolution", "subject_details"],
        "models": ["stable-diffusion", "midjourney", "nano-banana"],
        "max_tokens": 500,
        "description": "Generates detailed visual descriptions for image generation tools.",
    },
    "code": {
        "fields": ["language", "framework", "patterns", "testing", "documentation", "requirements"],
        "models": ["cursor", "copilot", "claude", "gpt-oss"],
        "max_tokens": 1000,
        "description": "Generates production-ready coding instructions and specifications.",
    },
    "rag": {
        "fields": ["context_needed", "implementation_detail", "file_structure", "errors", "search_keywords"],
        "models": ["gpt-oss:120b-cloud"],
        "max_tokens": 2000,
        "description": "Optimizes queries for retrieval-augmented generation and context searching.",
    },
    "llm": {
        "fields": ["clarity", "structure", "examples", "constraints", "persona"],
        "models": ["all"],
        "max_tokens": 800,
        "description": "Refines general prompts for better LLM reasoning and output quality.",
    },
}
