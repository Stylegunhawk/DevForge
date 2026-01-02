"""Tests for commit message generator intelligence component.

Comprehensive tests for AI-powered Conventional Commits generation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agents.github.intelligence.commit_generator import (
    CommitGenerator, CommitMessage, ChangeType, DiffAnalysis
)


class TestChangeType:
    """Test ChangeType enum"""
    
    def test_all_change_types(self):
        """Test all Conventional Commits types"""
        assert ChangeType.FEAT.value == "feat"
        assert ChangeType.FIX.value == "fix"
        assert ChangeType.DOCS.value == "docs"
        assert ChangeType.STYLE.value == "style"
        assert ChangeType.REFACTOR.value == "refactor"
        assert ChangeType.PERF.value == "perf"
        assert ChangeType.TEST.value == "test"
        assert ChangeType.CHORE.value == "chore"
        assert ChangeType.CI.value == "ci"
        assert ChangeType.BUILD.value == "build"


class TestDiffAnalysis:
    """Test DiffAnalysis dataclass"""
    
    def test_diff_analysis_creation(self):
        """Test creating DiffAnalysis"""
        analysis = DiffAnalysis(
            files=["file1.py", "file2.py"],
            additions=10,
            deletions=5,
            summary="2 files changed",
            file_types={"py"}
        )
        
        assert len(analysis.files) == 2
        assert analysis.additions == 10
        assert analysis.deletions == 5
        assert "py" in analysis.file_types


class TestCommitMessage:
    """Test CommitMessage dataclass"""
    
    def test_commit_message_creation(self):
        """Test creating CommitMessage"""
        msg = CommitMessage(
            text="feat(auth): add login endpoint",
            type=ChangeType.FEAT,
            scope="auth",
            description="add login endpoint",
            body=None,
            confidence=0.95
        )
        
        assert msg.type == ChangeType.FEAT
        assert msg.scope == "auth"
        assert msg.confidence == 0.95
    
    def test_to_conventional_format_with_scope(self):
        """Test conventional format with scope"""
        msg = CommitMessage(
            text="",
            type=ChangeType.FEAT,
            scope="auth",
            description="add login endpoint",
            body=None,
            confidence=0.95
        )
        
        result = msg.to_conventional_format()
        
        assert result == "feat(auth): add login endpoint"
    
    def test_to_conventional_format_without_scope(self):
        """Test conventional format without scope"""
        msg = CommitMessage(
            text="",
            type=ChangeType.FIX,
            scope=None,
            description="fix typo",
            body=None,
            confidence=0.90
        )
        
        result = msg.to_conventional_format()
        
        assert result == "fix: fix typo"
    
    def test_to_conventional_format_with_body(self):
        """Test conventional format with body"""
        msg = CommitMessage(
            text="",
            type=ChangeType.FEAT,
            scope="api",
            description="add new endpoint",
            body="This adds a new REST endpoint for user management.",
            confidence=0.95
        )
        
        result = msg.to_conventional_format()
        
        assert "feat(api): add new endpoint" in result
        assert "This adds a new REST endpoint" in result


class TestCommitGenerator:
    """Test CommitGenerator class"""
    
    @pytest.fixture
    def generator(self):
        """Create CommitGenerator with mocked dependencies"""
        with patch('src.agents.github.intelligence.commit_generator.ModelRouter'):
            return CommitGenerator()
    
    def test_analyze_diff_basic(self, generator):
        """Test basic diff analysis"""
        diff = """
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,5 @@
+# New line 1
+# New line 2
 existing line
-removed line
"""
        analysis = generator._analyze_diff(diff)
        
        assert "file1.py" in analysis.files
        assert analysis.additions >= 2
        assert analysis.deletions >= 1
        assert "py" in analysis.file_types
    
    def test_analyze_diff_multiple_files(self, generator):
        """Test diff with multiple files"""
        diff = """
