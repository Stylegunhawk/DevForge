"""Pydantic models for Phase 10.1 RAG API endpoints."""

from typing import List, Optional
from pydantic import BaseModel, Field


class IngestAsyncRequest(BaseModel):
    """Request model for async document ingestion."""
    
    file_paths: List[str] = Field(
        ...,
        description="List of file paths to ingest",
        min_items=1,
        max_items=100,
    )
    collection_name: str = Field(
        default="devforge_docs",
        description="Target collection name",
    )
    embed_model: str = Field(
        default="nomic-embed-text",
        description="Embedding model to use",
    )


class IngestAsyncResponse(BaseModel):
    """Response model for async ingestion task."""
    
    task_id: str = Field(..., description="Celery task ID for tracking")
    status: str = Field(default="queued", description="Initial task status")
    collection: str = Field(..., description="Target collection name")
    total_files: int = Field(..., description="Number of files queued")


class TaskStatusResponse(BaseModel):
    """Response model for task status query."""
    
    task_id: str
    status: str  # PENDING, PROGRESS, SUCCESS, FAILURE
    result: Optional[dict] = None
    progress: Optional[dict] = None  # current, total, file, percent
    error: Optional[str] = None
