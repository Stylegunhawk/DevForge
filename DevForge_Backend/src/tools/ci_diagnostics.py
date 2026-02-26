"""CI/CD failure analysis tool.

Analyzes GitHub Actions workflow failures and suggests fixes.
Self-contained tool optimized for LobeChat single-call architecture.
"""

import logging
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from src.tools.github.tools import GitHubTools
from src.core.audit import Timeline, EventType, generate_audit_id
from src.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


@dataclass
class FailurePattern:
    """Detected failure pattern"""
    type: str  # test_failure, build_error, dependency_issue, etc.
    message: str
    line: Optional[int]
    file: Optional[str]
    severity: str  # critical, high, medium, low


@dataclass
class SuggestedFix:
    """Suggested fix for a failure"""
    title: str
    description: str
    confidence: float  # 0.0 to 1.0
    auto_fixable: bool
    commands: Optional[List[str]]  # Commands to run
    file_changes: Optional[Dict[str, str]]  # File path -> suggested change


class CIAnalyzer:
    """Analyze CI/CD pipeline failures"""
    
    def __init__(self, github_tools: Optional[GitHubTools] = None):
        self.github_tools = github_tools or GitHubTools()
        self.model_router = ModelRouter()
    
    async def analyze(
        self,
        repo: str,
        run_id: Optional[int] = None,
        pr_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Analyze CI failure and suggest fixes
        
        Args:
            repo: Repository name (user/repo)
            run_id: Workflow run ID (optional)
            pr_number: PR number to analyze (optional)
            
        Returns:
            Analysis with failures and suggested fixes
        """
        audit_id = generate_audit_id()
        timeline = Timeline(audit_id, "analyze_ci_failure")
        timeline.add_event(EventType.OPERATION_START, f"Analyzing CI for {repo}")
        
        try:
            # Fetch workflow logs
            timeline.start_step("fetch_logs", "Fetching workflow logs")
            logs = await self._fetch_logs(repo, run_id, pr_number)
            timeline.complete_step("fetch_logs", f"Fetched {len(logs)} bytes of logs")
            
            # Extract failure patterns
            timeline.start_step("extract_failures", "Extracting failure patterns")
            failures = self._extract_failure_patterns(logs)
            timeline.complete_step("extract_failures", f"Found {len(failures)} failures")
            
            # Generate fix suggestions using LLM
            timeline.start_step("suggest_fixes", "Generating fix suggestions")
            fixes = await self._suggest_fixes(failures, logs)
            timeline.complete_step("suggest_fixes", f"Generated {len(fixes)} suggestions")
            
            timeline.add_event(EventType.OPERATION_COMPLETE, "CI analysis complete")
            
            # Categorize fixes by confidence
            auto_fixable = [f for f in fixes if f.auto_fixable and f.confidence > 0.95]
            high_confidence = [f for f in fixes if f.confidence >= 0.85]
            
            return {
                "success": True,
                "repo": repo,
                "failures": [self._serialize_failure(f) for f in failures],
                "suggested_fixes": [self._serialize_fix(f) for f in fixes],
                "auto_fixable_count": len(auto_fixable),
                "high_confidence_count": len(high_confidence),
                "summary": self._generate_summary(failures, fixes),
                "audit_id": audit_id,
                "timeline": timeline.to_dict()
            }
            
        except Exception as e:
            timeline.fail_step("analyze", str(e))
            logger.error(f"[{audit_id}] CI analysis failed: {e}", exc_info=True)
            
            return {
                "success": False,
                "error": str(e),
                "audit_id": audit_id,
                "timeline": timeline.to_dict()
            }
    
    async def _fetch_logs(
        self,
        repo: str,
        run_id: Optional[int],
        pr_number: Optional[int]
    ) -> str:
        """Fetch workflow run logs from GitHub
        
        Args:
            repo: Repository name
            run_id: Optional workflow run ID
            pr_number: Optional PR number
            
        Returns:
            Combined workflow logs
        """
        try:
            github_repo = self.github_tools.client.get_repo(repo)
            
            if run_id:
                # Get specific workflow run
                run = github_repo.get_workflow_run(run_id)
            elif pr_number:
                # Get latest failed run for PR
                pr = github_repo.get_pull(pr_number)
                runs = github_repo.get_workflow_runs(
                    status="failure",
                    branch=pr.head.ref
                )
                run = list(runs)[0] if list(runs) else None
                
                if not run:
                    raise ValueError(f"No failed runs found for PR #{pr_number}")
            else:
                # Get latest failed run
                runs = github_repo.get_workflow_runs(status="failure")
                run = list(runs)[0] if list(runs) else None
                
                if not run:
                    raise ValueError("No failed workflow runs found")
            
            # Get logs (Note: This is simplified - actual implementation would use run.get_logs())
            # For now, return run conclusion and jobs info
            logs = []
            logs.append(f"Workflow: {run.name}")
            logs.append(f"Status: {run.status}")
            logs.append(f"Conclusion: {run.conclusion}")
            logs.append("")
            
            # Get job details
            jobs = run.jobs()
            for job in jobs:
                if job.conclusion == "failure":
                    logs.append(f"Failed Job: {job.name}")
                    logs.append(f"Conclusion: {job.conclusion}")
                    
                    # Get steps
                    for step in job.steps:
                        if step.conclusion == "failure":
                            logs.append(f"  Failed Step: {step.name}")
                            logs.append(f"  Conclusion: {step.conclusion}")
                    logs.append("")
            
            return "\n".join(logs)
            
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            raise
    
    def _extract_failure_patterns(self, logs: str) -> List[FailurePattern]:
        """Extract failure patterns from logs
        
        Args:
            logs: Raw workflow logs
            
        Returns:
            List of detected failure patterns
        """
        failures = []
        
        # Test failure patterns
        test_pattern = r'(FAILED|ERROR|AssertionError):?\s+(.+)'
        for match in re.finditer(test_pattern, logs):
            failures.append(FailurePattern(
                type="test_failure",
                message=match.group(2).strip(),
                line=None,
                file=None,
                severity="high"
            ))
        
        # Build error patterns
        build_pattern = r'(error|fatal):\s+(.+)'
        for match in re.finditer(build_pattern, logs, re.IGNORECASE):
            failures.append(FailurePattern(
                type="build_error",
                message=match.group(2).strip(),
                line=None,
                file=None,
                severity="critical"
            ))
        
        # Dependency issues
        if "ModuleNotFoundError" in logs or "ImportError" in logs:
            failures.append(FailurePattern(
                type="dependency_issue",
                message="Missing Python dependencies",
                line=None,
                file=None,
                severity="high"
            ))
        
        # Timeout issues
        if "timeout" in logs.lower() or "timed out" in logs.lower():
            failures.append(FailurePattern(
                type="timeout",
                message="Workflow or step timeout",
                line=None,
                file=None,
                severity="medium"
            ))
        
        return failures
    
    async def _suggest_fixes(
        self,
        failures: List[FailurePattern],
        logs: str
    ) -> List[SuggestedFix]:
        """Generate fix suggestions using LLM with auto-fix policy
        
        Args:
            failures: Detected failure patterns
            logs: Raw logs for context
            
        Returns:
            List of suggested fixes (with auto_fixable enforced by policy)
        """
        if not failures:
            return []
        
        try:
            from src.core.config import settings
            
            model = await self.model_router.select_model_by_task("github")
            
            # Build prompt
            failure_summary = "\n".join([
                f"- {f.type}: {f.message}" for f in failures[:5]  # Limit to 5
            ])
            
            prompt = f"""Analyze these CI/CD failures and suggest fixes:

Failures:
{failure_summary}

Logs excerpt:
{logs[:1000]}

Provide 2-3 specific, actionable fixes. For each fix, specify:
1. Title (brief description)
2. Detailed description
3. Confidence (0.0-1.0)
4. Fix type (one of: format, dependency_patch, lint, config, code_change)
5. Commands to run (if applicable)

Respond in JSON format:
[
  {{
    "title": "Fix title",
    "description": "Detailed fix description",
    "confidence": 0.9,
    "type": "dependency_patch", 
    "commands": ["command1", "command2"]
  }}
]
"""
            
            response = await self.model_router.invoke_with_fallback(
                model=model,
                prompt=prompt,
                fallback_chain=["gpt-oss:120b-cloud"]
            )
            
            # Parse response
            import json
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            fixes_data = json.loads(response_text)
            
            fixes = []
            for fix_data in fixes_data:
                fix_type = fix_data.get("type", "code_change")
                confidence = fix_data.get("confidence", 0.5)
                
                # Apply auto-fix policy
                auto_fixable = (
                    confidence >= settings.GITOPS_AUTO_FIX_THRESHOLD and
                    fix_type in settings.GITOPS_AUTO_FIX_TYPES
                )
                
                if auto_fixable:
                    logger.info(
                        f"Fix marked as auto-fixable: {fix_data['title']} "
                        f"(confidence: {confidence}, type: {fix_type})"
                    )
                
                fixes.append(SuggestedFix(
                    title=fix_data["title"],
                    description=fix_data["description"],
                    confidence=confidence,
                    auto_fixable=auto_fixable,
                    commands=fix_data.get("commands"),
                    file_changes=fix_data.get("file_changes")
                ))
            
            return fixes
            
        except Exception as e:
            logger.error(f"Failed to generate fix suggestions: {e}")
            # Return fallback generic suggestions
            return self._get_fallback_fixes(failures)
    
    def _get_fallback_fixes(self, failures: List[FailurePattern]) -> List[SuggestedFix]:
        """Get fallback suggestions based on failure types
        
        Args:
            failures: Detected failures
            
        Returns:
            Generic fix suggestions
        """
        fixes = []
        
        for failure in failures:
            if failure.type == "test_failure":
                fixes.append(SuggestedFix(
                    title="Review test assertions",
                    description="Check test expectations and actual behavior",
                confidence=0.6,
                    auto_fixable=False,
                    commands=None,
                    file_changes=None
                ))
            elif failure.type == "dependency_issue":
                fixes.append(SuggestedFix(
                    title="Update dependencies",
                    description="Install missing dependencies in requirements.txt or package.json",
                    confidence=0.8,
                    auto_fixable=True,
                    commands=["pip install -r requirements.txt"],
                    file_changes=None
                ))
            elif failure.type == "timeout":
                fixes.append(SuggestedFix(
                    title="Increase timeout limit",
                    description="Update workflow timeout settings",
                    confidence=0.7,
                    auto_fixable=True,
                    commands=None,
                    file_changes={".github/workflows/ci.yml": "timeout-minutes: 30"}
                ))
        
        return fixes[:3]  # Return top 3
    
    def _generate_summary(
        self,
        failures: List[FailurePattern],
        fixes: List[SuggestedFix]
    ) -> str:
        """Generate human-readable summary
        
        Args:
            failures: Detected failures
            fixes: Suggested fixes
            
        Returns:
            Summary string
        """
        summary = []
        
        summary.append(f"Found {len(failures)} failure(s):")
        
        # Group by type
        by_type = {}
        for failure in failures:
            by_type.setdefault(failure.type, []).append(failure)
        
        for failure_type, items in by_type.items():
            summary.append(f"  - {len(items)} {failure_type.replace('_', ' ')}")
        
        summary.append("")
        summary.append(f"Generated {len(fixes)} suggested fix(es)")
        
        auto_fixable = sum(1 for f in fixes if f.auto_fixable)
        if auto_fixable > 0:
            summary.append(f"  - {auto_fixable} auto-fixable")
        
        return "\n".join(summary)
    
    def _serialize_failure(self, failure: FailurePattern) -> dict:
        """Serialize failure to dict"""
        return {
            "type": failure.type,
            "message": failure.message,
            "line": failure.line,
            "file": failure.file,
            "severity": failure.severity
        }
    
    def _serialize_fix(self, fix: SuggestedFix) -> dict:
        """Serialize fix to dict"""
        return {
            "title": fix.title,
            "description": fix.description,
            "confidence": fix.confidence,
            "auto_fixable": fix.auto_fixable,
            "commands": fix.commands,
            "file_changes": fix.file_changes
        }


# Convenience function for API
async def analyze_ci_failure_invoke(
    args: Dict[str, Any],
    github_tools: Optional[GitHubTools] = None
) -> Dict[str, Any]:
    """API entry point for CI failure analysis
    
    Args:
        args: Arguments dict with repo, run_id, pr_number
        github_tools: Optional GitHubTools instance
        
    Returns:
        Analysis result
    """
    analyzer = CIAnalyzer(github_tools=github_tools)
    
    return await analyzer.analyze(
        repo=args["repo_name"],
        run_id=args.get("run_id"),
        pr_number=args.get("pr_number")
    )
