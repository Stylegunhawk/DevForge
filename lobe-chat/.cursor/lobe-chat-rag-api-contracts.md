# Lobe Chat RAG API Contracts (Code-Verified)

⚠️ **UNIFIED BACKEND CONTRACT (PHASE 15)**
This document reconciled with the backend contract in `src/api/routers/rag.py`.

## 1. Authorization Header

> [!IMPORTANT]
> - **Header Name:** `X-User-ID`
> - **Role:** Identifies the user for strictly isolated collections.
> - **Backend Requirement:** In Phase 15, this header is the PRIMARY source of tenant isolation. If missing, backend falls back to `"default"`, which is **NOT** recommended for production.

## 2. Service Layer (Bridge)
**File:** `src/services/rag.ts`

```typescript
import { lambdaClient } from '@/libs/trpc/client';
import { SemanticSearchSchemaType } from '@/types/rag';

class RAGService {
  parseFileContent = async (id: string, skipExist?: boolean) => {
    return lambdaClient.document.parseFileContent.mutate({ id, skipExist });
  };

  createParseFileTask = async (id: string, skipExist?: boolean) => {
    return lambdaClient.chunk.createParseFileTask.mutate({ id, skipExist });
  };

  retryParseFile = async (id: string) => {
    return lambdaClient.chunk.retryParseFileTask.mutate({ id });
  };

  createEmbeddingChunksTask = async (id: string) => {
    return lambdaClient.chunk.createEmbeddingChunksTask.mutate({ id });
  };

  semanticSearch = async (query: string, fileIds?: string[]) => {
    return lambdaClient.chunk.semanticSearch.mutate({ fileIds, query });
  };

  semanticSearchForChat = async (params: SemanticSearchSchemaType) => {
    return lambdaClient.chunk.semanticSearchForChat.mutate(params);
  };
```

> [!IMPORTANT]
> - `semanticSearchForChat` returns **partially enriched chunks** (no `fileType` or `fileUrl`).
> - **Authoritative Boundary:** UI components **MUST NOT** consume raw `semanticSearchForChat` results. Only message-fetch–hydrated chunks are UI-safe.

  deleteMessageRagQuery = async (id: string) => {
    return lambdaClient.message.removeMessageQuery.mutate({ id });
  };
}

export const ragService = new RAGService();
```

## 2. API Contract (Schema)
**File:** `src/server/routers/lambda/chunk.ts`

### `createParseFileTask` Input Schema
```typescript
z.object({
  id: z.string(),
  skipExist: z.boolean().optional(),
})
```

### `semanticSearchForChat` Input Schema
**Source:** `packages/types/src/rag.ts` (`SemanticSearchSchema`)

```typescript
export const SemanticSearchSchema = z.object({
  fileIds: z.array(z.string()).optional(),      // ⚠️ IGNORED by backend in rag.py:136
  knowledgeIds: z.array(z.string()).optional(), // ⚠️ IGNORED by backend in rag.py:136
  messageId: z.string(),
  model: z.string().optional(),
  rewriteQuery: z.string(),
  userQuery: z.string(),
});
```

> [!WARNING]
> - ❌ **Removed assumption:** Previous docs implied `fileIds` were used for filtering. Code review of `rag.py` shows `agent.retrieve_with_reranking` only uses the collection broad search; direct filtering on `fileIds` is not currently implemented in the frozen contract.

export type SemanticSearchSchemaType = z.infer<typeof SemanticSearchSchema>;

## 3. Data Types (Shape)
**Source:** `packages/types/src/chunk/index.ts`

### `ChatSemanticSearchChunk`
```typescript
export type ChatSemanticSearchChunk = Omit<SemanticSearchChunk, 'metadata' | 'type'>;
```

### `SemanticSearchChunk`
```typescript
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
```

### Supporting Types
```typescript
export interface ChunkMetadata {
  coordinates: Coordinates;
  languages: string[];
  pageNumber?: number;
  parent_id?: string;
  text_as_html?: string;
}

export interface Coordinates {
  layout_height: number;
  layout_width: number;
  points: number[][];
  system: string;
}

export interface Elements {
  element_id: string;
  metadata: ChunkMetadata;
  text: string;
  type: string;
}
```
