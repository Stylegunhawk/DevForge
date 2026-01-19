/**
 * RAG Backend Data Contracts - TypeScript Reference
 * 
 * Copy these exact interfaces into your backend type definitions
 * to ensure 100% compatibility with lobe-chat frontend.
 */

// ============================================================================
// 1. CHUNK RETRIEVAL TYPES
// ============================================================================

/**
 * Primary interface for semantic search chunk results
 * Source: packages/types/src/chunk/index.ts
 */
export interface ChatSemanticSearchChunk {
    fileId: string | null;
    fileName: string | null;
    id: string;
    pageNumber?: number | null;
    similarity: number;
    text: string | null;
}

/**
 * Extended interface used by UI components
 * Source: packages/types/src/message/ui/rag.ts
 */
export interface ChatFileChunk {
    fileId: string;        // REQUIRED
    fileType: string;      // REQUIRED (Injected during Message Fetch)
    fileUrl: string;       // REQUIRED (Injected during Message Fetch)
    filename: string;      // REQUIRED
    id: string;            // REQUIRED
    similarity?: number;   // OPTIONAL (will be displayed with .toFixed(1))
    text: string;          // REQUIRED
    // ⚠️ role is NOT AVAILABLE (SQL selection missing in Node.js model)
}

/**
 * Semantic search response from backend
 */
export interface SemanticSearchResponse {
    chunks: ChatFileChunk[]; // ⚠️ Partially enriched (no fileType/fileUrl)
    queryId?: string;
}

> [!IMPORTANT]
> **Authoritative Boundary:** UI components **MUST NOT** consume raw `SemanticSearchResponse.chunks`. Only message-fetch–hydrated chunks are UI-safe.

// ============================================================================
// 2. ASYNC TASK STATUS TYPES
// ============================================================================

/**
 * Status enum for chunking and embedding tasks
 * ⚠️ CRITICAL: Must use exact lowercase string literals
 * Source: packages/types/src/asyncTask.ts
 */
export enum AsyncTaskStatus {
    Error = 'error',
    Pending = 'pending',
    Processing = 'processing',
    Success = 'success',
}

// As TypeScript union type (for JSON responses):
export type AsyncTaskStatusString = 'error' | 'pending' | 'processing' | 'success';

/**
 * Error structure for async tasks
 */
export interface IAsyncTaskError {
    name: string;  // e.g., "NoChunkError", "EmbeddingError", "TaskTriggerError"
    body: string | { detail: string };
}

/**
 * File parsing task status
 * Source: packages/types/src/asyncTask.ts
 */
export interface FileParsingTask {
    chunkCount?: number | null;
    chunkingError?: IAsyncTaskError | null;
    chunkingStatus?: AsyncTaskStatus | null;
    embeddingError?: IAsyncTaskError | null;
    embeddingStatus?: AsyncTaskStatus | null;
    finishEmbedding?: boolean;
}

// ============================================================================
// 3. RAG SEARCH REQUEST TYPES
// ============================================================================

/**
 * Semantic search request payload
 * Source: packages/types/src/rag.ts
 */
export interface SemanticSearchRequest {
    fileIds?: string[];       // ⚠️ IGNORED: Currently not used by backend filtering
    knowledgeIds?: string[];  // ⚠️ IGNORED: Currently not used by backend filtering
    messageId: string;        // Required: for tracking
    model?: string;           // Optional: embedding model name
    rewriteQuery: string;     // Required: LLM-optimized query
    userQuery: string;        // Required: original user query
}

/**
 * Chunk reference stored in message
 */
export interface MessageSemanticSearchChunk {
    id: string;
    similarity: number;
}

// ============================================================================
// 4. FILE ITEM RESPONSE (for polling)
// ============================================================================

/**
 * File item returned by getFileItem(id) during polling
 * Frontend polls this endpoint every 2 seconds
 */
export interface FileListItem extends FileParsingTask {
    id: string;
    name: string;
    size?: number;
    url?: string;
    type?: string;
    createdAt?: string;
    updatedAt?: string;
    // ... other metadata

    // FileParsingTask fields (required for polling):
    chunkCount?: number | null;
    chunkingError?: IAsyncTaskError | null;
    chunkingStatus?: AsyncTaskStatusString | null;
    embeddingError?: IAsyncTaskError | null;
    embeddingStatus?: AsyncTaskStatusString | null;
    finishEmbedding?: boolean;  // ⚠️ Set to true when both tasks complete
}

// ============================================================================
// 5. BACKEND API CONTRACTS
// ============================================================================

/**
 * Your backend must implement these endpoints:
 */

// POST /api/rag/semanticSearchForChat
interface SemanticSearchAPI {
    request: SemanticSearchRequest;
    response: SemanticSearchResponse;
}

// GET /api/files/:id
interface GetFileItemAPI {
    params: { id: string };
    response: FileListItem;
}

// ============================================================================
// 6. VALIDATION SCHEMAS (Zod)
// ============================================================================

