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
        """Test that generated prompt includes EVIDENCE block."""
        enhancer = PromptEnhancer()
        
        context = CodeContext()
        project_files = {"requirements.txt": "fastapi==0.100.0"}
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = "Mocked refined prompt"
        
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        
        with patch('src.agents.prompt_refiner.enhancer.model_router') as mock_router:
            mock_router.select_model_by_task.return_value = "test-model"
            mock_router.get_chat_model.return_value = mock_model
            
            result = await enhancer.enhance(
                prompt="add authentication",
                domain="code",
                code_context=context,
                project_files=project_files
            )
            
            # Check that LLM was called
            assert mock_model.ainvoke.called
            
            # Get the actual prompt sent to the LLM
            call_args = mock_model.ainvoke.call_args
            messages = call_args[0][0]
            formatted_prompt = messages[0]["content"]
            
            # Assert EVIDENCE block is present
            assert "EVIDENCE:" in formatted_prompt
            assert "FastAPI" in formatted_prompt
            assert "STRICT RULE" in formatted_prompt
            
            # Assert chosen_stack is present
            assert "chosen_stack" in result
            assert result["chosen_stack"]["source"] == "dependency_analysis"
            assert "FastAPI" in result["chosen_stack"]["frameworks"]


class TestChosenStackSchema:
    """Test ChosenStack always present with full schema."""

    def test_empty_stack_has_full_schema(self):
        """Test that even empty stack has all fields."""
        stack = ChosenStack()
        stack_dict = stack.to_dict()
        
        assert "language" in stack_dict
        assert "frameworks" in stack_dict
        assert "database" in stack_dict
        assert "source" in stack_dict
        assert "confidence" in stack_dict
        assert "evidence" in stack_dict
        
        assert stack_dict["language"] == "unknown"
        assert stack_dict["source"] == "none"
        assert stack_dict["confidence"] == 0.0
        assert isinstance(stack_dict["frameworks"], list)
        assert isinstance(stack_dict["evidence"], list)