--- a/src/app.py
+++ b/src/app.py
+# new line
--- a/tests/test_app.py
+++ b/tests/test_app.py
+# test line
"""
        analysis = generator._analyze_diff(diff)
        
        assert len(analysis.files) >= 2
    
    def test_infer_change_type_test(self, generator):
        """Infer TEST type for test files"""
        analysis = DiffAnalysis(
            files=["tests/test_auth.py"],
            additions=10,
            deletions=0,
            summary="1 file changed",
            file_types={"py"}
        )
        
        change_type = generator._infer_change_type(analysis)
        
        assert change_type == ChangeType.TEST
    
    def test_infer_change_type_docs(self, generator):
        """Infer DOCS type for documentation files"""
        analysis = DiffAnalysis(
            files=["README.md"],
            additions=5,
            deletions=2,
            summary="1 file changed",
            file_types={"md"}
        )
        
        change_type = generator._infer_change_type(analysis)
        
        assert change_type == ChangeType.DOCS
    
    def test_infer_change_type_ci(self, generator):
        """Infer CI type for CI config files"""
        analysis = DiffAnalysis(
            files=[".github/workflows/ci.yml"],
            additions=10,
            deletions=0,
            summary="1 file changed",
            file_types={"yml"}
        )
        
        change_type = generator._infer_change_type(analysis)
        
        assert change_type == ChangeType.CI
    
    def test_infer_change_type_build(self, generator):
        """Infer BUILD type for dependency files"""
        analysis = DiffAnalysis(
            files=["requirements.txt"],
            additions=3,
            deletions=0,
            summary="1 file changed",
            file_types={"txt"}
        )
        
        change_type = generator._infer_change_type(analysis)
        
        assert change_type == ChangeType.BUILD
    
    def test_infer_change_type_refactor(self, generator):
        """Infer REFACTOR when mostly deletions"""
        analysis = DiffAnalysis(
            files=["src/app.py"],
            additions=5,
            deletions=20,  # More deletions = refactor
            summary="1 file changed",
            file_types={"py"}
        )
        
        change_type = generator._infer_change_type(analysis)
        
        assert change_type == ChangeType.REFACTOR
    
    def test_infer_change_type_feat(self, generator):
        """Infer FEAT when mostly additions"""
        analysis = DiffAnalysis(
            files=["src/new_feature.py"],
            additions=50,
            deletions=5,
            summary="1 file changed",
            file_types={"py"}
        )
        
        change_type = generator._infer_change_type(analysis)
        
        assert change_type == ChangeType.FEAT
    
    def test_parse_llm_response_valid(self, generator):
        """Test parsing valid LLM response"""
        response = "feat(auth): add OAuth2 login support"
        analysis = DiffAnalysis([], 10, 0, "", set())
        
        msg = generator._parse_llm_response(response, ChangeType.FEAT, analysis)
        
        assert msg.type == ChangeType.FEAT
        assert msg.scope == "auth"
        assert msg.description == "add OAuth2 login support"
        assert msg.confidence >= 0.90
    
    def test_parse_llm_response_no_scope(self, generator):
        """Test parsing LLM response without scope"""
        response = "fix: correct typo in config"
        analysis = DiffAnalysis([], 1, 1, "", set())
        
        msg = generator._parse_llm_response(response, ChangeType.FIX, analysis)
        
        assert msg.type == ChangeType.FIX
        assert msg.scope is None
        assert msg.confidence >= 0.85
    
    def test_fallback_generation(self, generator):
        """Test fallback rule-based generation"""
        analysis = DiffAnalysis(
            files=["src/auth/login.py"],
            additions=10,
            deletions=5,
            summary="1 file changed",
            file_types={"py"}
        )
        
        msg = generator._fallback_generation(analysis, ChangeType.FEAT)
        
        assert msg.type == ChangeType.FEAT
        assert msg.confidence == 0.60
        assert "src" in msg.scope or "login" in msg.description
    
    @pytest.mark.asyncio
    async def test_generate_with_feature_disabled(self, generator):
        """Test generation when feature is disabled"""
        with patch('src.agents.github.intelligence.commit_generator.FeatureFlags') as mock_flags:
            mock_flags.is_enabled.return_value = False
            
            msg = await generator.generate("owner/repo", "diff content")
            
            assert msg.type == ChangeType.CHORE
            assert msg.confidence == 0.5
    
    @pytest.mark.asyncio
    async def test_generate_llm_fallback(self, generator):
        """Test fallback when LLM fails"""
        with patch('src.agents.github.intelligence.commit_generator.FeatureFlags') as mock_flags:
            mock_flags.is_enabled.return_value = True
            
            # Make LLM call fail
            generator.model_router.select_model_by_task = AsyncMock(side_effect=Exception("LLM error"))
            
            diff = "+# new line"
            msg = await generator.generate("owner/repo", diff)
            
            # Should use fallback
            assert msg.confidence <= 0.70
