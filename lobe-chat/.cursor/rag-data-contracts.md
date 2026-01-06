# RAG Backend Data Contracts - Frontend Requirements

This document contains the **exact** TypeScript interfaces and string literals that your RAG backend must match to prevent UI crashes.

## 1. ChatSemanticSearchChunk Interface (Primary Retrieval Result)

### Full Type Definition

```typescript
// Source: packages/types/src/chunk/index.ts
export interface SemanticSearchChunk {
  fileId: string | null;
  fileName: string | null;
  id: string;
  metadata: ChunkMetadata | null;
  pageNumber?: number | null;
  similarity: number;
  text: string | null;
  type: string | null;
}

export type ChatSemanticSearchChunk = Omit<SemanticSearchChunk, 'metadata' | 'type'>;
```

### Resolved Interface (Used by Frontend)

```typescript
export interface ChatSemanticSearchChunk {
  fileId: string | null;
  fileName: string | null;
  id: string;
  pageNumber?: number | null;
  similarity: number;
  text: string | null;
}
```

### Required Fields for UI Display

The `ChatFileChunk` interface used by UI components extends this with display metadata:

```typescript
// Source: packages/types/src/message/ui/rag.ts
export interface ChatFileChunk {
  fileId: string;        // REQUIRED for opening file preview
  fileType: string;      // REQUIRED for FileIcon component
  fileUrl: string;       // REQUIRED (though not directly used in ChunkItem)
  filename: string;      // REQUIRED for display
  id: string;            // REQUIRED (chunk ID)
  similarity?: number;   // OPTIONAL but displayed as badge if present
  text: string;          // REQUIRED for preview on click
}
```

### Backend Response Schema

Your backend semantic search endpoint must return:

```typescript
{
  chunks: ChatFileChunk[],  // Array of chunks matching above interface
  queryId?: string,          // Optional RAG query tracking ID
}
```

### Critical Notes

1. **`fileType`** must be a valid MIME type (e.g., `"application/pdf"`, `"text/plain"`) for the FileIcon component
2. **`similarity`** should be a floating point number (displayed with `.toFixed(1)`)
3. **`text`** is displayed in the file preview modal when chunk is clicked
4. **`filename`** is displayed directly in the UI - keep it user-friendly

---

## 2. Async Task Status Enums

### AsyncTaskStatus (for chunking and embedding)

```typescript
// Source: packages/types/src/asyncTask.ts
export enum AsyncTaskStatus {
  Error = 'error',         // ⚠️ String literal: 'error'
  Pending = 'pending',     // ⚠️ String literal: 'pending'
  Processing = 'processing', // ⚠️ String literal: 'processing'
  Success = 'success',     // ⚠️ String literal: 'success'
}
```

### ⚠️ CRITICAL: Exact String Values

Your backend JSON responses **MUST** use these exact lowercase strings:

- `"error"` - NOT `"failed"`, `"ERROR"`, or `"failure"`
- `"pending"` - NOT `"queued"`, `"waiting"`, or `"PENDING"`
- `"processing"` - NOT `"in_progress"`, `"running"`, or `"uploading"`
- `"success"` - NOT `"completed"`, `"done"`, or `"finished"`

### Usage in File Status

```typescript
// Source: packages/types/src/asyncTask.ts
export interface FileParsingTask {
  chunkCount?: number | null;
  chunkingError?: IAsyncTaskError | null;
  chunkingStatus?: AsyncTaskStatus | null;  // Must be: 'error' | 'pending' | 'processing' | 'success'
  embeddingError?: IAsyncTaskError | null;
  embeddingStatus?: AsyncTaskStatus | null; // Must be: 'error' | 'pending' | 'processing' | 'success'
  finishEmbedding?: boolean;
}
```

### Status Flow Examples

**Normal flow:**
```json
{
  "chunkingStatus": "pending",
  "embeddingStatus": null
}
→
{
  "chunkingStatus": "processing",
  "embeddingStatus": null
}
→
{
  "chunkingStatus": "success",
  "embeddingStatus": "processing",
  "chunkCount": 42
}
→
{
  "chunkingStatus": "success",
  "embeddingStatus": "success",
  "chunkCount": 42,
  "finishEmbedding": true
}
```

