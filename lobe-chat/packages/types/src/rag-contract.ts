export type RAGAsyncTaskStatus = 'pending' | 'processing' | 'success' | 'error';

export interface BackendChunk {
    fileId: string;
    fileType?: string;
    fileUrl?: string;
    filename: string;
    id: string;
    pageNumber?: number | null;
    similarity: number;
    text: string;
}

export interface SemanticSearchResponse {
    chunks: BackendChunk[];
    queryId?: string;
}

export interface RAGFileListItem {
    chunkingStatus?: RAGAsyncTaskStatus | null;
    embeddingStatus?: RAGAsyncTaskStatus | null;
    finishEmbedding?: boolean;
    id: string;
    name: string;
}
