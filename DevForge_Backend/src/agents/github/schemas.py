# src/agents/github/schemas.py
"""
Pydantic schemas for GitHub operation parameters.
Ensures strict validation before executing any API calls.
"""

from typing import List, Optional, Literal, Union, Annotated
from pydantic import BaseModel, Field, validator, RootModel, model_validator


class ListReposParams(BaseModel):
    visibility: Literal["all", "public", "private"] = "all"
    sort: Literal["updated", "created", "pushed", "full_name"] = "updated"
    limit: Annotated[int, Field(gt=0, le=100)] = 10


class CreateRepoParams(BaseModel):
    name: Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")]
    description: Optional[str] = ""
    private: bool = False
    auto_init: bool = True


class CreateIssueParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    title: Annotated[str, Field(min_length=1)]
    body: Optional[str] = ""
    labels: Optional[List[str]] = None
    assignees: Optional[List[str]] = None


class CommitFileParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    file_path: Annotated[str, Field(min_length=1)]
    content: Optional[str] = None
    commit_message: Annotated[str, Field(min_length=1)]
    branch: str = "main"
    file_url: Optional[str] = None

    @model_validator(mode="after")
    def check_content_or_url(self) -> "CommitFileParams":
        if not self.content and not self.file_url:
            raise ValueError("Either 'content' or 'file_url' must be provided")
        return self


class CreatePullRequestParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    title: Annotated[str, Field(min_length=1)]
    head: Annotated[str, Field(min_length=1)]
    base: str = "main"
    body: Optional[str] = ""
    draft: bool = False


class BrowseFilesParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    path: str = "/"


class ReadFileParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    file_path: Annotated[str, Field(min_length=1)]


class SearchCodeParams(BaseModel):
    query: Annotated[str, Field(min_length=1)]
    repo_name: Optional[Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]] = None


class ScaffoldRepoParams(BaseModel):
    name: Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")]
    template: Annotated[str, Field(min_length=1)]
    description: Optional[str] = ""
    private: bool = False
    force: bool = False


class GenerateChangelogParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    from_tag: Optional[str] = None
    to_tag: str = "HEAD"
    format: Literal["markdown", "json", "plain"] = "markdown"


class AnalyzeCiFailureParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    run_id: int
    pr_number: Optional[int] = None


# Discriminated Union for all operations
OperationParams = Union[
    ListReposParams,
    CreateRepoParams,
    CreateIssueParams,
    CommitFileParams,
    CreatePullRequestParams,
    BrowseFilesParams,
    ReadFileParams,
    SearchCodeParams,
    ScaffoldRepoParams,
    GenerateChangelogParams,
    AnalyzeCiFailureParams
]

SCHEMA_MAP = {
    "list_repos": ListReposParams,
    "create_repo": CreateRepoParams,
    "create_issue": CreateIssueParams,
    "commit_file": CommitFileParams,
    "create_pull_request": CreatePullRequestParams,
    "browse_files": BrowseFilesParams,
    "read_file": ReadFileParams,
    "search_code": SearchCodeParams,
    "scaffold_repo": ScaffoldRepoParams,
    "generate_changelog": GenerateChangelogParams,
    "analyze_ci_failure": AnalyzeCiFailureParams,
}

def validate_op_params(operation: str, params: dict) -> dict:
    """Validate parameters for a specific operation.
    Returns validated dict or raises ValidationError.
    """
    if operation not in SCHEMA_MAP:
        raise ValueError(f"No validation schema for operation: {operation}")
    
    schema = SCHEMA_MAP[operation]
    validated = schema(**params)
    return validated.model_dump()
