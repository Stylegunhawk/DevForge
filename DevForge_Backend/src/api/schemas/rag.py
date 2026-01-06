from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from datetime import datetime

# ============================================================================
# 1. EXACT STATUS ENUMS (Case Sensitive!)
# ============================================================================

TaskStatus = Literal['pending', 'processing', 'success', 'error']

# ============================================================================
# 2. ERROR STRUCTURES
# ============================================================================

class AsyncTaskError(BaseModel):
    name: str = "ProcessingError"
    body: Union[str, dict]  # Can be string or {"detail": "..."}

# ============================================================================
# 3. FILE ITEM (Matches FileListItem from frontend)
# ============================================================================

class FileStatusResponse(BaseModel):
    """Response for GET /api/v1/rag/file/{fileId}"""
    id: str
    name: str  # Filename
    size: int
    url: str  # Static URL for preview
    fileType: str  # MIME type (e.g., "application/pdf", "text/python")
    
    # Async Task Fields (polling)
    chunkCount: Optional[int] = 0
    chunkingStatus: Optional[TaskStatus] = "pending"
    embeddingStatus: Optional[TaskStatus] = "pending"
    finishEmbedding: bool = False  # ⚠️ CRITICAL: Stops polling when True
    
    # Error tracking
    chunkingError: Optional[AsyncTaskError] = None
    embeddingError: Optional[AsyncTaskError] = None
    
    # Optional metadata
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

# ============================================================================
# 4. CHUNK RESPONSE (Matches ChatFileChunk from frontend)
# ============================================================================

class ChatFileChunk(BaseModel):
    """Individual chunk in semantic search response"""
    id: str  # Chunk UUID
    fileId: str  # File UUID (maps back to file metadata)
    filename: str  # Display name
    fileType: str  # MIME type
    fileUrl: str  # Static URL
    text: str  # Chunk content
    similarity: float  # Float (frontend will .toFixed(1))
    pageNumber: Optional[int] = None  # For PDFs

# ============================================================================
# 5. SEMANTIC SEARCH (Request + Response)
# ============================================================================

class SemanticSearchRequest(BaseModel):
    """Request for semantic search"""
    messageId: str
    userQuery: str
    rewriteQuery: Optional[str] = None  # LLM-optimized query
    fileIds: List[str] = Field(default_factory=list)  # Filter by files
    knowledgeIds: List[str] = Field(default_factory=list)  # Knowledge bases
    model: Optional[str] = None  # Embedding model
    top_k: int = Field(default=5, ge=1, le=50)

class SemanticSearchResponse(BaseModel):
    """Response for semantic search"""
    chunks: List[ChatFileChunk]
    queryId: Optional[str] = None  # For tracking/deletion

# ============================================================================
# 6. UPLOAD RESPONSE
# ============================================================================

class FileUploadResponse(BaseModel):
    """Response for file upload"""
    files: List[FileStatusResponse]
