"""Changelog generation tool.

Generates release notes and changelog from git history between tags/commits.
Self-contained tool optimized for Lobe Chat single-call architecture.
"""

import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

from src.tools.github.tools import GitHubTools
from src.core.audit import Timeline, EventType, generate_audit_id
from src.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class ChangelogGenerator:
    """Generate changelogs from git history"""
    
    def __init__(self):
        self.github_tools = GitHubTools()
        self.model_router = ModelRouter()
    
    async def generate(
        self,
        repo: str,
        from_tag: str,
        to_tag: str = "HEAD",
        format: str = "markdown"
    ) -> Dict[str, Any]:
        """Generate changelog between tags
        
        Args:
            repo: Repository name (user/repo)
            from_tag: Start tag/commit
            to_tag: End tag/commit (default: HEAD)
            format: Output format (markdown|json)
            
        Returns:
            Complete changelog with categorized commits
        """
        audit_id = generate_audit_id()
        timeline = Timeline(audit_id, "generate_changelog")
        timeline.add_event(EventType.OPERATION_START, f"Generating changelog for {repo}")
        
        try:
            # Extract commits
            timeline.start_step("fetch_commits", f"Fetching commits {from_tag}..{to_tag}")
            commits = await self._fetch_commits(repo, from_tag, to_tag)
            timeline.complete_step("fetch_commits", f"Fetched {len(commits)} commits")
            
            # Categorize commits
            timeline.start_step("categorize", "Categorizing commits by type")
            categorized = self._categorize_commits(commits)
            timeline.complete_step("categorize", f"Found {len(categorized)} categories")
            
            # Generate changelog
            timeline.start_step("format", f"Formatting as {format}")
            
            if format == "markdown":
                changelog = self._format_markdown(categorized, from_tag, to_tag)
            else:
                changelog = categorized
            
            timeline.complete_step("format", "Formatted changelog")
            timeline.add_event(EventType.OPERATION_COMPLETE, "Changelog generated")
            
            return {
                "success": True,
                "changelog": changelog,
                "from_tag": from_tag,
                "to_tag": to_tag,
                "commits_analyzed": len(commits),
                "categories": list(categorized.keys()),
                "audit_id": audit_id,
                "timeline": timeline.to_dict()
            }
            
        except Exception as e:
            timeline.fail_step("generate", str(e))
            logger.error(f"[{audit_id}] Changelog generation failed: {e}", exc_info=True)
            
            return {
                "success": False,
                "error": str(e),
                "audit_id": audit_id,
                "timeline": timeline.to_dict()
            }
    
    async def _fetch_commits(
        self,
        repo: str,
        from_tag: str,
        to_tag: str
    ) -> List[Dict[str, str]]:
        """Fetch commits between tags using GitHub API
        
        Args:
            repo: Repository name
            from_tag: Start tag
            to_tag: End tag
            
        Returns:
            List of commit dicts with sha, message, author, date
        """
        try:
            # Use PyGithub to get commits
            github_repo = self.github_tools.g.get_repo(repo)
            
            # Get commit range
            comparison = github_repo.compare(from_tag, to_tag)
            
            commits = []
            for commit in comparison.commits:
                commits.append({
                    "sha": commit.sha[:7],
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url
                })
            
            return commits
            
        except Exception as e:
            logger.error(f"Failed to fetch commits: {e}")
            raise
    
    def _categorize_commits(self, commits: List[dict]) -> Dict[str, List[dict]]:
        """Categorize commits by conventional commit type
        
        Args:
            commits: List of commit dicts
            
        Returns:
            Dict mapping category to list of commits
        """
        categories = defaultdict(list)
        
        for commit in commits:
            message = commit["message"].split("\n")[0]  # First line only
            
            # Parse conventional commit format
            match = re.match(r'^(feat|fix|docs|style|refactor|perf|test|chore|ci|build)(\([^)]+\))?: (.+)$', message, re.IGNORECASE)
            
            if match:
                commit_type, scope, description = match.groups()
                commit_type = commit_type.lower()
                
                # Map to user-friendly categories
                category_map = {
                    "feat": "✨ Features",
                    "fix": "🐛 Bug Fixes",
                    "docs": "📚 Documentation",
                    "style": "💎 Styles",
                    "refactor": "♻️ Refactors",
                    "perf": "⚡ Performance",
                    "test": "✅ Tests",
                    "chore": "🔧 Chores",
                    "ci": "👷 CI/CD",
                    "build": "📦 Build"
                }
                
                category = category_map.get(commit_type, "📝 Other")
                
                categories[category].append({
                    **commit,
                    "type": commit_type,
                    "scope": scope[1:-1] if scope else None,  # Remove parentheses
                    "description": description.strip()
                })
            else:
                # Non-conventional commit
                categories["📝 Other"].append({
                    **commit,
                    "type": "other",
                    "scope": None,
                    "description": message
                })
        
        return dict(categories)
    
    def _format_markdown(
        self,
        categorized: Dict[str, List[dict]],
        from_tag: str,
        to_tag: str
    ) -> str:
        """Format changelog as markdown
        
        Args:
            categorized: Categorized commits
            from_tag: Start tag
            to_tag: End tag
            
        Returns:
            Markdown formatted changelog
        """
        lines = []
        
        # Header
        lines.append(f"# Changelog: {from_tag} → {to_tag}")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Summary
        total_commits = sum(len(commits) for commits in categorized.values())
        lines.append(f"**Total Changes:** {total_commits} commits")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Categories (ordered by importance)
        category_order = [
            "🚨 Breaking Changes",
            "✨ Features",
            "🐛 Bug Fixes",
            "⚡ Performance",
            "♻️ Refactors",
            "📚 Documentation",
            "✅ Tests",
            "👷 CI/CD",
            "📦 Build",
            "🔧 Chores",
            "💎 Styles",
            "📝 Other"
        ]
        
        for category in category_order:
            if category not in categorized:
                continue
            
            commits = categorized[category]
            lines.append(f"## {category}")
            lines.append("")
            
            for commit in commits:
                # Format: - description (#sha) by @author
                scope_str = f"**{commit['scope']}**: " if commit.get('scope') else ""
                lines.append(
                    f"- {scope_str}{commit['description']} "
                    f"([{commit['sha']}]({commit['url']})) by @{commit['author']}"
                )
            
            lines.append("")
        
        return "\n".join(lines)


# Convenience function for API
async def generate_changelog_invoke(args: Dict[str, Any]) -> Dict[str, Any]:
    """API entry point for changelog generation
    
    Args:
        args: Arguments dict with repo, from_tag, to_tag, format
        
    Returns:
        Changelog result
    """
    generator = ChangelogGenerator()
    
    return await generator.generate(
        repo=args["repo"],
        from_tag=args["from_tag"],
        to_tag=args.get("to_tag", "HEAD"),
        format=args.get("format", "markdown")
    )