**Error flow:**
```json
{
  "chunkingStatus": "error",
  "chunkingError": {
    "name": "NoChunkError",
    "body": { "detail": "File parsing failed: unsupported format" }
  }
}
```

---

## 3. ChunkItem Component Props

### What Gets Rendered

```typescript
// Source: src/features/Conversation/Messages/Assistant/FileChunks/Item/index.tsx
export interface ChunkItemProps extends ChatFileChunk {
  index: number;  // Added by parent component
}

// Used props in rendering:
- fileType     → FileIcon component (determines icon based on MIME type)
- filename     → Displayed as text label
- similarity   → Badge with tooltip (shows similarity.toFixed(1))
- id           → Key and for preview
- fileId       → Opens file preview modal
- text         → Shown in preview modal
```

### FileIcon Requirements

The `fileType` property is passed to `<FileIcon />` which expects standard MIME types:

- PDFs: `"application/pdf"`
- Word: `"application/vnd.openxmlformats-officedocument.wordprocessingml.document"`
- Text: `"text/plain"`, `"text/markdown"`
- Images: `"image/jpeg"`, `"image/png"`
- etc.

### Similarity Display

If `similarity` is present, it's displayed as:
```jsx
<Tooltip title={similarity}>
  <Badge>{similarity.toFixed(1)}</Badge>
</Tooltip>
```

Example: `0.847` displays as `"0.8"`

---

## 4. File Status Polling Logic

### Polling Implementation

```typescript
// Source: src/store/file/slices/chat/action.ts
async function startAsyncTask(id, runner, onFileItemUpdate) {
  await runner(id);  // Start the task
  
  let isFinished = false;
  
  while (!isFinished) {
    await sleep(2000);  // ⏰ Poll every 2 seconds
    
    const fileItem = await serverFileService.getFileItem(id);
    
    onFileItemUpdate(fileItem);  // Update UI
    
    // ✅ Success condition
    if (fileItem.finishEmbedding) {
      isFinished = true;
    }
    
    // ❌ Error condition
    else if (fileItem.chunkingStatus === 'error' || fileItem.embeddingStatus === 'error') {
      isFinished = true;
    }
  }
}
```

### Backend Requirements

Your `getFileItem(id)` endpoint must return:

```typescript
{
  id: string;
  chunkingStatus: 'pending' | 'processing' | 'success' | 'error' | null;
  embeddingStatus: 'pending' | 'processing' | 'success' | 'error' | null;
  chunkingError?: {
    name: string;
    body: string | { detail: string };
  };
  embeddingError?: {
    name: string;
    body: string | { detail: string };
  };
  chunkCount?: number | null;
  finishEmbedding?: boolean;  // ⚠️ CRITICAL: Set to true when BOTH chunking and embedding are complete
  // ... other file metadata
}
```

### Completion Detection

The frontend considers processing complete when **either**:

1. ✅ `finishEmbedding === true` (success)
2. ❌ `chunkingStatus === 'error'` OR `embeddingStatus === 'error'` (failure)

### Error Structure

Errors must follow this interface:

```typescript
export interface IAsyncTaskError {
  name: string;  // Error type (e.g., "NoChunkError", "EmbeddingError")
  body: string | { detail: string };  // Error message
}
```

Example error response:
```json
{
  "chunkingStatus": "error",
  "chunkingError": {
    "name": "TaskTriggerError",
    "body": {
      "detail": "Failed to start chunking task: service unavailable"
    }
  }
}
```

---

## 5. RAG Search Request Schema

### Semantic Search Request

```typescript
// Source: packages/types/src/rag.ts
export const SemanticSearchSchema = z.object({
  fileIds: z.array(z.string()).optional(),      // Files to search in
  knowledgeIds: z.array(z.string()).optional(), // Knowledge bases to search
  messageId: z.string(),                         // For tracking
  model: z.string().optional(),                  // Embedding model
  rewriteQuery: z.string(),                      // LLM-optimized query
  userQuery: z.string(),                         // Original user query
});

export type SemanticSearchSchemaType = z.infer<typeof SemanticSearchSchema>;
```

