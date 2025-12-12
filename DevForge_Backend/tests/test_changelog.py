"""Tests for changelog generation tool.

Tests conventional commit parsing, categorization, and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.tools.changelog import ChangelogGenerator, generate_changelog_invoke


class TestChangelogGenerator:
    """Test changelog generator functionality"""
    
    @pytest.mark.asyncio
    async def test_generate_changelog_success(self):
        """Test successful changelog generation"""
        generator = ChangelogGenerator()
        
        with patch.object(generator, '_fetch_commits') as mock_fetch:
            mock_fetch.return_value = [
                {
                    "sha": "abc1234",
                    "message": "feat(auth): add JWT rotation",
                    "author": "developer",
                    "date": "2025-12-12T00:00:00",
                    "url": "https://github.com/user/repo/commit/abc1234"
                },
                {
                    "sha": "def5678",
                    "message": "fix(api): handle null responses",
                    "author": "developer",
                    "date": "2025-12-12T01:00:00",
                    "url": "https://github.com/user/repo/commit/def5678"
                }
            ]
            
            result = await generator.generate(
                repo="user/test-repo",
                from_tag="v1.0.0",
                to_tag="v1.1.0"
            )
            
            assert result["success"] is True
            assert result["commits_analyzed"] == 2
            assert "✨ Features" in result["categories"]
            assert "🐛 Bug Fixes" in result["categories"]
            assert "audit_id" in result
    
    @pytest.mark.asyncio
    async def test_categorize_conventional_commits(self):
        """Test conventional commit categorization"""
        generator = ChangelogGenerator()
        
        commits = [
            {"sha": "1", "message": "feat: new feature", "author": "dev", "date": "2025-12-12", "url": "url1"},
            {"sha": "2", "message": "fix: bug fix", "author": "dev", "date": "2025-12-12", "url": "url2"},
            {"sha": "3", "message": "docs: update readme", "author": "dev", "date": "2025-12-12", "url": "url3"},
            {"sha": "4", "message": "chore: update deps", "author": "dev", "date": "2025-12-12", "url": "url4"},
        ]
        
        categorized = generator._categorize_commits(commits)
        
        assert "✨ Features" in categorized
        assert "🐛 Bug Fixes" in categorized
        assert "📚 Documentation" in categorized
        assert "🔧 Chores" in categorized
        
        assert len(categorized["✨ Features"]) == 1
        assert len(categorized["🐛 Bug Fixes"]) == 1
    
    def test_categorize_with_scope(self):
        """Test categorization with scopes"""
        generator = ChangelogGenerator()
        
        commits = [
            {"sha": "1", "message": "feat(auth): add login", "author": "dev", "date": "2025-12-12", "url": "url"},
        ]
        
        categorized = generator._categorize_commits(commits)
        commit = categorized["✨ Features"][0]
        
        assert commit["scope"] == "auth"
        assert commit["description"] == "add login"
    
    def test_categorize_non_conventional(self):
        """Test non-conventional commits go to Other"""
        generator = ChangelogGenerator()
        
        commits = [
            {"sha": "1", "message": "Random commit message", "author": "dev", "date": "2025-12-12", "url": "url"},
        ]
        
        categorized = generator._categorize_commits(commits)
        
        assert "📝 Other" in categorized
        assert len(categorized["📝 Other"]) == 1
    
    def test_format_markdown(self):
        """Test markdown formatting"""
        generator = ChangelogGenerator()
        
        categorized = {
            "✨ Features": [{
                "sha": "abc123",
                "message": "feat: add feature",
                "author": "developer",
                "date": "2025-12-12",
                "url": "https://github.com/user/repo/commit/abc123",
                "type": "feat",
                "scope": None,
                "description": "add feature"
            }]
        }
        
        markdown = generator._format_markdown(categorized, "v1.0.0", "v1.1.0")
        
        assert "# Changelog: v1.0.0 → v1.1.0" in markdown
        assert "## ✨ Features" in markdown
        assert "add feature" in markdown
        assert "[abc123]" in markdown
    
    @pytest.mark.asyncio
    async def test_generate_no_commits(self):
        """Test changelog with no commits"""
        generator = ChangelogGenerator()
        
        with patch.object(generator, '_fetch_commits') as mock_fetch:
            mock_fetch.return_value = []
            
            result = await generator.generate(
                repo="user/repo",
                from_tag="v1.0.0",
                to_tag="v1.0.1"
            )
            
            assert result["success"] is True
            assert result["commits_analyzed"] == 0
            assert len(result["categories"]) == 0
    
    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """Test handling GitHub API errors"""
        generator = ChangelogGenerator()
        
        with patch.object(generator, '_fetch_commits') as mock_fetch:
            mock_fetch.side_effect = Exception("GitHub API error")
            
            result = await generator.generate(
                repo="user/repo",
                from_tag="v1.0.0"
            )
            
            assert result["success"] is False
            assert "error" in result
            assert "GitHub API error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_json_format_output(self):
        """Test JSON format output"""
        generator = ChangelogGenerator()
        
        with patch.object(generator, '_fetch_commits') as mock_fetch:
            mock_fetch.return_value = [
                {"sha": "1", "message": "feat: test", "author": "dev", "date": "2025-12-12", "url": "url"}
            ]
            
            result = await generator.generate(
                repo="user/repo",
                from_tag="v1.0.0",
                format="json"
            )
            
            assert result["success"] is True
            assert isinstance(result["changelog"], dict)
            assert "✨ Features" in result["changelog"]


@pytest.mark.asyncio
async def test_changelog_invoke():
    """Test API invoke function"""
    with patch('src.tools.changelog.ChangelogGenerator') as MockGenerator:
        mock_instance = AsyncMock()
        mock_instance.generate.return_value = {
            "success": True,
            "changelog": "# Changelog...",
            "commits_analyzed": 5
        }
        MockGenerator.return_value = mock_instance
        
        result = await generate_changelog_invoke({
            "repo": "user/repo",
            "from_tag": "v1.0.0",
            "to_tag": "v1.1.0"
        })
        
        assert result["success"] is True
        assert result["commits_analyzed"] == 5
