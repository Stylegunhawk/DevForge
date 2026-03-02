"""Repository scaffolding tool.

Creates new repositories from templates with CI/CD setup.
Implements all production guardrails: token scopes, idempotency, async fallback, input validation.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from src.tools.github.tools import GitHubTools
from src.core.audit import Timeline, EventType, generate_audit_id
from src.core.security import SecurityValidator, InputValidator, check_idempotency
from src.core.config import settings
from src.core.jobs import get_job_queue

logger = logging.getLogger(__name__)


@dataclass
class Template:
    """Repository template definition"""
    name: str
    description: str
    files: Dict[str, str]  # filepath -> content
    ci_workflows: List[Dict[str, Any]]


class RepositoryScaffolder:
    """Scaffold new repositories from templates"""
    
    TEMPLATES = {
        "fastapi": Template(
            name="fastapi",
            description="FastAPI microservice with PostgreSQL",
            files={
                "README.md": "# {repo_name}\n\nFastAPI microservice\n",
                "requirements.txt": "fastapi>=0.109.0\nuvicorn>=0.27.0\npydantic>=2.0.0\n",
                "src/main.py": '''from fastapi import Fast API\n\napp = FastAPI(title="{repo_name}")\n\n@app.get("/")\ndef read_root():\n    return {"message": "Hello from {repo_name}"}\n''',
                ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\n"
            },
            ci_workflows=[{
                "name": "ci.yml",
                "content": '''name: CI\n\non: [push, pull_request]\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - uses: actions/setup-python@v4\n        with:\n          python-version: '3.11'\n      - run: pip install -r requirements.txt\n      - run: pytest\n'''
            }]
        ),
        "react": Template(
            name="react",
            description="React application with TypeScript",
            files={
                "README.md": "# {repo_name}\n\nReact application\n",
                "package.json": '''{
  "name": "{repo_name}",
  "version": "0.1.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }
}''',
                ".gitignore": "node_modules/\nbuild/\n.env\n"
            },
            ci_workflows=[{
                "name": "ci.yml",
                "content": '''name: CI\n\non: [push, pull_request]\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - uses: actions/setup-node@v3\n        with:\n          node-version: '18'\n      - run: npm install\n      - run: npm test\n'''
            }]
        ),
        "nextjs": Template(
            name="nextjs",
            description="Next.js application",
            files={
                "README.md": "# {repo_name}\n\nNext.js application\n",
                "package.json": '''{
  "name": "{repo_name}",
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build"
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0"
  }
}''',
                ".gitignore": "node_modules/\n.next/\nbuild/\n"
            },
            ci_workflows=[{
                "name": "ci.yml",
                "content": "name: CI\n\non: [push]\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - run: npm install\n      - run: npm run build\n"
            }]
        ),
        "microservice": Template(
            name="microservice",
            description="Generic microservice with Docker",
            files={
                "README.md": "# {repo_name}\n\nMicroservice\n",
                "Dockerfile": "FROM python:3.11-slim\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD python src/main.py\n",
                "requirements.txt": "fastapi\nuvicorn\n",
                ".gitignore": "__pycache__/\n*.pyc\n"
            },
            ci_workflows=[]
        ),
        "docs": Template(
            name="docs",
            description="Documentation site with mkdocs",
            files={
                "README.md": "# {repo_name}\n\nDocumentation\n",
                "mkdocs.yml": "site_name: {repo_name}\n",
                "docs/index.md": "# Welcome\n\nDocumentation for {repo_name}\n",
                ".gitignore": "site/\n"
            },
            ci_workflows=[]
        )
    }
    
    def __init__(self, github_tools: Optional[GitHubTools] = None):
        self.github_tools = github_tools or GitHubTools()
        self.security_validator = SecurityValidator(self.github_tools.client)
    
    async def scaffold(
        self,
        name: str,
        template: str,
        description: Optional[str] = None,
        private: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """Scaffold new repository from template
        
        Args:
            name: Repository name
            template: Template name (fastapi, react, nextjs, microservice, docs)
            description: Repository description
            private: Whether repo should be private
            force: Force creation if repo exists
            
        Returns:
            Scaffold result with repo URL and files created
        """
        audit_id = generate_audit_id()
        timeline = Timeline(audit_id, "scaffold_repository")
        timeline.add_event(EventType.OPERATION_START, f"Scaffolding {name} from {template}")
        
        try:
            # GUARDRAIL 1: Token scope check
            timeline.start_step("validate_token", "Checking token scopes")
            self.security_validator.ensure_token_scopes("scaffold_repo")
            timeline.complete_step("validate_token", "Token scopes validated")
            
            # GUARDRAIL 2: Input validation
            timeline.start_step("validate_inputs", "Validating inputs")
            name = InputValidator.validate_repo_name(name)
            description = InputValidator.sanitize_description(description)
            template = InputValidator.validate_enum(
                template,
                list(self.TEMPLATES.keys()),
                "template"
            )
            timeline.complete_step("validate_inputs", "Inputs validated")
            
            # GUARDRAIL 3: Idempotency check
            timeline.start_step("check_exists", "Checking if repo exists")
            user = self.github_tools.client.get_user()
            idempotent_check = check_idempotency(
                self.github_tools.client,
                user.login,
                name,
                force
            )
            
            if idempotent_check.get("success") is False:
                # Repo exists and force=False
                return idempotent_check
            
            timeline.complete_step("check_exists", "Idempotency check passed")
            
            # GUARDRAIL 4: Async fallback for large templates
            template_obj = self.TEMPLATES[template]
            work_units = len(template_obj.files) + len(template_obj.ci_workflows)
            
            if work_units > settings.MAX_SYNC_WORK_UNITS:
                # Enqueue async job
                job_queue = get_job_queue()
                job_id = await job_queue.enqueue(
                    handler_name="scaffold_repository",
                    params={
                        "name": name,
                        "template": template,
                        "description": description,
                        "private": private
                    }
                )
                
                return {
                    "success": True,
                    "mode": "async",
                    "job_id": job_id,
                    "status_endpoint": f"/api/jobs/{job_id}",
                    "message": f"Large template ({work_units} files). Job enqueued.",
                    "audit_id": audit_id
                }
            
            # Execute scaffolding synchronously
            result = await self._execute_scaffold(
                user.login,
                name,
                template_obj,
                description,
                private,
                timeline
            )
            
            timeline.add_event(EventType.OPERATION_COMPLETE, "Scaffolding complete")
            
            return {
                **result,
                "audit_id": audit_id,
                "timeline": timeline.to_dict()
            }
            
        except Exception as e:
            timeline.fail_step("scaffold", str(e))
            logger.error(f"[{audit_id}] Scaffolding failed: {e}", exc_info=True)
            
            # Attempt rollback if repo was created
            if hasattr(self, '_created_repo'):
                try:
                    logger.warning(f"Rolling back: deleting repo {name}")
                    self._created_repo.delete()
                except:
                    pass
            
            return {
                "success": False,
                "error": str(e),
                "audit_id": audit_id,
                "timeline": timeline.to_dict()
            }
    
    async def _execute_scaffold(
        self,
        owner: str,
        name: str,
        template: Template,
        description: Optional[str],
        private: bool,
        timeline: Timeline
    ) -> Dict[str, Any]:
        """Execute scaffolding steps
        
        Args:
            owner: Repository owner
            name: Repository name
            template: Template object
            description: Description
            private: Private flag
            timeline: Timeline for tracking
            
        Returns:
            Result dict
        """
        # Create repository
        timeline.start_step("create_repo", f"Creating repository {name}")
        
        user = self.github_tools.client.get_user()
        repo = user.create_repo(
            name=name,
            description=description or template.description,
            private=private,
            auto_init=False  # We'll create initial commit
        )
        
        self._created_repo = repo  # For rollback
        timeline.complete_step("create_repo", f"Created {repo.html_url}")
        
        # Create main branch and initial commit with all files
        timeline.start_step("scaffold_files", f"Creating {len(template.files)} files")
        
        # Prepare all files
        elements = []
        for filepath, content_template in template.files.items():
            content = content_template.replace("{repo_name}", name)
            elements.append(
                {
                    "path": filepath,
                    "mode": "100644",
                    "type": "blob",
                    "content": content
                }
            )
        
        # Create tree
        base_tree = repo.create_git_tree(elements)
        
        # Create commit
        commit = repo.create_git_commit(
            message=f"chore: initial scaffold from {template.name} template",
            tree=base_tree,
            parents=[]
        )
        
        # Create main branch ref
        repo.create_git_ref("refs/heads/main", commit.sha)
        
        timeline.complete_step("scaffold_files",f"Created {len(template.files)} files")
        
        # Setup CI workflows
        if template.ci_workflows:
            timeline.start_step("setup_ci", f"Setting up {len(template.ci_workflows)} CI workflows")
            
            for workflow in template.ci_workflows:
                workflow_path = f".github/workflows/{workflow['name']}"
                try:
                    repo.create_file(
                        path=workflow_path,
                        message=f"ci: add {workflow['name']} workflow",
                        content=workflow['content'],
                        branch="main"
                    )
                except Exception as e:
                    logger.error(f"Failed to create workflow {workflow['name']}: {e}")
                    # Continue with other workflows
            
            timeline.complete_step("setup_ci", "CI workflows created")
        
        return {
            "success": True,
            "repo_url": repo.html_url,
            "repo_name": repo.full_name,
            "template_used": template.name,
            "files_created": len(template.files),
            "ci_workflows": len(template.ci_workflows),
            "clone_url": repo.clone_url
        }


# Convenience function for API
async def scaffold_repository_invoke(
    args: Dict[str, Any], 
    github_tools: Optional[GitHubTools] = None
) -> Dict[str, Any]:
    """API entry point for repository scaffolding
    
    Args:
        args: Arguments dict with name, template, description, private, force
        github_tools: Optional GitHubTools instance
        
    Returns:
        Scaffold result
    """
    scaffolder = RepositoryScaffolder(github_tools=github_tools)
    
    return await scaffolder.scaffold(
        name=args["name"],
        template=args["template"],
        description=args.get("description"),
        private=args.get("private", False),
        force=args.get("force", False)
    )