### Example Request

```json
{
  "messageId": "msg_abc123",
  "userQuery": "How do I implement RAG?",
  "rewriteQuery": "What are the steps to implement Retrieval-Augmented Generation in a chat system?",
  "fileIds": ["file_1", "file_2"],
  "knowledgeIds": ["kb_general"],
  "model": "text-embedding-3-small"
}
```

---

## 6. FileChunks Component Props

### Component Interface

```typescript
// Source: src/features/Conversation/Messages/Assistant/FileChunks/index.tsx
interface FileChunksProps {
  data: ChatFileChunk[];  // Array of chunks to display
}
```

### Rendering Behavior

- Renders expandable/collapsible section
- Shows count: `"Referenced Chunks (N)"`
- Maps `data` array to `<ChunkItem />` components
- Empty array → component doesn't render (parent checks `chunksList.length > 0`)

---

## 7. Quick Reference: JSON Schema

### Backend Response Schema (JSON)

```json
{
  "chunks": [
    {
      "id": "chunk_abc123",
      "fileId": "file_xyz789",
      "filename": "documentation.pdf",
      "fileType": "application/pdf",
      "fileUrl": "https://example.com/files/file_xyz789",
      "text": "Retrieval-Augmented Generation (RAG) is a technique...",
      "similarity": 0.8472,
      "pageNumber": 5
    }
  ],
  "queryId": "query_def456"
}
```

### File Status Response (JSON)

```json
{
  "id": "file_xyz789",
  "name": "documentation.pdf",
  "chunkingStatus": "success",
  "embeddingStatus": "processing",
  "chunkCount": 42,
  "finishEmbedding": false
}
```

---

## 8. Validation Checklist

Before deploying your backend, verify:

- [ ] `chunkingStatus` only uses: `"pending"`, `"processing"`, `"success"`, `"error"`, or `null`
- [ ] `embeddingStatus` only uses: `"pending"`, `"processing"`, `"success"`, `"error"`, or `null`
- [ ] `finishEmbedding` is set to `true` when embedding completes successfully
- [ ] `fileType` contains valid MIME type strings
- [ ] `similarity` is a number (not a string)
- [ ] `chunks` array contains objects with all required fields: `id`, `fileId`, `filename`, `fileType`, `fileUrl`, `text`
- [ ] Error objects have both `name` (string) and `body` (string or `{ detail: string }`)
- [ ] Polling endpoint returns data every 2 seconds without rate limiting

---

## 9. Common Pitfalls

### ❌ Wrong Status Values
```json
// WRONG
{ "chunkingStatus": "in_progress" }
{ "embeddingStatus": "PROCESSING" }
{ "chunkingStatus": "completed" }

// CORRECT
{ "chunkingStatus": "processing" }
{ "embeddingStatus": "processing" }
{ "chunkingStatus": "success" }
```

### ❌ Missing Required Fields
```json
// WRONG - Missing fileType and fileUrl
{
  "id": "chunk_1",
  "fileId": "file_1",
  "filename": "doc.pdf",
  "text": "...",
  "similarity": 0.8
}

// CORRECT
{
  "id": "chunk_1",
  "fileId": "file_1",
  "filename": "doc.pdf",
  "fileType": "application/pdf",
  "fileUrl": "https://...",
  "text": "...",
  "similarity": 0.8
}
```

### ❌ Wrong Data Types
```json
// WRONG - similarity as string
{ "similarity": "0.847" }

// CORRECT - similarity as number
{ "similarity": 0.847 }
```

---

## Summary

Your backend must:

1. Return `ChatFileChunk[]` with exact field names and types
2. Use only the 4 allowed status strings: `"pending"`, `"processing"`, `"success"`, `"error"`
3. Set `finishEmbedding: true` when processing completes
4. Support polling every 2 seconds without errors
5. Include valid MIME types in `fileType`
6. Return numerical `similarity` scores

Deviation from these contracts will cause TypeScript errors, runtime crashes, or broken UI components.
