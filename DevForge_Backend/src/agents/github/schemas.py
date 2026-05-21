# src/agents/github/schemas.py
"""
Pydantic schemas for GitHub operation parameters.
Ensures strict validation before executing any API calls.
"""

from typing import List, Optional, Literal, Union, Annotated, Dict
from pydantic import BaseModel, Field, validator, RootModel, model_validator


class ListReposParams(BaseModel):
    visibility: Literal["all", "public", "private"] = "all"
    sort: Literal["updated", "created", "pushed", "full_name"] = "updated"
    limit: Annotated[int, Field(gt=0, le=100)] = 10
    page: Annotated[int, Field(gt=0)] = 1


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
    delete: bool = False

    @model_validator(mode="after")
    def check_content_or_url(self) -> "CommitFileParams":
        if not self.delete and not self.content and not self.file_url:
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
    branch: Optional[str] = None


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


class ListBranchesParams(BaseModel):
    repo_name: Annotated[str, Field(min_length=1)]


class CreateBranchParams(BaseModel):
    repo_name: Annotated[str, Field(min_length=1)]
    branch_name: Annotated[str, Field(min_length=1, pattern=r"^[^\s]+$")]
    from_branch: str = "main"


class DeleteBranchParams(BaseModel):
    repo_name: Annotated[str, Field(min_length=1)]
    branch_name: Annotated[str, Field(min_length=1)]


class DeleteRepoParams(BaseModel):
    # Enforce owner/repo format at schema level — mirrors the tools.py safety requirement
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]


class MergePRParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    pr_number: Annotated[int, Field(gt=0)]
    merge_method: Literal["merge", "squash", "rebase"] = "merge"
    commit_title: Optional[str] = None
    commit_message: Optional[str] = None
    base: Optional[str] = None  # target branch, used for risk-gate context only


class ListPullRequestsParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    state: Literal["open", "closed", "all"] = "open"
    base: Optional[str] = None
    head: Optional[str] = None
    limit: Annotated[int, Field(gt=0, le=100)] = 10


class GetPRParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    pr_number: Annotated[int, Field(gt=0)]


class CloseIssueParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]


class UpdateIssueParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]
    title: Optional[str] = None
    body: Optional[str] = None
    state: Optional[Literal["open", "closed"]] = None
    labels: Optional[List[str]] = None
    assignees: Optional[List[str]] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateIssueParams":
        if all(v is None for v in [self.title, self.body, self.state, self.labels, self.assignees]):
            raise ValueError("At least one of title/body/state/labels/assignees must be provided")
        return self


class AddCommentParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]
    body: Annotated[str, Field(min_length=1)]


class ListCommitsParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    branch: str = "main"
    limit: Annotated[int, Field(gt=0, le=100)] = 20
    author: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


class GetCommitParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    sha: Annotated[str, Field(min_length=7)]


class ListReleasesParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    limit: Annotated[int, Field(gt=0, le=50)] = 10


class CreateReleaseParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    tag_name: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    body: str = ""
    draft: bool = False
    prerelease: bool = False
    target_commitish: str = "main"


class TriggerWorkflowParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    workflow_id: Annotated[str, Field(min_length=1)]
    ref: str = "main"
    inputs: Optional[Dict[str, str]] = None


class CreateWebhookParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    url: Annotated[str, Field(min_length=1)]
    events: List[str] = ["push"]
    content_type: Literal["json", "form"] = "json"
    active: bool = True
    secret: Optional[str] = None


class ListWebhooksParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]


class DeleteWebhookParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    hook_id: Annotated[int, Field(gt=0)]


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
    AnalyzeCiFailureParams,
    ListBranchesParams,
    CreateBranchParams,
    DeleteBranchParams,
    DeleteRepoParams,
    MergePRParams,
    ListPullRequestsParams,
    GetPRParams,
    CloseIssueParams,
    UpdateIssueParams,
    AddCommentParams,
    ListCommitsParams,
    GetCommitParams,
    ListReleasesParams,
    CreateReleaseParams,
    TriggerWorkflowParams,
    CreateWebhookParams,
    ListWebhooksParams,
    DeleteWebhookParams,
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
    "list_branches": ListBranchesParams,
    "create_branch": CreateBranchParams,
    "delete_branch": DeleteBranchParams,
    "delete_repo": DeleteRepoParams,
    "merge_pr": MergePRParams,
    "list_pull_requests": ListPullRequestsParams,
    "get_pr": GetPRParams,
    "close_issue": CloseIssueParams,
    "update_issue": UpdateIssueParams,
    "add_comment": AddCommentParams,
    "list_commits": ListCommitsParams,
    "get_commit": GetCommitParams,
    "list_releases": ListReleasesParams,
    "create_release": CreateReleaseParams,
    "trigger_workflow": TriggerWorkflowParams,
    "create_webhook": CreateWebhookParams,
    "list_webhooks": ListWebhooksParams,
    "delete_webhook": DeleteWebhookParams,
}

# Subset of SCHEMA_MAP exposed via structured-call mode on /mcp.
# The 3 extended ops (scaffold_repo, generate_changelog, analyze_ci_failure) stay
# accessible only via natural-language routing — they're not in this set.
_STRUCTURED_CALL_OPERATIONS = frozenset({
    "list_repos", "create_repo", "create_issue", "commit_file",
    "create_pull_request", "browse_files", "read_file", "search_code",
    "list_branches", "create_branch", "delete_branch", "delete_repo",
    "merge_pr", "list_pull_requests", "get_pr",
    "close_issue", "update_issue", "add_comment",
    "list_commits", "get_commit",
    "list_releases", "create_release",
    "trigger_workflow",
    "create_webhook", "list_webhooks", "delete_webhook",
})

# Derived from SCHEMA_MAP to keep a single source of truth.
# Consumers: GithubOperationArgs validator and tools/list oneOf builder.
OPERATION_SCHEMAS: dict[str, type[BaseModel]] = {
    op: SCHEMA_MAP[op] for op in sorted(_STRUCTURED_CALL_OPERATIONS)
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
