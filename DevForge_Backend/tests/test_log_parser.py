"""Tests for log parser intelligence component.

Comprehensive tests for multi-language stack trace parsing.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agents.github.intelligence.log_parser import LogParser, StackTrace, ParsedIssue, Language


class TestStackTrace:
    """Test StackTrace dataclass"""
    
    def test_stack_trace_creation(self):
        """Test creating StackTrace"""
        trace = StackTrace(
            language=Language.PYTHON,
            error_type="ValueError",
            message="Invalid input",
            file="app.py",
            line=42,
            function="main",
            stack_frames=[],
            raw_trace="sample trace"
        )
        
        assert trace.file == "app.py"
        assert trace.line == 42
        assert trace.function == "main"
        assert trace.language == Language.PYTHON


class TestParsedIssue:
    """Test ParsedIssue dataclass"""
    
    def test_parsed_issue_creation(self):
        """Test creating ParsedIssue"""
        trace = StackTrace(
            language=Language.PYTHON,
            error_type="ValueError",
            message="Invalid input",
            file=None,
            line=None,
            function=None,
            stack_frames=[],
            raw_trace=""
        )
        
        issue = ParsedIssue(
            title="Test Issue",
            body="Issue body",
            labels=["bug"],
            stack_trace=trace,
            root_cause=None
        )
        
        assert issue.title == "Test Issue"
        assert "bug" in issue.labels


class TestLogParser:
    """Test LogParser class"""
    
    @pytest.fixture
    def parser(self):
        """Create LogParser instance"""
        return LogParser()
    
    # Python parsing tests
    def test_parse_python_error(self, parser):
        """Test parsing Python error"""
        log = """
Traceback (most recent call last):
  File "app.py", line 42, in main
    result = process(data)
  File "utils.py", line 15, in process
    return int(value)
ValueError: invalid literal for int() with base 10: 'abc'
"""
        result = parser.parse(log)
        
        assert result.language == "python"
        assert result.error_type == "ValueError"
        assert "invalid literal" in result.message
        assert len(result.stack_trace) >= 2
    
    def test_parse_python_assertion_error(self, parser):
        """Test parsing Python AssertionError"""
        log = """
Traceback (most recent call last):
  File "test_app.py", line 25, in test_case
    assert expected == actual
AssertionError: 'hello' != 'world'
"""
        result = parser.parse(log)
        
        assert result.error_type == "AssertionError"
        assert result.language == "python"
    
    def test_parse_python_import_error(self, parser):
        """Test parsing Python ImportError"""
        log = """
Traceback (most recent call last):
  File "app.py", line 1, in <module>
    from unknown_module import something
ModuleNotFoundError: No module named 'unknown_module'
"""
        result = parser.parse(log)
        
        assert result.error_type in ["ModuleNotFoundError", "ImportError"]
        assert "unknown_module" in result.message
    
    # JavaScript parsing tests
    def test_parse_javascript_error(self, parser):
        """Test parsing JavaScript error"""
        log = """
TypeError: Cannot read properties of undefined (reading 'map')
    at processItems (/app/src/utils.js:42:15)
    at main (/app/src/index.js:10:5)
    at Object.<anonymous> (/app/src/index.js:25:1)
"""
        result = parser.parse(log)
        
        assert result.language == "javascript"
        assert result.error_type == "TypeError"
        assert "undefined" in result.message
        assert len(result.stack_trace) >= 2
    
    def test_parse_javascript_reference_error(self, parser):
        """Test parsing JavaScript ReferenceError"""
        log = """
ReferenceError: variable is not defined
    at eval (eval:1:1)
    at Object.<anonymous> (/app/index.js:5:1)
"""
        result = parser.parse(log)
        
        assert result.error_type == "ReferenceError"
        assert result.language == "javascript"
    
    # Java parsing tests
    def test_parse_java_exception(self, parser):
        """Test parsing Java exception"""
        log = """
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.App.processData(App.java:42)
    at com.example.App.main(App.java:15)
"""
        result = parser.parse(log)
        
        assert result.language == "java"
        assert "NullPointerException" in result.error_type
        assert len(result.stack_trace) >= 2
    
    def test_parse_java_with_caused_by(self, parser):
        """Test parsing Java with Caused by chain"""
        log = """
