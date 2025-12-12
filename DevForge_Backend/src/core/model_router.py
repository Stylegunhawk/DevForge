"""Model router for intelligent model selection and fallback.

Pre-configured for all 7 models (3 local + 4 cloud).
Ready for Phase 2-3, but not invoked by Phase 1 DataGen.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

from langchain_ollama import ChatOllama

from src.core.config import settings


class ModelType(str, Enum):
    """Model type classification."""

    LOCAL = "local"
    CLOUD = "cloud"


class ModelProfile:
    """Profile for a model configuration."""

    def __init__(
        self,
        name: str,
        model_type: ModelType,
        speed: str,
        cost_per_1k: float,
        best_for: list[str],
        max_tokens: Optional[int] = None,
    ):
        """Initialize model profile.

        Args:
            name: Model identifier (e.g., "qwen3:4b")
            model_type: LOCAL or CLOUD
            speed: Relative speed ("fast", "medium", "slow")
            cost_per_1k: Estimated cost per 1K tokens (USD)
            best_for: List of use cases this model excels at
            max_tokens: Maximum context window (if known)
        """
        self.name = name
        self.model_type = model_type
        self.speed = speed
        self.cost_per_1k = cost_per_1k
        self.best_for = best_for
        self.max_tokens = max_tokens


class ModelRouter:
    """Intelligent model selection and invocation with fallback."""

    def __init__(self):
        """Initialize model router with all configured models."""
        self.profiles: Dict[str, ModelProfile] = {}
        self._initialize_profiles()

    def _initialize_profiles(self) -> None:
        """Initialize model profiles for all 7 models."""
        # Phase 1: Fast local model
        self.profiles[settings.DEFAULT_MODEL] = ModelProfile(
            name=settings.DEFAULT_MODEL,
            model_type=ModelType.LOCAL,
            speed="fast",
            cost_per_1k=0.0,
            best_for=["simple tasks", "data generation", "quick responses"],
            max_tokens=8192,
        )

        # Phase 2: Supervisor router
        self.profiles[settings.SUPERVISOR_MODEL] = ModelProfile(
            name=settings.SUPERVISOR_MODEL,
            model_type=ModelType.LOCAL,
            speed="medium",
            cost_per_1k=0.0,
            best_for=["routing", "classification", "decision making"],
            max_tokens=32768,
        )

        # Phase 3: RAG local
        self.profiles[settings.RAG_LOCAL_MODEL] = ModelProfile(
            name=settings.RAG_LOCAL_MODEL,
            model_type=ModelType.LOCAL,
            speed="medium",
            cost_per_1k=0.0,
            best_for=["RAG", "document understanding", "local privacy"],
            max_tokens=131072,
        )

        # Phase 3: RAG cloud (quality)
        self.profiles[settings.RAG_CLOUD_MODEL] = ModelProfile(
            name=settings.RAG_CLOUD_MODEL,
            model_type=ModelType.CLOUD,
            speed="slow",
            cost_per_1k=0.002,
            best_for=["complex RAG", "deep understanding", "quality"],
            max_tokens=131072,
        )

        # Phase 3: GitHub operations
        self.profiles[settings.GITHUB_MODEL] = ModelProfile(
            name=settings.GITHUB_MODEL,
            model_type=ModelType.CLOUD,
            speed="medium",
            cost_per_1k=0.01,
            best_for=["code generation", "GitHub operations", "long context"],
            max_tokens=262144,
        )

        # Phase 3: Premium reasoning
        self.profiles[settings.PREMIUM_MODEL] = ModelProfile(
            name=settings.PREMIUM_MODEL,
            model_type=ModelType.CLOUD,
            speed="slow",
            cost_per_1k=0.015,
            best_for=["complex reasoning", "deep analysis", "premium tasks"],
            max_tokens=163840,
        )

        # Phase 3: Embedding model (not for chat, but included for completeness)
        self.profiles[settings.EMBEDDING_MODEL] = ModelProfile(
            name=settings.EMBEDDING_MODEL,
            model_type=ModelType.LOCAL,
            speed="fast",
            cost_per_1k=0.0,
            best_for=["embeddings", "vector search"],
            max_tokens=None,
        )

        logging.info(f"Initialized ModelRouter with {len(self.profiles)} models")

    def select_model(self, use_case: str, prefer_local: bool = True) -> str:
        """Select best model for a given use case.

        Args:
            use_case: Description of the task (e.g., "simple data generation")
            prefer_local: If True, prefer local models when suitable

        Returns:
            Model name string
        """
        use_case_lower = use_case.lower()

        # Find models that match the use case
        candidates = []
        for model_name, profile in self.profiles.items():
            # Skip embedding model for chat tasks
            if "embedding" in model_name.lower() and "embedding" not in use_case_lower:
                continue

            # Score based on best_for matches
            score = sum(1 for tag in profile.best_for if tag.lower() in use_case_lower)
            if score > 0:
                candidates.append((score, profile))

        if not candidates:
            # Default fallback
            if prefer_local:
                return settings.DEFAULT_MODEL
            return settings.PREMIUM_MODEL

        # Sort by score (highest first), then by cost (lowest first)
        candidates.sort(key=lambda x: (-x[0], x[1].cost_per_1k))

        selected = candidates[0][1]
        logging.info(
            f"Selected model {selected.name} for use case: {use_case}",
            extra={"use_case": use_case, "model": selected.name},
        )
        return selected.name

    def get_chat_model(self, model_name: str) -> ChatOllama:
        """Get LangChain ChatOllama instance for a model.

        Args:
            model_name: Model identifier

        Returns:
            ChatOllama instance configured for the model
        """
        if model_name not in self.profiles:
            logging.warning(
                f"Model {model_name} not in profiles, using DEFAULT_MODEL",
                extra={"requested_model": model_name, "fallback": settings.DEFAULT_MODEL},
            )
            model_name = settings.DEFAULT_MODEL

        return ChatOllama(
            model=model_name,
            base_url=settings.OLLAMA_HOST,
            temperature=0.7,
        )

    async def invoke_with_fallback(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        use_case: Optional[str] = None,
        fallback_models: Optional[list[str]] = None,
    ) -> str:
        """Invoke model with automatic fallback on failure.

        Args:
            prompt: Input prompt
            model_name: Specific model to use (optional)
            use_case: Description of task for model selection (optional)
            fallback_models: List of fallback models to try (optional)

        Returns:
            Model response string

        Raises:
            Exception: If all models fail
        """
        # Select primary model
        if not model_name:
            if use_case:
                model_name = self.select_model(use_case)
            else:
                model_name = settings.DEFAULT_MODEL

        # Default fallback chain: local -> cloud premium
        if not fallback_models:
            fallback_models = [
                settings.DEFAULT_MODEL,
                settings.SUPERVISOR_MODEL,
                settings.PREMIUM_MODEL,
            ]

        models_to_try = [model_name] + fallback_models

        last_error = None
        for model in models_to_try:
            try:
                chat_model = self.get_chat_model(model)
                logging.info(f"Invoking model: {model}", extra={"model": model, "prompt_length": len(prompt)})
                response = await chat_model.ainvoke(prompt)
                return response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                last_error = e
                logging.warning(
                    f"Model {model} failed, trying next: {str(e)}",
                    extra={"model": model, "error": str(e)},
                )
                continue

        # All models failed
        raise Exception(f"All models failed. Last error: {last_error}") from last_error

    def estimate_cost(self, model_name: str, num_tokens: int) -> float:
        """Estimate cost for a model invocation.

        Args:
            model_name: Model identifier
            num_tokens: Number of tokens

        Returns:
            Estimated cost in USD
        """
        if model_name not in self.profiles:
            return 0.0

        profile = self.profiles[model_name]
        cost = (num_tokens / 1000) * profile.cost_per_1k
        return round(cost, 6)

    def select_model_by_task(self, task_type: str, prefer_local: bool = True) -> str:
        """Select model based on task type for supervisor routing.

        Args:
            task_type: One of "datagen", "routing", "rag_simple", "rag_complex", "code_gen", "premium"
            prefer_local: If True and cloud model specified, try to use local alternative

        Returns:
            Model name string (e.g., "qwen3:4b")

        Raises:
            ValueError: If task_type is not recognized
        """
        # Build task-to-model mapping using settings (dynamic values)
        task_model_map = {
            "datagen": settings.DEFAULT_MODEL,  # qwen3:4b - Fast local for data generation
            "routing": settings.SUPERVISOR_MODEL,  # deepseek-r1:8b - Supervisor intent classification
            "rag_simple": settings.RAG_LOCAL_MODEL,  # gpt-oss:20b - Local RAG queries
            "rag_complex": settings.RAG_CLOUD_MODEL,  # gpt-oss:120b-cloud - Complex RAG (cloud)
            "code_gen": settings.GITHUB_MODEL,  # qwen3-coder:480b-cloud - GitHub code generation
            "github": settings.GITHUB_MODEL,  # Alias for code_gen (GitHub operations)
            "premium": settings.PREMIUM_MODEL,  # deepseek-v3.1:671b-cloud - Ultimate reasoning
        }

        if task_type not in task_model_map:
            valid_types = list(task_model_map.keys())
            raise ValueError(f"Unknown task_type: {task_type}. Valid types: {valid_types}")

        model = task_model_map[task_type]

        # If prefer_local and model is cloud, try to substitute with local alternative
        if prefer_local and "-cloud" in model:
            # Map cloud models to local alternatives
            local_alternatives = {
                settings.RAG_CLOUD_MODEL: settings.RAG_LOCAL_MODEL,  # gpt-oss:120b-cloud -> gpt-oss:20b
                settings.GITHUB_MODEL: settings.DEFAULT_MODEL,  # qwen3-coder:480b-cloud -> qwen3:4b (fallback)
                settings.PREMIUM_MODEL: settings.SUPERVISOR_MODEL,  # deepseek-v3.1:671b-cloud -> deepseek-r1:8b
            }
            alternative = local_alternatives.get(model)
            if alternative:
                model = alternative
                original_model = task_model_map[task_type]
                logging.info(
                    f"Using local alternative: {model} for task: {task_type}",
                    extra={"task_type": task_type, "original_model": original_model, "alternative": model},
                )

        logging.info(
            f"Selected model '{model}' for task type '{task_type}'",
            extra={"task_type": task_type, "model": model, "prefer_local": prefer_local},
        )
        return model

    async def check_model_health(self, model_name: str) -> bool:
        """Check if a model is available and responsive.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is healthy, False otherwise
        """
        try:
            chat_model = self.get_chat_model(model_name)
            # Send minimal test message
            response = await chat_model.ainvoke([{"role": "user", "content": "test"}])
            is_healthy = bool(response)
            if is_healthy:
                logging.debug(f"Health check passed for model '{model_name}'")
            return is_healthy
        except Exception as e:
            logging.warning(
                f"Health check failed for model '{model_name}': {e}",
                extra={"model": model_name, "error": str(e)},
            )
            return False


# Task type to model mapping for supervisor routing (module-level constant)
# Note: Actual values are loaded from settings at runtime in select_model_by_task()
# This serves as documentation of the mapping structure
TASK_MODEL_MAP = {
    "datagen": "qwen3:4b",  # Fast local for data generation
    "routing": "deepseek-r1:8b",  # Supervisor intent classification
    "rag_simple": "gpt-oss:20b",  # Local RAG queries
    "rag_complex": "gpt-oss:120b-cloud",  # Complex RAG (cloud)
    "code_gen": "qwen3-coder:480b-cloud",  # GitHub code generation
    "premium": "deepseek-v3.1:671b-cloud",  # Ultimate reasoning
}

# Global model router instance
model_router = ModelRouter()

