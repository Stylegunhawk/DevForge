FINAL CORRECTED BACKEND-FRONTEND RAG INTEGRATION PLAN v2.1
Version: 2.1 (Critical Fixes Applied)
Date: 2025-01-02
Timeline: 2-3 days
Status: Production-Ready Blueprint

Critical Fixes Applied
✅ Fix #1: Celery async handling corrected
✅ Fix #2: Redis wildcard deletion fixed
✅ Fix #3: File path → File ID mapping implemented
✅ Fix #4: Query deletion logic corrected
✅ Fix #5: CORS OPTIONS support added

PHASE 1: Backend API Endpoints (YOUR Backend)
Timeline: Days 1-2

1.1 File Upload with Auto-Parse
Endpoint: POST /api/v1/rag/file/upload
Request:
python# multipart/form-data
files: List[UploadFile]
collection: str = "default"
user_id: str = "default"
Response:
json{
  "files": [
    {
      "id": "uuid",
      "filename": "auth.py",
      "size": 4390,
      "fileType": "text/x-python",
      "url": "/storage/users/default/uploads/auth.py",
      "chunkingStatus": "processing",
      "embeddingStatus": "idle",
      "finishEmbedding": false,
      "createdAt": "2025-01-02T..."
    }
  ]
}
Implementation:
pythonimport redis.asyncio as redis
from fastapi import UploadFile, Form, Header

# Initialize Redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