/**
 * If using Zod for validation, these match the frontend schemas
 */
import { z } from 'zod';

export const ChatFileChunkSchema = z.object({
    fileId: z.string(),
    fileType: z.string(),
    fileUrl: z.string(),
    filename: z.string(),
    id: z.string(),
    similarity: z.number().optional(),
    text: z.string(),
    pageNumber: z.number().optional(),
});

export const AsyncTaskStatusSchema = z.enum(['error', 'pending', 'processing', 'success']);

export const IAsyncTaskErrorSchema = z.object({
    name: z.string(),
    body: z.union([
        z.string(),
        z.object({ detail: z.string() })
    ]),
});

export const FileParsingTaskSchema = z.object({
    chunkCount: z.number().nullable().optional(),
    chunkingError: IAsyncTaskErrorSchema.nullable().optional(),
    chunkingStatus: AsyncTaskStatusSchema.nullable().optional(),
    embeddingError: IAsyncTaskErrorSchema.nullable().optional(),
    embeddingStatus: AsyncTaskStatusSchema.nullable().optional(),
    finishEmbedding: z.boolean().optional(),
});

export const SemanticSearchRequestSchema = z.object({
    fileIds: z.array(z.string()).optional(),      // ⚠️ IGNORED by backend
    knowledgeIds: z.array(z.string()).optional(), // ⚠️ IGNORED by backend
    messageId: z.string(),
    model: z.string().optional(),
    rewriteQuery: z.string(),
    userQuery: z.string(),
});

export const SemanticSearchResponseSchema = z.object({
    chunks: z.array(ChatFileChunkSchema),
    queryId: z.string().optional(),
});

// ============================================================================
// 7. EXAMPLE RESPONSES
// ============================================================================

/**
 * Example 1: Semantic Search Response
 */
const exampleSemanticSearchResponse: SemanticSearchResponse = {
    chunks: [
        {
            id: "chunk_abc123",
            fileId: "file_xyz789",
            filename: "documentation.pdf",
            fileType: "application/pdf",
            fileUrl: "https://storage.example.com/files/file_xyz789.pdf",
            text: "Retrieval-Augmented Generation (RAG) combines retrieval and generation...",
            similarity: 0.8472,
            pageNumber: 5,
        },
        {
            id: "chunk_def456",
            fileId: "file_xyz789",
            filename: "documentation.pdf",
            fileType: "application/pdf",
            fileUrl: "https://storage.example.com/files/file_xyz789.pdf",
            text: "To implement RAG, you need three components: retriever, context builder...",
            similarity: 0.7891,
            pageNumber: 12,
        },
    ],
    queryId: "query_ghi789",
};

/**
 * Example 2: File Item During Processing
 */
const exampleFileItemProcessing: FileListItem = {
    id: "file_xyz789",
    name: "documentation.pdf",
    type: "application/pdf",
    size: 2048000,
    url: "https://storage.example.com/files/file_xyz789.pdf",
    chunkingStatus: "success",
    embeddingStatus: "processing",
    chunkCount: 42,
    finishEmbedding: false,
};

/**
 * Example 3: File Item Completed
 */
const exampleFileItemComplete: FileListItem = {
    id: "file_xyz789",
    name: "documentation.pdf",
    type: "application/pdf",
    size: 2048000,
    url: "https://storage.example.com/files/file_xyz789.pdf",
    chunkingStatus: "success",
    embeddingStatus: "success",
    chunkCount: 42,
    finishEmbedding: true,  // ⚠️ This signals completion to frontend
};

/**
 * Example 4: File Item With Error
 */
const exampleFileItemError: FileListItem = {
    id: "file_xyz789",
    name: "corrupted.pdf",
    type: "application/pdf",
    chunkingStatus: "error",
    chunkingError: {
        name: "NoChunkError",
        body: {
            detail: "Failed to parse file: corrupted PDF structure detected"
        }
    },
    finishEmbedding: false,
};

// ============================================================================
// 8. CRITICAL REMINDERS
// ============================================================================

/**
 * ⚠️ MUST USE EXACT STRING LITERALS:
 * - chunkingStatus/embeddingStatus: ONLY 'error' | 'pending' | 'processing' | 'success'
 * - NOT: 'failed', 'in_progress', 'completed', 'done', etc.
 * 
 * ⚠️ POLLING COMPLETION:
 * Frontend checks EVERY 2 SECONDS and stops when:
 * - finishEmbedding === true (success), OR
 * - chunkingStatus === 'error' OR embeddingStatus === 'error' (failure)
 * 
 * ⚠️ FILE TYPES:
 * - Must be valid MIME types (e.g., "application/pdf", NOT "pdf")
 * - Used by FileIcon component for display
 * 
 * ⚠️ SIMILARITY:
 * - Must be a NUMBER, not a string
 * - Displayed as: similarity.toFixed(1) (e.g., 0.847 → "0.8")
 */