java.lang.RuntimeException: Failed to process
    at com.example.App.run(App.java:50)
Caused by: java.io.IOException: File not found
    at com.example.IO.read(IO.java:20)
"""
        result = parser.parse(log)
        
        assert result.language == "java"
        # Should identify root cause
        assert "IOException" in str(result.root_cause) or "RuntimeException" in result.error_type
    
    # Go parsing tests
    def test_parse_go_panic(self, parser):
        """Test parsing Go panic"""
        log = """
panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.processItems(...)
    /app/main.go:42 +0x45
main.main()
    /app/main.go:15 +0x25
"""
        result = parser.parse(log)
        
        assert result.language == "go"
        assert "panic" in result.error_type.lower() or "index out of range" in result.message
    
    # Edge cases
    def test_parse_empty_log(self, parser):
        """Test parsing empty log"""
        result = parser.parse("")
        
        assert result.error_type == "unknown"
        assert result.confidence < 0.5
    
    def test_parse_non_error_log(self, parser):
        """Test parsing non-error log"""
        log = """
INFO: Application started
DEBUG: Processing request
INFO: Request completed
"""
        result = parser.parse(log)
        
        # Should have low confidence for non-error logs
        assert result.confidence < 0.7
    
    def test_extract_file_reference(self, parser):
        """Test extracting file references from stack trace"""
        log = """
Traceback (most recent call last):
  File "/app/src/services/auth.py", line 42, in authenticate
    return verify_token(token)
ValueError: Invalid token
"""
        result = parser.parse(log)
        
        assert len(result.stack_trace) >= 1
        assert result.stack_trace[0].file == "/app/src/services/auth.py"
        assert result.stack_trace[0].line == 42
        assert result.stack_trace[0].function == "authenticate"
    
    def test_language_detection_from_file_extension(self, parser):
        """Test language detection from file extension"""
        # Python
        log = "File: test.py - Error occurred"
        result = parser.parse(log)
        assert result.language in ["python", "unknown"]
        
        # JavaScript
        log = "at module.js:10:5"
        result = parser.parse(log)
        assert result.language in ["javascript", "unknown"]
    
    def test_confidence_calculation(self, parser):
        """Test confidence is calculated correctly"""
        # Clear error with stack trace
        python_log = """
Traceback (most recent call last):
  File "app.py", line 1
ValueError: test
"""
        result = parser.parse(python_log)
        assert result.confidence >= 0.7
        
        # Unclear log
        unclear_log = "Something went wrong"
        result = parser.parse(unclear_log)
        assert result.confidence < 0.7


class TestLogParserIntegration:
    """Integration tests for log parser"""
    
    @pytest.fixture
    def parser(self):
        return LogParser()
    
    def test_parse_github_actions_log(self, parser):
        """Test parsing typical GitHub Actions failure log"""
        log = """
Run pytest tests/
============================= test session starts =============================
FAILED tests/test_api.py::test_login - AssertionError: Expected 200, got 401
============================= 1 failed, 10 passed =============================
Error: Process completed with exit code 1.
"""
        result = parser.parse(log)
        
        assert result.error_type in ["AssertionError", "test_failure", "unknown"]
        assert "test" in result.message.lower() or "failed" in result.message.lower()
    
    def test_parse_npm_build_error(self, parser):
        """Test parsing npm build error"""
        log = """
npm ERR! code ELIFECYCLE
npm ERR! errno 1
npm ERR! project@1.0.0 build: `webpack --mode production`
npm ERR! Exit status 1

ERROR in ./src/App.js
Module not found: Error: Can't resolve './Components/Header'
"""
        result = parser.parse(log)
        
        assert "Module" in result.message or "not found" in result.message.lower()
    
    def test_parse_multiline_error(self, parser):
        """Test parsing error spanning multiple lines"""
        log = """
Error: Failed to compile
Details: 
  - File: src/app.tsx
  - Line: 42
  - Column: 15
  - Message: Type 'string' is not assignable to type 'number'
"""
        result = parser.parse(log)
        
        assert "compile" in result.message.lower() or "type" in result.message.lower()