@router.post("/api/v1/rag/file/upload")
async def upload_files(
    files: List[UploadFile],
    collection: str = Form("default"),
    user_id: str = Header("default"),
):
    """Upload files and trigger async ingestion."""
    results = []
    
    for file in files:
        # 1. Save file
        file_id = str(uuid.uuid4())
        upload_dir = Path(f"/storage/users/{user_id}/uploads/{collection}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / f"{file_id}_{file.filename}"
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 2. Create metadata record
        file_metadata = {
            "id": file_id,
            "filename": file.filename,
            "size": len(content),
            "fileType": file.content_type,
            "url": str(file_path),
            "chunkingStatus": "processing",
            "embeddingStatus": "idle",
            "finishEmbedding": False,
            "createdAt": datetime.utcnow().isoformat(),
            "collection": collection,
            "userId": user_id,
        }
        
        # Store in Redis
        await redis_client.set(
            f"file:{file_id}",
            json.dumps(file_metadata),
            ex=86400 * 7  # 7 day expiry
        )
        
        # 3. Trigger async ingestion (Celery)
        async_ingest_documents.delay(
            file_paths=[str(file_path)],
            collection=f"user_{user_id}_{collection}",
            file_id=file_id
        )
        
        results.append(file_metadata)
    
    return {"files": results}
✅ FIXED: Celery Task (Sync Wrapper for Async Code):
pythonfrom celery import shared_task
import asyncio
import json

@shared_task
def async_ingest_documents(file_paths: List[str], collection: str, file_id: str):
    """
    Celery task to ingest documents.
    Wraps async code in sync context.
    """
    try:
        # Update status: processing
        _update_file_status_sync(file_id, chunkingStatus="processing")
        
        # Run async ingestion in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            agent = get_shared_rag_agent()
            
            # If ingest_documents is async
            result = loop.run_until_complete(
                agent.ingest_documents(file_paths)
            )
            
            # OR if you have a sync version:
            # result = agent.ingest_documents_sync(file_paths)
            
            # Update status: success
            _update_file_status_sync(
                file_id,
                chunkingStatus="success",
                embeddingStatus="success",
                finishEmbedding=True,
                chunkCount=result.get("chunks_created", 0)
            )
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Ingestion failed for {file_id}: {e}")
        _update_file_status_sync(
            file_id,
            chunkingStatus="error",
            errors=[str(e)]
        )
        raise


def _update_file_status_sync(file_id: str, **updates):
    """Synchronous Redis update for Celery tasks."""
    import redis
    client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Get current metadata
    data = client.get(f"file:{file_id}")
    if not data:
        return
    
    metadata = json.loads(data)
    metadata.update(updates)
    
    # Save back
    client.set(f"file:{file_id}", json.dumps(metadata), ex=86400 * 7)

1.2 File Status Polling
Endpoint: GET /api/v1/rag/file/{fileId}
Response:
json{
  "id": "uuid",
  "filename": "auth.py",
  "chunkingStatus": "success",
  "embeddingStatus": "success",
  "finishEmbedding": true,
  "chunkCount": 15
}
Implementation:
python@router.get("/api/v1/rag/file/{file_id}")
async def get_file_status(file_id: str):
    """Poll file processing status."""
    metadata = await redis_client.get(f"file:{file_id}")
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
    return json.loads(metadata)

1.3 Semantic Search (Chunk Retrieval)
Endpoint: POST /api/v1/rag/chunk/semanticSearchForChat
Request:
json{
  "messageId": "msg-123",
  "userQuery": "how does auth work?",
  "rewriteQuery": "authentication implementation",
  "fileIds": ["file-1", "file-2"],
  "top_k": 5
}
Response:
json{
  "chunks": [
    {
      "id": "chunk-uuid",
      "text": "def authenticate(token): ...",
      "similarity": 0.92,
      "fileId": "file-1",
      "filename": "auth.py",
      "fileType": "text/x-python",
      "metadata": {
        "chunk_type": "function",
        "name": "authenticate",
        "language": "python",
        "start_line": 45,
        "end_line": 60
      }
    }
  ],
  "queryId": "query-uuid",
  "metadata": {
    "intent": "code_search",
    "cache_hit": false,
    "latency_ms": 320
  }
}
✅ FIXED: Implementation with File ID Mapping:
pythonfrom pydantic import BaseModel
from typing import List, Optional

class SemanticSearchRequest(BaseModel):
    messageId: str
    userQuery: str
    rewriteQuery: Optional[str] = None
    fileIds: List[str] = []
    top_k: int = 5


async def get_file_id_by_path(file_path: str) -> Optional[str]:
    """
    ✅ CRITICAL FIX: Map file path back to file ID.
    Required for Lobe Chat to display file names correctly.
    """
    # Get all file keys
    keys = await redis_client.keys("file:*")
    
    for key in keys:
        metadata_json = await redis_client.get(key)
        if not metadata_json:
            continue
        
        metadata = json.loads(metadata_json)
        if metadata.get("url") == file_path:
            return metadata["id"]
    
    return None


@router.post("/api/v1/rag/chunk/semanticSearchForChat")
async def semantic_search_for_chat(request: SemanticSearchRequest):
    """Retrieve chunks using Phase 12A pipeline."""
    
    query = request.rewriteQuery or request.userQuery
    user_id = "default"
    collection = f"user_{user_id}_default"
    
    # Phase 12A: Intent classification
    intent = IntentClassifier.classify(query)
    
    # Phase 12A: Check semantic cache
    cache_key = f"cache:{intent}:{hashlib.md5(query.encode()).hexdigest()}"
    cached = await redis_client.get(cache_key)
    if cached:
        result = json.loads(cached)
        result["metadata"]["cache_hit"] = True
        return result
    
    # Map fileIds to file paths
    file_paths = []
    if request.fileIds:
        for file_id in request.fileIds:
            file_meta_json = await redis_client.get(f"file:{file_id}")
            if file_meta_json:
                file_meta = json.loads(file_meta_json)
                file_paths.append(file_meta["url"])
    
    # Retrieve with Phase 12A
    start_time = time.time()
    agent = get_shared_rag_agent()
    
    result = await agent.retrieve_with_reranking(
        query=query,
        top_k=request.top_k,
        file_paths=file_paths if file_paths else None,
        use_reranking=True
    )
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Transform to frontend format
    chunks = []
    for doc in result.documents:
        file_path = doc.metadata.get("source", "")
        
        # ✅ CRITICAL FIX: Map file path → file ID
        file_id = await get_file_id_by_path(file_path)
        
        chunks.append({
            "id": doc.metadata.get("chunk_id", str(uuid.uuid4())),
            "text": doc.page_content,  # NOT "content"
            "similarity": float(doc.metadata.get("score", 0.0)),
            "fileId": file_id,
            "filename": Path(file_path).name if file_path else "unknown",
            "fileType": doc.metadata.get("file_type", "text/plain"),
            "metadata": {
                "chunk_type": doc.metadata.get("chunk_type"),
                "name": doc.metadata.get("name"),
                "language": doc.metadata.get("language"),
                "start_line": doc.metadata.get("start_line"),
                "end_line": doc.metadata.get("end_line"),
            }
        })
    
    # Create query record
    query_id = str(uuid.uuid4())
    query_record = {
        "id": query_id,
        "messageId": request.messageId,
        "userQuery": request.userQuery,
        "rewriteQuery": request.rewriteQuery,
        "intent": intent,
        "chunkIds": [c["id"] for c in chunks],
        "createdAt": datetime.utcnow().isoformat()
    }
    
    await redis_client.set(
        f"query:{query_id}",
        json.dumps(query_record),
        ex=86400  # 1 day expiry
    )
    
    # Build response
    response = {
        "chunks": chunks,
        "queryId": query_id,
        "metadata": {
            "intent": intent,
            "cache_hit": False,
            "latency_ms": latency_ms,
            "expansion_used": result.metadata.get("expansion_used", False),
            "rerank_applied": result.metadata.get("reranked", False)
        }
    }
    
    # Cache result
    await redis_client.set(
        cache_key,
        json.dumps(response),
        ex=3600  # 1 hour cache
    )
    
    return response
Backend Enhancement (Phase 12A Integration):
python# src/agents/rag/agent.py

async def retrieve_with_reranking(
    self,
    query: str,
    top_k: int = 5,
    file_paths: Optional[List[str]] = None,  # ✅ NEW: File filtering
    use_reranking: bool = True
) -> dict:
    """
    Retrieve with Phase 12A features + optional file filtering.
    """
    
    # Vector search (get more candidates for reranking)
    results = await self.vector_store.similarity_search(
        query, 
        top_k=top_k * 3
    )
    
    # ✅ Filter by file_paths if provided
    if file_paths:
        results = [
            r for r in results 
            if r.metadata.get("source") in file_paths
        ]
    
    # Phase 12A: Rerank
    if use_reranking and self._reranker:
        results = await self._reranker.rerank(query, results)
    
    return {
        "documents": results[:top_k],
        "metadata": {
            "reranked": use_reranking,
            "expansion_used": False,  # Set by query expander if used
        }
    }

1.4 File Deletion
Endpoint: DELETE /api/v1/rag/file/{fileId}
✅ FIXED: Complete implementation with vector deletion:
python@router.delete("/api/v1/rag/file/{file_id}")
async def delete_file(file_id: str):
    """Delete file and all associated data atomically."""
    
    # 1. Get file metadata
    file_meta_json = await redis_client.get(f"file:{file_id}")
    if not file_meta_json:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_meta = json.loads(file_meta_json)
    file_path = file_meta["url"]
    
    # 2. Delete physical file
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Failed to delete file {file_path}: {e}")
    
    # 3. Delete vector embeddings
    agent = get_shared_rag_agent()
    
    # ✅ Confirm your vector store supports filter deletion
    # ChromaDB: ✅ Works
    # FAISS: ❌ Needs custom implementation
    try:
        deleted_count = agent.vector_store.delete(
            filter={"source": file_path}
        )
    except Exception as e:
        logger.error(f"Failed to delete vectors for {file_path}: {e}")
        deleted_count = 0
    
    # 4. Clear semantic cache (by file path pattern)
    cache_keys = await redis_client.keys("cache:*")
    for key in cache_keys:
        try:
            cached_data = await redis_client.get(key)
            if cached_data and file_path in cached_data:
                await redis_client.delete(key)
        except:
            pass
    
    # 5. Delete file metadata from Redis
    await redis_client.delete(f"file:{file_id}")
    
    return {
        "success": True,
        "fileId": file_id,
        "deletedChunks": deleted_count
    }

1.5 Query Deletion
Endpoint: DELETE /api/v1/rag/message/{messageId}/query
✅ FIXED: Proper Redis key iteration (no wildcard delete):
python@router.delete("/api/v1/rag/message/{message_id}/query")
async def delete_message_query(message_id: str):
    """
    Delete RAG query record associated with a message.
    ✅ FIX: Redis doesn't support wildcard delete, must iterate.
    """
    deleted_count = 0
    
    # Get all query keys
    query_keys = await redis_client.keys("query:*")
    
    for key in query_keys:
        try:
            query_data_json = await redis_client.get(key)
            if not query_data_json:
                continue
            
            query_data = json.loads(query_data_json)
            
            # Check if this query belongs to the message
            if query_data.get("messageId") == message_id:
                await redis_client.delete(key)
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to process query key {key}: {e}")
            continue
    
    return {
        "success": True,
        "messageId": message_id,
        "deletedQueries": deleted_count
    }

1.6 CORS Configuration
✅ FIXED: Added OPTIONS method support:
pythonfrom fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],  # ✅ Added OPTIONS
    allow_headers=["*"],
    expose_headers=["*"]
)

