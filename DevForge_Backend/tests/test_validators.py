"""Unit tests for validators.py

Tests the CheatsheetValidator logic.
"""

import pytest
from src.agents.cheatsheet.validators import CheatsheetValidator, ValidationResult

class TestCheatsheetValidator:
    """Test suite for CheatsheetValidator."""
    
    def setup_method(self):
        self.validator = CheatsheetValidator()
        self.validator.MIN_LENGTH = 50  # Lower limit for easier testing
    
    def test_valid_markdown_passes(self):
        """Test that comprehensive, valid markdown passes validation."""
        markdown = """# Valid Cheatsheet

## Introduction
This is a test.

## Code Example
```python
import os
def hello():
    print("Hello World")
```

## Another Example
```python
x = 1 + 1
```

## Reference Table
| Cmd | Desc |
|-----|------|
| ls  | list |
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is True
        assert len(result.errors) == 0
        assert result.quality_score > 80
        assert result.quality_indicators["syntax_valid"] is True
        assert result.quality_indicators["has_table"] is True

    def test_min_length_failure(self):
        """Test failure on content too short."""
        markdown = "# Short\nToo short."
        # Min length is 50 in setup
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is False
        assert any("content too short" in e.lower() for e in result.errors)

    def test_min_code_blocks_failure(self):
        """Test failure when not enough code blocks."""
        markdown = """# No Code
## Intro
Text but no code blocks.
## Section 2
More text.
## Section 3
Even more text.
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is False
        assert any("insufficient code examples" in e.lower() for e in result.errors)

    def test_min_structure_failure(self):
        """Test failure when headings are missing."""
        markdown = """No headings here.
Just text.
And code:
```python
print("hi")
```
And more code:
```python
print("bye")
```
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is False
        assert any("poor structure" in e.lower() for e in result.errors)

    def test_syntax_error_detection(self):
        """Test detection of invalid Python syntax."""
        markdown = """# Syntax Error
## Bad Code
```python
def broken_function(
    print("Missing closing parenthesis")
```
## Good code
```python
x = 1
```
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is False
        assert len(result.errors) > 0
        assert any("syntax error" in e.lower() for e in result.errors)
        assert result.quality_indicators["syntax_valid"] is False

    def test_no_syntax_check_for_other_languages(self):
        """Test that syntax errors in non-python blocks don't fail validation (feature not implemented yet)."""
        markdown = """# Bash Cheatsheet
## Example
```bash
if [ -z "$VAR" ]; then
    echo "This is valid bash but not python"
fi
```
## Example 2
```text
Some text
```
"""
        # Validator currently only checks Python syntax
        result = self.validator.validate(markdown, "query", "bash")
        assert result.passed is True  # Should pass as we ignore bash syntax

    def test_hallucinated_import_detection(self):
        """Test detection of unknown/hallucinated imports."""
        markdown = """# Hallucination
## Fake Import
```python
import non_existent_package_xyz
import os
```
## Another One
```python
from super_fake_lib import magic
```
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is False
        assert any("hallucinated imports" in e.lower() for e in result.errors)
        assert "non_existent_package_xyz" in result.errors[0] or "super_fake_lib" in result.errors[0]

    def test_known_imports_pass(self):
        """Test that known standard and common libs pass."""
        markdown = """# Good Imports
## Imports
```python
import os
import pandas as pd
from typing import List
import langchain
```
## More code
```python
x=1
```
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is True

    def test_warnings_generated(self):
        """Test that warnings are generated for missing table etc."""
        markdown = """# No Table
## Code 1
```python
x=1
```
## Code 2
```python
y=2
```
## Code 3
```python
z=3
```
## Code 4
```python
a=4
```
"""
        result = self.validator.validate(markdown, "query", "python")
        assert result.passed is True  # Warnings don't fail validation
        assert any("no reference table" in w.lower() for w in result.warnings)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
