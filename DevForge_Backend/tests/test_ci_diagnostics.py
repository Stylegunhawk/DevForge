"""Tests for CI diagnostics tool.

Tests pattern detection, auto-fix policy, and LLM integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.tools.ci_diagnostics import CIAnalyzer, analyze_ci_failure_invoke, FailurePattern


class TestCIAnalyzer:
    """Test CI failure analyzer"""
    
    @pytest.mark.asyncio
    async def test_analyze_success(self):
        """Test successful CI analysis"""
        analyzer = CIAnalyzer()
        
        with patch.object(analyzer, '_fetch_logs') as mock_logs:
            mock_logs.return_value = "FAILED test_auth.py::test_login\nAssertionError: expected True"
            
            with patch.object(analyzer, '_suggest_fixes') as mock_fixes:
                from src.tools.ci_diagnostics import SuggestedFix
                mock_fixes.return_value = [
                    SuggestedFix(
                        title="Fix login test",
                        description="Update test expectations",
                        confidence=0.9,
                        auto_fixable=False,
                        commands=None,
                        file_changes=None
                    )
                ]
                
                result = await analyzer.analyze(
repo="user/test-repo",
                    run_id=12345
                )
                
                assert result["success"] is True
                assert len(result["failures"]) > 0
                assert len(result["suggested_fixes"]) == 1
                assert "audit_id" in result
    
    def test_extract_test_failures(self):
        """Test extracting test failure patterns"""
        analyzer = CIAnalyzer()
        
        logs = """
        FAILED tests/test_auth.py::test_login - AssertionError: Login failed
        ERROR tests/test_db.py::test_connection - Connection refused
        """
        
        failures = analyzer._extract_failure_patterns(logs)
        
        assert len(failures) >= 2
        assert any(f.type == "test_failure" for f in failures)
    
    def test_extract_build_errors(self):
        """Test extracting build errors"""
        analyzer = CIAnalyzer()
        
        logs = "error: command failed with exit code 1\nfatal: repository not found"
        
        failures = analyzer._extract_failure_patterns(logs)
        
        assert any(f.type == "build_error" for f in failures)
        assert any(f.severity == "critical" for f in failures)
    
    def test_extract_dependency_issues(self):
        """Test detecting dependency issues"""
        analyzer = CIAnalyzer()
        
        logs = "ModuleNotFoundError: No module named 'requests'"
        
        failures = analyzer._extract_failure_patterns(logs)
        
        assert any(f.type == "dependency_issue" for f in failures)
    
    def test_extract_timeout(self):
        """Test detecting timeout issues"""
        analyzer = CIAnalyzer()
        
        logs = "Error: The operation timed out after 300 seconds"
        
        failures = analyzer._extract_failure_patterns(logs)
        
        assert any(f.type == "timeout" for f in failures)
    
    @pytest.mark.asyncio
    async def test_auto_fix_policy_enforcement(self):
        """Test auto-fix policy is correctly enforced"""
        analyzer = CIAnalyzer()
        
        failures = [
            FailurePattern(
                type="test_failure",
                message="Lint error: line too long",
                line=42,
                file="app.py",
                severity="low"
            )
        ]
        
        logs = "lint error on line 42"
        
        with patch('src.tools.ci_diagnostics.ModelRouter') as mock_router:
            mock_instance = AsyncMock()
            mock_instance.select_model_by_task.return_value = "test-model"
            mock_instance.invoke_with_fallback.return_value = '''[
                {
                    "title": "Fix lint error",
                    "description": "Shorten line 42",
                    "confidence": 0.96,
                    "type": "lint",
                    "commands": ["black app.py"]
                }
            ]'''
            mock_router.return_value = mock_instance
            
            fixes = await analyzer._suggest_fixes(failures, logs)
            
            # Should be auto-fixable: confidence 0.96 >= 0.95 AND type=lint
            assert len(fixes) == 1
            assert fixes[0].auto_fixable is True
            assert fixes[0].confidence == 0.96
    
    @pytest.mark.asyncio
    async def test_auto_fix_policy_low_confidence(self):
        """Test auto-fix rejected for low confidence"""
        analyzer = CIAnalyzer()
        
        failures = [FailurePattern("test_failure", "test failed", None, None, "high")]
        
        with patch('src.tools.ci_diagnostics.ModelRouter') as mock_router:
            mock_instance = AsyncMock()
            mock_instance.select_model_by_task.return_value = "test-model"
            mock_instance.invoke_with_fallback.return_value = '''[
                {
                    "title": "Fix test",
                    "description": "Update test",
                    "confidence": 0.80,
                    "type": "lint",
                    "commands": []
                }
            ]'''
            mock_router.return_value = mock_instance
            
            fixes = await analyzer._suggest_fixes(failures, "logs")
            
            # Should NOT be auto-fixable: confidence 0.80 < 0.95
            assert fixes[0].auto_fixable is False
    
    @pytest.mark.asyncio
    async def test_auto_fix_policy_wrong_type(self):
        """Test auto-fix rejected for non-allowed type"""
        analyzer = CIAnalyzer()
        
        failures = [FailurePattern("test_failure", "test failed", None, None, "high")]
        
        with patch('src.tools.ci_diagnostics.ModelRouter') as mock_router:
            mock_instance = AsyncMock()
            mock_instance.select_model_by_task.return_value = "test-model"
            mock_instance.invoke_with_fallback.return_value = '''[
                {
                    "title": "Fix test",
                    "description": "Rewrite logic",
                    "confidence": 0.97,
                    "type": "code_change",
                    "commands": []
                }
            ]'''
            mock_router.return_value = mock_instance
            
            fixes = await analyzer._suggest_fixes(failures, "logs")
            
            # Should NOT be auto-fixable: type=code_change not in allowed list
            assert fixes[0].auto_fixable is False
    
    def test_fallback_fixes(self):
        """Test fallback fix suggestions"""
        analyzer = CIAnalyzer()
        
        failures = [
            FailurePattern("dependency_issue", "missing module", None, None, "high")
        ]
        
        fixes = analyzer._get_fallback_fixes(failures)
        
        assert len(fixes) > 0
        assert any("dependencies" in f.title.lower() for f in fixes)
    
    @pytest.mark.asyncio
    async def test_analyze_no_failures_found(self):
        """Test analysis when no failures detected"""
        analyzer = CIAnalyzer()
        
        with patch.object(analyzer, '_fetch_logs') as mock_logs:
            mock_logs.return_value = "All tests passed successfully"
            
            result = await analyzer.analyze(
                repo="user/repo",
                run_id=123
            )
            
            assert result["success"] is True
            assert len(result["failures"]) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_api_error(self):
        """Test handling GitHub API errors"""
        analyzer = CIAnalyzer()
        
        with patch.object(analyzer, '_fetch_logs') as mock_logs:
            mock_logs.side_effect = Exception("API rate limit exceeded")
            
            result = await analyzer.analyze(
                repo="user/repo"
            )
            
            assert result["success"] is False
            assert "error" in result


@pytest.mark.asyncio
async def test_ci_diagnostics_invoke():
    """Test API invoke function"""
    with patch('src.tools.ci_diagnostics.CIAnalyzer') as MockAnalyzer:
        mock_instance = AsyncMock()
        mock_instance.analyze.return_value = {
            "success": True,
            "failures": [],
            "suggested_fixes": []
        }
        MockAnalyzer.return_value = mock_instance
        
        result = await analyze_ci_failure_invoke({
            "repo": "user/repo",
            "run_id": 123
        })
        
        assert result["success"] is True
