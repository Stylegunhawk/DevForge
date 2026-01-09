# Lobe Chat RAG API Contracts

This document outlines the exact API contracts and data structures used by Lobe Chat's RAG implementation, intended for backend integration.

## 1. Service Layer (Bridge)
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
  fileIds: z.array(z.string()).optional(),
  knowledgeIds: z.array(z.string()).optional(),
  messageId: z.string(),
  model: z.string().optional(),
  rewriteQuery: z.string(),
  userQuery: z.string(),
});

export type SemanticSearchSchemaType = z.infer<typeof SemanticSearchSchema>;
```

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
