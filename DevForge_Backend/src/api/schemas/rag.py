from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal, Union
from datetime import datetime

# ============================================================================
# 1. EXACT STATUS ENUMS (Case Sensitive!)
# ============================================================================

TaskStatus = Literal['pending', 'processing', 'success', 'error']

# Legacy Redis data written by older workers used "complete" instead of "success".
# This mapping is applied before Pydantic validates the Literal constraint.
_LEGACY_STATUS_MAP = {"complete": "success", "done": "success", "failed": "error"}

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

    @field_validator("chunkingStatus", "embeddingStatus", mode="before")
    @classmethod
    def normalise_legacy_status(cls, v: object) -> object:
        if isinstance(v, str):
            return _LEGACY_STATUS_MAP.get(v, v)
        return v

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
    
    # Phase 13: Context Roles (entry, dependency, supporting)
    role: Optional[str] = "supporting"  # Default to supporting if missing

    # Phase 12A: Graph expansion provenance
    is_graph_expansion: bool = False
    expanded_from: Optional[str] = None

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
    expansion_count: int = 0

# ============================================================================
# 6. UPLOAD RESPONSE
# ============================================================================

class FileUploadResponse(BaseModel):
    """Response for file upload"""
    files: List[FileStatusResponse]

# ============================================================================
# 7. CODE GRAPH RESPONSES
# ============================================================================

class GraphNode(BaseModel):
    id: str
    name: str
    chunk_type: str
    source_file: str
    language: Optional[str] = None


class GraphLink(BaseModel):
    source: str
    target: str
    relation: str = "related"


class CodeGraphResponse(BaseModel):
    node_count: int
    link_count: int
    nodes: List[GraphNode] = Field(default_factory=list)
    links: List[GraphLink] = Field(default_factory=list)


# GraphAnchor, RelatedEntity, GraphRelatedResponse — used by GET /graph/related (Task 3)
class GraphAnchor(BaseModel):
    id: str
    name: str
    chunk_type: str
    source_file: str


class RelatedEntity(BaseModel):
    id: str
    name: str
    chunk_type: str
    source_file: str
    snippet: Optional[str] = None


class GraphRelatedResponse(BaseModel):
    entity: str
    anchor: Optional[GraphAnchor] = None
    related: List[RelatedEntity] = []
    related_count: int
    ambiguous: bool = False
    all_anchors: List[GraphAnchor] = []