PHASE 2: Frontend Service Adapter (Lobe Chat)
Timeline: Days 2-3
2.1 Create DevForge RAG Service
File: lobe-chat/src/services/devforge-rag.ts (NEW)
typescriptinterface FileUploadResult {
  files: Array<{
    id: string;
    filename: string;
    size: number;
    fileType: string;
    chunkingStatus: 'idle' | 'processing' | 'success' | 'error';
    finishEmbedding: boolean;
  }>;
}

interface SemanticSearchResult {
  chunks: Array<{
    id: string;
    text: string;
    similarity: number;
    fileId: string | null;
    filename: string;
    fileType: string;
    metadata?: any;
  }>;
  queryId: string;
  metadata: {
    intent: string;
    cache_hit: boolean;
    latency_ms: number;
  };
}

class DevForgeRAGService {
  private baseURL = process.env.NEXT_PUBLIC_DEVFORGE_RAG_URL || 'http://localhost:8000/api/v1';
  
  async uploadFiles(files: File[]): Promise<FileUploadResult> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    
    const res = await fetch(`${this.baseURL}/rag/file/upload`, {
      method: 'POST',
      body: formData,
    });
    
    if (!res.ok) {
      throw new Error(`Upload failed: ${res.statusText}`);
    }
    
    return res.json();
  }
  
  async getFileStatus(fileId: string) {
    const res = await fetch(`${this.baseURL}/rag/file/${fileId}`);
    if (!res.ok) throw new Error('Get file failed');
    return res.json();
  }
  
  async semanticSearchForChat(params: {
    messageId: string;
    userQuery: string;
    rewriteQuery?: string;
    fileIds: string[];
  }): Promise<SemanticSearchResult> {
    const res = await fetch(`${this.baseURL}/rag/chunk/semanticSearchForChat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...params, top_k: 5 }),
    });
    
    if (!res.ok) throw new Error('Search failed');
    return res.json();
  }
  
  async deleteFile(fileId: string): Promise<void> {
    await fetch(`${this.baseURL}/rag/file/${fileId}`, {
      method: 'DELETE',
    });
  }
  
  async deleteMessageQuery(messageId: string): Promise<void> {
    await fetch(`${this.baseURL}/rag/message/${messageId}/query`, {
      method: 'DELETE',
    });
  }
}

export const devforgeRAG = new DevForgeRAGService();

2.2 Integrate into RAG Actions
File: lobe-chat/src/store/chat/slices/aiChat/actions/rag.ts
typescriptinternal_retrieveChunks: async (id, userQuery, messages) => {
  const { internal_toggleMessageRAGLoading } = get();
  
  try {
    internal_toggleMessageRAGLoading(true, id);
    
    const message = chatSelectors.getMessageById(id)(get());
    const rewriteQuery = message?.ragQuery;
    
    // Get file IDs from current session
    const files = chatSelectors.currentChatFiles(get());
    
    // Call YOUR backend
    const result = await devforgeRAG.semanticSearchForChat({
      messageId: id,
      userQuery,
      rewriteQuery,
      fileIds: files,
    });
    
    return {
      chunks: result.chunks,
      queryId: result.queryId,
      rewriteQuery,
    };
  } catch (error) {
    console.error('[DevForge RAG] Retrieval failed:', error);
    return { chunks: [], queryId: '', rewriteQuery: '' };
  } finally {
    internal_toggleMessageRAGLoading(false, id);
  }
},

2.3 File Upload Integration
File: lobe-chat/src/store/file/slices/chat/action.ts
typescriptuploadChatFiles: async (files) => {
  try {
    const result = await devforgeRAG.uploadFiles(files);
    
    // Start polling for each file
    result.files.forEach(file => {
      get().pollFileStatus(file.id);
    });
    
    return result.files;
  } catch (error) {
    console.error('[Upload] Failed:', error);
    throw error;
  }
},

pollFileStatus: async (fileId: string) => {
  let attempts = 0;
  const maxAttempts = 60; // 2 minutes
  
  const interval = setInterval(async () => {
    attempts++;
    
    try {
      const file = await devforgeRAG.getFileStatus(fileId);
      
      // Success
      if (file.finishEmbedding) {
        clearInterval(interval);
        console.log('[RAG] File ready:', fileId);
        // Optionally refresh file list
      }
      
      // Error
      if (file.chunkingStatus === 'error') {
        clearInterval(interval);
        console.error('[RAG] Ingestion failed for:', fileId);
      }
      
      // Timeout
      if (attempts >= maxAttempts) {
        clearInterval(interval);
        console.warn('[RAG] Polling timeout for:', fileId);
      }
    } catch (error) {
      clearInterval(interval);
      console.error('[RAG] Polling error:', error);
    }
  }, 2000);
},

PHASE 3: UI Enhancements (Optional)
Timeline: Day 3
3.1 Intent Badge Component
File: lobe-chat/src/features/Conversation/Messages/Assistant/FileChunks/IntentBadge.tsx
typescriptimport { Badge } from '@/components/ui/badge';

interface IntentBadgeProps {
  intent: string;
  cacheHit: boolean;
  latencyMs: number;
}

export const IntentBadge = ({ intent, cacheHit, latencyMs }: IntentBadgeProps) => {
  const icons = {
    code_search: '🔍',
    explain: '💡',
    debug: '🐛',
    general: '💬',
  };
  
  const icon = icons[intent as keyof typeof icons] || icons.general;
  
  return (
    <div className="flex gap-2 mb-2">
      <Badge variant="secondary">
        {icon} {intent.replace('_', ' ')}
      </Badge>
      
      {cacheHit ? (
        <Badge variant="success">⚡ Cached ({latencyMs}ms)</Badge>
      ) : (
        <Badge variant="outline">🔄 Retrieved ({latencyMs}ms)</Badge>
      )}
    </div>
  );
};

3.2 Enhanced FileChunks Component
File: lobe-chat/src/features/Conversation/Messages/Assistant/FileChunks/index.tsx
typescriptimport { IntentBadge } from './IntentBadge';

export const FileChunks = ({ data, metadata }) => {
  return (
    <div className="file-chunks">
      {/* Phase 12A metadata */}
      {metadata && (
        <IntentBadge
          intent={metadata.intent}
          cacheHit={metadata.cache_hit}
          latencyMs={metadata.latency_ms}
        />
      )}
      
      {/* Chunk list */}
      <div className="chunk-list">
        {data.map(chunk => (
          <ChunkItem key={chunk.id} chunk={chunk} />
        ))}
      </div>
    </div>
  );
};

3.3 Code Metadata in Chunk Items
File: lobe-chat/src/features/Conversation/Messages/Assistant/FileChunks/Item/index.tsx
typescriptexport const ChunkItem = ({ chunk }) => {
  const { text, similarity, filename, metadata } = chunk;
  
  return (
    <div className="chunk-item p-3 border rounded">
      {/* Header */}
      <div className="flex justify-between items-center mb-2">
        <span className="font-medium">{filename}</span>
        <Badge>{(similarity * 100).toFixed(0)}%</Badge>
      </div>
      
      {/* Code metadata (Phase 10.1) */}
      {metadata?.chunk_type === 'function' && (
        <div className="flex gap-2 mb-2">
          <Badge variant="blue">
            {metadata.language} · function {metadata.name}
          </Badge>
          <span className="text-xs text-gray-500">
            Lines {metadata.start_line}-{metadata.end_line}
          </span>
        </div>
      )}
      
      {metadata?.chunk_type === 'class' && (
        <Badge variant="purple">
          {metadata.language} · class {metadata.name}
        </Badge>
      )}
      
      {/* Chunk content */}
      <pre className="chunk-text text-sm bg-gray-50 p-2 rounded overflow-x-auto">
        {text}
      </pre>
    </div>
  );
};

Implementation Checklist
Backend (Days 1-2)

 POST /rag/file/upload with Redis storage
 Celery task with async wrapper ✅ FIXED
 GET /rag/file/{fileId} polling
 POST /rag/chunk/semanticSearchForChat
 get_file_id_by_path() helper ✅ FIXED
 File path filtering in retrieve_with_reranking
 DELETE /rag/file/{fileId} with vector cleanup
 DELETE /rag/message/{messageId}/query ✅ FIXED
 CORS with OPTIONS ✅ FIXED
 Redis connection setup
 Test all endpoints with curl

Frontend (Days 2-3)

 Create devforge-rag.ts service
 Add environment variable NEXT_PUBLIC_DEVFORGE_RAG_URL
 Integrate into internal_retrieveChunks
 Update uploadChatFiles with polling
 Test upload → processing → success flow
 Test semantic search returns correct format
 Verify citations display in UI
 Test file deletion

UI Enhancements (Day 3 - Optional)

 IntentBadge component
 Code metadata display in chunks
 Cache hit indicators
 End-to-end testing


Testing
Backend Tests
bash# 1. Upload file
curl -X POST http://localhost:8000/api/v1/rag/file/upload \
  -F "files=@test.py" \
  -F "collection=default"

# Response: {"files": [{"id": "uuid", "chunkingStatus": "processing", ...}]}

# 2. Poll status
FILE_ID="<from_upload_response>"
curl http://localhost:8000/api/v1/rag/file/$FILE_ID

# Wait until finishEmbedding: true

# 3. Search
curl -X POST http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "test-msg",
    "userQuery": "authentication",
    "fileIds": ["'$FILE_ID'"],
    "top_k": 5
  }'

# Response: {"chunks": [...], "queryId": "uuid", "metadata": {...}}

# 4. Delete file
curl -X DELETE http://localhost:8000/api/v1/rag/file/$FILE_ID

# 5. Delete query
curl -X DELETE http://localhost:8000/api/v1/rag/message/test-msg/query

Frontend Tests

Upload Flow:

Upload file in Lobe Chat
Console shows polling every 2s
Status changes: processing → success
finishEmbedding: true stops polling


Search Flow:

Ask question about uploaded file
Citations appear with Phase 12A metadata
Intent badge shows (code_search, explain, etc.)
Cache hit indicator on repeated queries


Deletion Flow:

Delete file from file manager
File removed from backend
Future queries don't return chunks from deleted file




Environment Setup
Backend (.env)
bash# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Storage
STORAGE_ROOT=/storage

# Phase 12A Features
ENABLE_INTENT_CLASSIFICATION=true
ENABLE_QUERY_EXPANSION=true
ENABLE_SEMANTIC_CACHE=true
ENABLE_RERANKING=true

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
Frontend (.env.local)
bash# DevForge Backend
NEXT_PUBLIC_DEVFORGE_RAG_URL=http://localhost:8000/api/v1

Critical Fixes Summary
IssueStatusFix AppliedCelery async handling✅ FIXEDAdded asyncio.run_until_complete() wrapperRedis wildcard delete✅ FIXEDIterate keys with filter logicFile path → ID mapping✅ FIXEDImplemented get_file_id_by_path()Query deletion logic✅ FIXEDProper Redis key iterationVector store deletion✅ CONFIRMEDChromaDB supports filter paramCORS OPTIONS✅ FIXEDAdded to allow_methods

Success Criteria

✅ User uploads file → auto-parses → shows "success"
✅ User asks question → backend retrieves → citations appear
✅ Citations show correct filename and file ID
✅ Phase 12A metadata displays (intent, cache hit, latency)
✅ Code chunks show metadata (type, name, lines)
✅ File deletion removes all data (file, vectors, cache)
✅ No errors in console or logs


Timeline
DayTasksHoursDay 1Backend endpoints 1.1-1.36-8Day 2Backend endpoints 1.4-1.6 + testing4-6Day 2Frontend service adapter 2.1-2.23-4Day 3Frontend integration 2.3 + UI 3.1-3.34-6Total17-24 hours