"""Unit tests for domain_detector.py

Tests the routing logic for template vs LLM path selection.
"""

import pytest
from src.agents.cheatsheet.domain_detector import DomainDetector


class TestDomainDetector:
    """Test suite for DomainDetector routing logic."""
    
    def setup_method(self):
        """Initialize detector for each test."""
        self.detector = DomainDetector()
    
    # ==================== UNSUPPORTED LANGUAGE TESTS ====================
    
    def test_sql_query_routes_to_llm(self):
        """SQL query should route to LLM (no template exists)."""
        should_llm, reason = self.detector.should_use_llm(
            query="sql basic queries",
            code_context="",
            detected_libraries=[],
            language="sql"
        )
        
        assert should_llm is True
        assert reason == "unsupported_language:sql"
    
    def test_sql_with_code_routes_to_llm(self):
        """SQL code with SELECT/FROM keywords should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="SELECT name, age FROM users WHERE age > 18",
            detected_libraries=[],
            language="sql"
        )
        
        assert should_llm is True
        assert reason == "unsupported_language:sql"
    
    def test_rust_code_routes_to_llm(self):
        """Rust code with fn/impl keywords should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="rust basics",
            code_context="fn main() { let mut x = 5; }",
            detected_libraries=[],
            language="rust"
        )
        
        assert should_llm is True
        assert reason.startswith("unsupported_language:rust")
    
    def test_go_code_routes_to_llm(self):
        """Go code with package/func keywords should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="package main\nfunc hello() {}",
            detected_libraries=[],
            language="go"
        )
        
        assert should_llm is True
        assert reason.startswith("unsupported_language:go")
    
    def test_yaml_kubernetes_routes_to_llm(self):
        """Kubernetes YAML should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="kubernetes deployment",
            code_context="apiVersion: v1\nkind: Deployment\nmetadata:",
            detected_libraries=[],
            language="yaml"
        )
        
        assert should_llm is True
        assert reason.startswith("unsupported_language:yaml")
    
    # ==================== FAST-EVOLVING LIBRARY TESTS ====================
    
    def test_langchain_with_code_routes_to_llm(self):
        """LangChain code should route to LLM (fast-evolving)."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="from langchain import PromptTemplate\ntemplate = PromptTemplate(...)",
            detected_libraries=["langchain"],
            language="python"
        )
        
        assert should_llm is True
        assert reason == "fast_evolving_lib:langchain"
    
    def test_langgraph_with_code_routes_to_llm(self):
        """LangGraph code should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="from langgraph import StateGraph\ngraph = StateGraph()",
            detected_libraries=["langgraph"],
            language="python"
        )
        
        assert should_llm is True
        assert reason == "fast_evolving_lib:langgraph"
    
    def test_nextjs_with_code_routes_to_llm(self):
        """Next.js code should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="import { useRouter } from 'next/router'\nexport default function Page() {}",
            detected_libraries=["next", "nextjs"],
            language="javascript"
        )
        
        assert should_llm is True
        assert "next" in reason.lower()
    
    def test_fast__without_code_uses_template(self):
        """Fast-evolving lib without code context AND with stub template should route to LLM.
        
        Rationale: LangChain has only stub template ("# This section will be enriched"),
        so even without code, we should use LLM to get real content.
        """
        should_llm, reason = self.detector.should_use_llm(
            query="langchain basics",
            code_context="",  # No code provided
            detected_libraries=["langchain"],
            language="python"
        )
        
        # Should use LLM because template is just a stub
        assert should_llm is True
        assert reason.startswith("no_template_available")
    
    # ==================== LATEST REQUEST TESTS ====================
    
    def test_latest_keyword_routes_to_llm(self):
        """Explicit 'latest' request should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="latest pandas syntax",
            code_context="",
            detected_libraries=["pandas"],
            language="python"
        )
        
        assert should_llm is True
        assert reason.startswith("explicit_latest_request")
    
    def test_version_2024_routes_to_llm(self):
        """Year keyword (2024) should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="python 2024 features",
            code_context="",
            detected_libraries=[],
            language="python"
        )
        
        assert should_llm is True
        assert reason.startswith("explicit_latest_request")
    
    def test_modern_keyword_routes_to_llm(self):
        """'modern' keyword should route to LLM."""
        should_llm, reason = self.detector.should_use_llm(
            query="modern react hooks",
            code_context="",
            detected_libraries=["react"],
            language="javascript"
        )
        
        assert should_llm is True
        assert reason.startswith("explicit_latest_request")
    
    # ==================== STABLE LIBRARY TESTS (USE TEMPLATE) ====================
    
    def test_pandas_code_uses_template(self):
        """Pandas code should use template (stable, well-documented)."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="import pandas as pd\ndf = pd.read_csv('data.csv')",
            detected_libraries=["pandas"],
            language="python"
        )
        
        assert should_llm is False
        assert reason == "template_available"
    
    def test_numpy_code_uses_template(self):
        """NumPy code should use template."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="import numpy as np\narr = np.array([1, 2, 3])",
            detected_libraries=["numpy"],
            language="python"
        )
        
        assert should_llm is False
        assert reason == "template_available"
    
    def test_fastapi_code_uses_template(self):
        """FastAPI code should use template."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="from fastapi import FastAPI\napp = FastAPI()",
            detected_libraries=["fastapi"],
            language="python"
        )
        
        assert should_llm is False
        assert reason == "template_available"
    
    def test_python_no_libraries_uses_template(self):
        """Python code without libraries should use template."""
        should_llm, reason = self.detector.should_use_llm(
            query="python basics",
            code_context="def greet(name):\n    print(f'Hello {name}')",
            detected_libraries=[],
            language="python"
        )
        
        assert should_llm is False
        assert reason == "template_available"
    
    # ==================== EDGE CASES ====================
    
    def test_empty_inputs_uses_template(self):
        """Empty inputs should default to template."""
        should_llm, reason = self.detector.should_use_llm(
            query="",
            code_context="",
            detected_libraries=[],
            language="python"
        )
        
        assert should_llm is False
        assert reason == "template_available"
    
    def test_single_sql_keyword_insufficient(self):
        """Single SQL keyword should not trigger (needs 2+ for confidence)."""
        should_llm, reason = self.detector.should_use_llm(
            query="database select",  # Only 1 keyword
            code_context="",
            detected_libraries=[],
            language="python"  # Not SQL
        )
        
        # Should use template (insufficient confidence)
        assert should_llm is False
    
    def test_explicit_language_overrides_keywords(self):
        """Explicit language parameter should have highest priority."""
        should_llm, reason = self.detector.should_use_llm(
            query="basic queries",  # Generic query
            code_context="",
            detected_libraries=[],
            language="sql"  # Explicit SQL
        )
        
        # Should route to LLM based on explicit language
        assert should_llm is True
        assert reason == "unsupported_language:sql"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
