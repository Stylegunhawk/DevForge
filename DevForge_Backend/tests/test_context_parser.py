"""Tests for context-aware prompt refinement."""

import pytest
from src.agents.prompt_refiner.conversation_parser import ConversationParser
from src.agents.prompt_refiner.code_parser import CodeParser
from src.agents.prompt_refiner.context_types import (
    ConversationContext,
    CodeStructure,
    CodeContext,
)


class TestConversationParser:
    """Tests for ConversationParser."""
    
    def test_extract_fastapi_from_conversation(self):
        """Test extracting FastAPI from conversation."""
        parser = ConversationParser()
        messages = [
            {"role": "user", "content": "I'm building a FastAPI application"},
            {"role": "assistant", "content": "Great! Here's how to start..."},
        ]
        
        context = parser.extract_context(messages)
        
        assert "FastAPI" in context.technologies
        assert context.project_type in ["REST API", "Unknown"]
    
    def test_extract_multiple_technologies(self):
        """Test extracting multiple technologies."""
        parser = ConversationParser()
        messages = [
            {"role": "user", "content": "Using FastAPI with PostgreSQL and Redis"},
            {"role": "assistant", "content": "Setting up database..."},
        ]
        
        context = parser.extract_context(messages)
        
        assert "FastAPI" in context.technologies
        assert "PostgreSQL" in context.technologies
        assert "Redis" in context.technologies
    
    def test_identify_project_type(self):
        """Test project type identification."""
        parser = ConversationParser()
        messages = [
            {"role": "user", "content": "Building a REST API backend"},
        ]
        
        context = parser.extract_context(messages)
        
        assert context.project_type == "REST API"
    
    def test_empty_conversation(self):
        """Test handling empty conversation."""
        parser = ConversationParser()
        context = parser.extract_context([])
        
        assert context.project_type == "Unknown"
        assert len(context.technologies) == 0
    
    def test_detect_async_preference(self):
        """Test detecting async preference."""
        parser = ConversationParser()
        messages = [
            {"role": "user", "content": "I want to use async/await patterns"},
        ]
        
        context = parser.extract_context(messages)
        
        assert context.preferences.get("async") is True
    
    def test_limit_to_last_5_messages(self):
        """Test that only last 5 messages are processed."""
        parser = ConversationParser()
        messages = [
            {"role": "user", "content": f"Message {i}"} for i in range(10)
        ]
        messages[7]["content"] = "Using Django"
        
        context = parser.extract_context(messages)
        
        # Django is in message 7, which should be included in last 5
        assert "Django" in context.technologies


class TestCodeParser:
    """Tests for CodeParser."""
    
    def test_parse_simple_class(self):
        """Test parsing a simple Python class."""
        parser = CodeParser()
        code = """
class UserModel:
    def __init__(self):
        pass
    
    def get_name(self):
        return self.name
"""
        
        structure = parser.parse_file(code, "python")
        
        assert "UserModel" in structure.classes
        assert structure.language == "python"
    
    def test_parse_async_functions(self):
        """Test detecting async functions."""
        parser = CodeParser()
        code = """
async def fetch_user(id: int):
    return await db.get(id)

async def create_user(data: dict):
    return await db.insert(data)
"""
        
        structure = parser.parse_file(code, "python")
        
        assert "async" in structure.patterns
        assert len(structure.functions) >= 2
    
    def test_detect_snake_case(self):
        """Test detecting snake_case naming convention."""
        parser = CodeParser()
        code = """
def fetch_user_data():
    pass

def create_new_record():
    pass
"""
        
        structure = parser.parse_file(code, "python")
        
        assert structure.conventions.get("naming") == "snake_case"
    
    def test_extract_imports(self):
        """Test extracting import statements."""
        parser = CodeParser()
        code = """
import os
from fastapi import FastAPI
from typing import Optional
"""
        
        structure = parser.parse_file(code, "python")
        
        assert len(structure.imports) >= 2
        assert any("fastapi" in imp.lower() for imp in structure.imports)
    
    def test_invalid_code_handling(self):
        """Test handling invalid Python code."""
        parser = CodeParser()
        invalid_code = "def broken syntax ]["
        
        structure = parser.parse_file(invalid_code, "python")
        
        # Should return empty structure without crashing
        assert structure.language == "python"
        assert len(structure.classes) == 0
    
    def test_detect_decorators(self):
        """Test detecting decorator usage."""
        parser = CodeParser()
        code = """
@app.get("/users")
async def get_users():
    pass

@staticmethod
def helper():
    pass
"""
        
        structure = parser.parse_file(code, "python")
        
        assert "decorators" in structure.patterns
    
    def test_parse_javascript_code(self):
        """Test parsing JavaScript code."""
        parser = CodeParser()
        code = """
class UserService {
    constructor() {}
    
    async fetchUser(id) {
        return await fetch(`/api/users/${id}`);
    }
}

const createUser = async (data) => {
    return await api.post('/users', data);
};
"""
        
        structure = parser.parse_file(code, language="javascript")  # Explicitly set language
        
        assert structure.language == "javascript"
        assert "UserService" in structure.classes
        assert "async" in structure.patterns
    
    def test_empty_code(self):
        """Test handling empty code."""
        parser = CodeParser()
        structure = parser.parse_file("")
        
        assert len(structure.classes) == 0
        assert len(structure.functions) == 0


class TestCodeContext:
    """Tests for CodeContext."""
    
    def test_has_context_with_data(self):
        """Test has_context returns True when context exists."""
        context = CodeContext()
        context.conversation.technologies = ["FastAPI"]
        context.code_structure.classes = ["UserModel"]
        
        assert context.has_context() is True
    
    def test_has_context_empty(self):
        """Test has_context returns False when no context."""
        context = CodeContext()
        
        assert context.has_context() is False
    
    def test_to_dict(self):
        """Test converting context to dictionary."""
        context = CodeContext()
        context.detected_language = "python"
        context.frameworks = ["FastAPI"]
        context.code_structure.classes = ["UserModel", "PostModel"]
        context.conversation.technologies = ["FastAPI", "PostgreSQL"]
        
        data = context.to_dict()
        
        assert data["language"] == "python"
        assert "FastAPI" in data["frameworks"]
        assert len(data["classes"]) == 2
        assert "FastAPI" in data["technologies"]


class TestIntegration:
    """Integration tests for context gathering."""
    
    @pytest.mark.asyncio
    async def test_full_context_extraction(self):
        """Test complete context extraction from conversation and code."""
        conv_parser = ConversationParser()
        code_parser = CodeParser()
        
        # Simulate conversation
        messages = [
            {"role": "user", "content": "Building a FastAPI application"},
            {"role": "assistant", "content": "Here's a user model..."},
            {"role": "user", "content": "Add async database queries"},
        ]
        
        conv_context = conv_parser.extract_context(messages)
        
        # Simulate code file
        code = """
from fastapi import FastAPI

class UserModel:
    def __init__(self):
        pass

async def get_user(id: int):
    return await db.fetch_one(id)
"""
        
        code_structure = code_parser.parse_file(code, "python")
        
        # Create unified context
        context = CodeContext()
        context.conversation = conv_context
        context.code_structure = code_structure
        context.frameworks = conv_context.technologies
        context.detected_language = code_structure.language
        
        # Verify complete context
        assert "FastAPI" in context.frameworks
        assert "UserModel" in context.code_structure.classes
        assert context.detected_language == "python"
        assert "async" in context.code_structure.patterns
        assert context.has_context() is True
