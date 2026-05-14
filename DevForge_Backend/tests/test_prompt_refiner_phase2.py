"""Tests for refined Phase 2 implementation (deterministic confidence)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.prompt_refiner.dependency_analyzer import DependencyAnalyzer
from src.agents.prompt_refiner.sanitizer import Sanitizer
from src.agents.prompt_refiner.enhancer import PromptEnhancer
from src.agents.prompt_refiner.context_types import Evidence, ChosenStack, CodeContext, ConversationContext


class TestDependencyAnalyzerWithEvidence:
    """Test dependency analyzer returns Evidence objects."""

    def test_parse_requirements_returns_evidence(self):
        analyzer = DependencyAnalyzer()
        files = {"requirements.txt": "fastapi==0.100.0\nsqlalchemy"}
        
        evidence = analyzer.analyze(files)
        
        assert len(evidence) > 0
        assert all(isinstance(e, Evidence) for e in evidence)
        
        # Find FastAPI evidence
        fastapi_evidence = [e for e in evidence if e.match == "FastAPI"]
        assert len(fastapi_evidence) == 1
        assert fastapi_evidence[0].source == "dependency_analysis"
        assert fastapi_evidence[0].weight == 0.9
        assert fastapi_evidence[0].file == "requirements.txt"
        assert fastapi_evidence[0].line == 1


class TestSanitizerWithLog:
    """Test sanitizer returns tuple with log."""

    def test_sanitize_returns_tuple(self):
        sanitizer = Sanitizer()
        text = "api_key = 'secret123abc'"
        
        sanitized, log = sanitizer.sanitize(text)
        
        assert isinstance(sanitized, str)
        assert isinstance(log, list)
        assert "[REDACTED]" in sanitized
        assert "secret123abc" not in sanitized
        
        # Check log contains metadata
        assert len(log) > 0
        assert log[0]["type"] == "secret_redacted"
        assert "secret123abc" not in str(log)  # Should NEVER contain actual secret


class TestEnhancerDeterministicConfidence:
    """Test enhancer computes deterministic confidence."""

    @pytest.mark.asyncio
    async def test_dependency_beats_conversation(self):
        """Test that dependency evidence has higher priority than conversation."""
        enhancer = PromptEnhancer()
        
        # Create context with conversation saying "Django"
        context = CodeContext()
        context.conversation = ConversationContext()
        context.conversation.technologies = ["Django"]
        
        # But project files say FastAPI
        project_files = {
            "requirements.txt": "fastapi==0.100.0"
        }
        
        # Call the evidence gathering logic directly
        dep_evidence = enhancer.dependency_analyzer.analyze(project_files)
        conv_evidence = enhancer._extract_conversation_evidence(context)
        
        all_evidence = dep_evidence + conv_evidence
        chosen_stack = enhancer._build_chosen_stack(all_evidence)
        
        # Assert dependency evidence wins
        assert chosen_stack.source == "dependency_analysis"
        assert "FastAPI" in chosen_stack.frameworks
        assert chosen_stack.confidence > 0.5  # Should be confident
        
        # Django should also be present but FastAPI should be first (higher weight)
        if "Django" in chosen_stack.frameworks:
            frameworks_list = chosen_stack.frameworks
            fastapi_idx = frameworks_list.index("FastAPI") if "FastAPI" in frameworks_list else -1
            django_idx = frameworks_list.index("Django") if "Django" in frameworks_list else -1
            # FastAPI should come before Django in sorted list (alphabetically)
            # But more importantly, source should be dependency_analysis
            assert chosen_stack.source == "dependency_analysis"
        
        # Verify evidence is present
        assert len(chosen_stack.evidence) > 0
        dep_ev = [e for e in chosen_stack.evidence if e.source == "dependency_analysis"]
        assert len(dep_ev) > 0
        assert dep_ev[0].weight > 0.8  # Dependency evidence should be high weight

    @pytest.mark.asyncio
    async def test_formatted_prompt_contains_evidence_block(self):
        """Test that generated prompt includes EVIDENCE block.

        v0.10: enhancer awaits ``model_router.invoke_with_usage(...)``, not
        ``get_chat_model().ainvoke()``. The mock must target that surface so
        the formatted prompt can be captured from the call args.
        """
        from src.core.model_router import UsageMetadata, UsageResult

        enhancer = PromptEnhancer()

        context = CodeContext()
        project_files = {"requirements.txt": "fastapi==0.100.0"}

        mock_invoke = AsyncMock(
            return_value=UsageResult(
                content="Mocked refined prompt",
                model_name="test-model",
                usage=UsageMetadata(),
            )
        )

        with patch('src.agents.prompt_refiner.enhancer.model_router') as mock_router:
            mock_router.select_model_by_task.return_value = "test-model"
            mock_router.invoke_with_usage = mock_invoke

            result = await enhancer.enhance(
                prompt="add authentication",
                domain="code",
                code_context=context,
                project_files=project_files
            )

            # Check that the LLM call surface was invoked
            assert mock_invoke.called

            # The formatted prompt is passed as the `prompt` kwarg
            call_kwargs = mock_invoke.call_args.kwargs
            formatted_prompt = call_kwargs.get("prompt") or mock_invoke.call_args.args[0]

            # Assert EVIDENCE block is present
            assert "EVIDENCE:" in formatted_prompt
            assert "FastAPI" in formatted_prompt
            assert "STRICT RULE" in formatted_prompt

            # Assert chosen_stack is present with v0.10 typed lists
            assert "chosen_stack" in result
            assert result["chosen_stack"]["source"] == "dependency_analysis"
            assert "FastAPI" in result["chosen_stack"]["frameworks"]

            # v0.10: quality block should be present
            assert "quality" in result
            assert result["quality"]["prompt_grounding"] in {"low", "medium", "high"}


class TestChosenStackSchema:
    """Test ChosenStack always present with full schema."""

    def test_empty_stack_has_full_schema(self):
        """Test that even empty stack has all fields (v0.10: typed lists)."""
        stack = ChosenStack()
        stack_dict = stack.to_dict()

        # v0.9 fields (preserved for back-compat)
        assert "language" in stack_dict
        assert "frameworks" in stack_dict
        assert "database" in stack_dict
        assert "source" in stack_dict
        assert "confidence" in stack_dict
        assert "evidence" in stack_dict

        # v0.10 typed lists
        for key in ("languages", "libraries", "services", "databases"):
            assert key in stack_dict, f"v0.10 typed list {key!r} missing from to_dict()"
            assert isinstance(stack_dict[key], list)

        assert stack_dict["language"] == "unknown"
        assert stack_dict["source"] == "none"
        assert stack_dict["confidence"] == 0.0
        assert isinstance(stack_dict["frameworks"], list)
        assert isinstance(stack_dict["evidence"], list)


# ---------------------------------------------------------------------------
# v0.10: Category routing + polyglot + anti-hallucination
# ---------------------------------------------------------------------------

class TestCategoryRouting:
    """v0.10: services/databases must not leak into chosen_stack.frameworks."""

    def test_aws_from_conversation_goes_to_services_not_frameworks(self):
        enhancer = PromptEnhancer()
        ctx = CodeContext()
        ctx.conversation = ConversationContext(
            technologies=["FastAPI", "AWS", "PostgreSQL", "Redis"]
        )

        conv_evidence = enhancer._extract_conversation_evidence(ctx)
        stack = enhancer._build_chosen_stack(conv_evidence)

        # Frameworks list stays clean
        assert stack.frameworks == ["FastAPI"]
        # Services and databases populated separately
        assert "AWS" in stack.services
        assert "Redis" in stack.services
        assert stack.databases == ["PostgreSQL"]

    def test_database_field_picks_first_alphabetically(self):
        enhancer = PromptEnhancer()
        ctx = CodeContext()
        ctx.conversation = ConversationContext(
            technologies=["PostgreSQL", "MySQL"]
        )
        stack = enhancer._build_chosen_stack(
            enhancer._extract_conversation_evidence(ctx)
        )
        # databases list sorted; primary `database` field is the first
        assert stack.databases == ["MySQL", "PostgreSQL"]
        assert stack.database == "MySQL"


class TestPolyglotLanguageDetection:
    """v0.10: language picker honors highest-weighted evidence across all
    ecosystems, not just Python vs JS."""

    def test_go_only_evidence_picks_go(self):
        from src.agents.prompt_refiner.dependency_analyzer import DependencyAnalyzer
        enhancer = PromptEnhancer()
        evidence = DependencyAnalyzer().analyze({
            "go.mod": "module x\nrequire github.com/gin-gonic/gin v1.9.0\n",
        })
        stack = enhancer._build_chosen_stack(evidence)
        assert stack.language == "go"
        assert "Gin" in stack.frameworks

    def test_polyglot_picks_highest_weighted_language(self):
        """Cargo.toml axum (rust, 0.9) + go.mod cobra (go, 0.8) → rust wins."""
        from src.agents.prompt_refiner.dependency_analyzer import DependencyAnalyzer
        enhancer = PromptEnhancer()
        evidence = DependencyAnalyzer().analyze({
            "Cargo.toml": "[dependencies]\naxum = \"0.7\"",
            "go.mod": "module x\nrequire github.com/spf13/cobra v1.8.0",
        })
        stack = enhancer._build_chosen_stack(evidence)
        assert stack.language == "rust", \
            f"axum (0.9) should outweigh cobra (0.8); got {stack.language}"

    def test_rust_libraries_categorized_correctly(self):
        from src.agents.prompt_refiner.dependency_analyzer import DependencyAnalyzer
        enhancer = PromptEnhancer()
        evidence = DependencyAnalyzer().analyze({
            "Cargo.toml": "[dependencies]\naxum = \"0.7\"\ntokio = \"1.0\"\nserde = \"1.0\"\n",
        })
        stack = enhancer._build_chosen_stack(evidence)
        assert stack.frameworks == ["Axum"]
        assert set(stack.libraries) == {"Serde", "Tokio"}


class TestLowGroundingTemplateSelection:
    """v0.10: vague code prompts must NOT trigger the strict EVIDENCE template
    — they should land on the soft clarifying-questions template instead."""

    @pytest.mark.asyncio
    async def test_vague_code_prompt_selects_low_grounding_template(self):
        """'refactor' with domain='code' and no context → code_low_grounding."""
        from src.core.model_router import UsageMetadata, UsageResult

        enhancer = PromptEnhancer()

        mock_invoke = AsyncMock(
            return_value=UsageResult(
                content="(clarifying questions)",
                model_name="test-model",
                usage=UsageMetadata(),
            )
        )
        with patch('src.agents.prompt_refiner.enhancer.model_router') as mock_router:
            mock_router.select_model_by_task.return_value = "test-model"
            mock_router.invoke_with_usage = mock_invoke

            result = await enhancer.enhance(
                prompt="refactor",
                domain="code",
                code_context=None,
                project_files=None,
            )

        # The formatted prompt sent to the LLM must come from the
        # CODE_TEMPLATE_LOW_GROUNDING template — its signature phrase is
        # "did not provide enough information". The strict EVIDENCE template
        # must NOT be selected.
        formatted = mock_invoke.call_args.kwargs.get("prompt") \
            or mock_invoke.call_args.args[0]
        assert "did not provide enough information" in formatted
        assert "EVIDENCE:" not in formatted
        assert "STRICT RULE" not in formatted

        # Quality block confirms low grounding
        assert result["quality"]["prompt_grounding"] == "low"

    @pytest.mark.asyncio
    async def test_well_grounded_code_prompt_still_uses_strict_template(self):
        """Sanity check: high-confidence path still gets EVIDENCE template."""
        from src.core.model_router import UsageMetadata, UsageResult

        enhancer = PromptEnhancer()
        mock_invoke = AsyncMock(
            return_value=UsageResult(
                content="(refined)",
                model_name="test-model",
                usage=UsageMetadata(),
            )
        )
        with patch('src.agents.prompt_refiner.enhancer.model_router') as mock_router:
            mock_router.select_model_by_task.return_value = "test-model"
            mock_router.invoke_with_usage = mock_invoke

            await enhancer.enhance(
                prompt="implement OAuth2 with PKCE for our FastAPI service",
                domain="code",
                code_context=None,
                project_files={"requirements.txt": "fastapi==0.110\nsqlalchemy==2.0"},
            )

        formatted = mock_invoke.call_args.kwargs.get("prompt") \
            or mock_invoke.call_args.args[0]
        assert "EVIDENCE:" in formatted
        assert "STRICT RULE" in formatted
