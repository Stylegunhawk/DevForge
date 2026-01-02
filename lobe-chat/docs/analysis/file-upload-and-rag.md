# File Upload and RAG Implementation in Lobe Chat

This document details how file uploads and Retrieval-Augmented Generation (RAG) are implemented in the Lobe Chat codebase.

## 1. File Upload Architecture

Lobe Chat uses a **client-to-storage** upload strategy (Pre-signed URLs) for server mode and direct file operations for Desktop mode.

### Core Components

*   **Frontend Service**: [`src/services/upload.ts`](../../src/services/upload.ts)
    *   `uploadFileToS3`: Main entry point. Determines if running in Desktop or Server mode.
    *   `uploadToServerS3`: Requests a pre-signed URL from the backend and performs a `PUT` request to upload the file directly to S3 (or MinIO).
    *   `uploadToDesktopS3`: Uses Electron IPC to save files locally.
*   **Backend Router**: [`src/server/routers/lambda/upload.ts`](../../src/server/routers/lambda/upload.ts)
    *   `createS3PreSignedUrl`: Generates a secure URL for the frontend to upload files.
*   **S3 Module**: [`src/server/modules/S3`](../../src/server/modules/S3)
    *   Wraps S3 SDK for generating keys/URLs.

### Upload Flow (Server Mode)

1.  **Request URL**: Frontend calls `upload.createS3PreSignedUrl` (TRPC).
2.  **Generate URL**: Backend generates a temporary S3 PUT URL.
3.  **Upload**: Frontend uses `XMLHttpRequest` to upload binary data to the generated URL.
4.  **Database**: File metadata (URL, size, type) is typically stored in the database when the file is associated with a Knowledge Base or Message (via `FileModel`).

---

## 2. RAG (Retrieval-Augmented Generation) Architecture

Lobe Chat's RAG implementation is built on an **Async Task Queue** pattern to handle heavy processing (chunking and embedding) without blocking the UI.

### Core Components

*   **Frontend Service**: [`src/services/rag.ts`](../../src/services/rag.ts)
*   **Backend Routers**:
    *   **Lambda Router**: [`src/server/routers/lambda/chunk.ts`](../../src/server/routers/lambda/chunk.ts) (User-facing API for creating tasks/search)
    *   **Async Router**: [`src/server/routers/async/file.ts`](../../src/server/routers/async/file.ts) (Background worker logic)
*   **Processing Modules**:
    *   **ContentChunk**: [`src/server/modules/ContentChunk`](../../src/server/modules/ContentChunk) (Parsing logic)
    *   **ModelRuntime**: [`src/server/modules/ModelRuntime`](../../src/server/modules/ModelRuntime) (AI Model interaction)

### RAG Workflow

#### Phase 1: Ingestion & Chunking

1.  **Trigger**: Frontend calls `chunk.createParseFileTask`.
2.  **Task Creation**: Backend creates an `AsyncTask` (Status: `Pending`) and returns the Task ID.
3.  **Async Processing**:
    *   The Lambda function triggers an async call to `file.parseFileToChunks`.
    *   **Parsing**: [`ContentChunk`](../../src/server/modules/ContentChunk/index.ts) module parses the file.
        *   **Strategy**: Preferentially uses `Unstructured` (external API) for high-quality parsing (PDFs, images).
        *   **Fallback**: Uses `LangChain` (local JS parsers) if Unstructured is not configured.
    *   **Storage**: Parsed chunks are saved to the `Chunk` database table via `ChunkModel`.
4.  **Auto-Embedding**: If enabled (`CHUNKS_AUTO_EMBEDDING`), it automatically triggers Phase 2.

#### Phase 2: Embedding

1.  **Trigger**: `chunk.createEmbeddingChunksTask` (or auto-trigger).
2.  **Vectorization**:
    *   `file.embeddingChunks` fetches chunks from the database.
    *   It initializes `agentRuntime` with the user's selected provider (OpenAI, Ollama, etc.).
    *   Calls the provider's embedding API (`text-embedding-3-small`, `nomic-embed-text`, etc.).
3.  **Storage**: Vectors are stored in `Embedding` table (Postgres + pgvector).

#### Phase 3: Retrieval (Semantic Search)

1.  **Search**: Frontend calls `chunk.semanticSearchForChat`.
2.  **Query Embedding**: Backend generates an embedding for the user's query.
3.  **Vector Search**:
    *   `ChunkModel.semanticSearch` performs a cosine similarity search in Postgres.
    *   It filters by `fileId` or `knowledgeBaseId`.
4.  **Rank & Return**: Top matches are returned to the LLM context.

### Database Models

*   `FileModel`: Stores file metadata.
*   `ChunkModel`: Stores text content of chunks.
*   `EmbeddingModel`: Stores vector representations (1024/1536 dim).
*   `AsyncTaskModel`: Tracks status of chunking/embedding jobs.

### Key Files Summary

| File | Purpose |
| :--- | :--- |
| `src/services/upload.ts` | Frontend upload logic (S3/Local). |
| `src/server/routers/lambda/chunk.ts` | API for creating tasks and searching. |
| `src/server/routers/async/file.ts` | Background worker for Parsing & Embedding. |
| `src/server/modules/ContentChunk/index.ts` | Wrapper for Unstructured / LangChain parsing. |
| `src/database/models/chunk.ts` | Database operations for chunks. |
