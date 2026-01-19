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

  uploadFile = async (file: File): Promise<{ id: string; url: string }> => {
    // Default implementation could throw or return undefined if not supported by tRPC
    throw new Error('uploadFile not implemented in RAGService');
  };

  getFile = async (id: string): Promise<any> => {
    throw new Error('getFile not implemented in RAGService');
  };

  deleteFile = async (id: string): Promise<void> => {
    throw new Error('deleteFile not implemented in RAGService');
  };
}

export const ragService = new RAGService();

const USE_CUSTOM_RAG = process.env.NEXT_PUBLIC_USE_CUSTOM_RAG === 'true';

const originalSearch = ragService.semanticSearchForChat.bind(ragService);
const originalParse = ragService.parseFileContent.bind(ragService);

ragService.semanticSearchForChat = (params) => {
  if (USE_CUSTOM_RAG) {
    const { RAGBackendAdapter } = require('./adapters/rag-backend-adapter');
    const adapter = new RAGBackendAdapter();
    return adapter.semanticSearchForChat(params);
  }
  return originalSearch(params);
};

ragService.uploadFile = async (file: File) => {
  if (USE_CUSTOM_RAG) {
    const { RAGBackendAdapter } = require('./adapters/rag-backend-adapter');
    const adapter = new RAGBackendAdapter();
    return adapter.uploadFile(file);
  }
  return ragService.uploadFile(file); // Fallback to default (throw)
};

ragService.parseFileContent = async (id: string, skipExist?: boolean) => {
  if (USE_CUSTOM_RAG) {
    // Stub to preserve UI flow - backend already trigerred ingestion on upload
    return { id, success: true } as any;
  }
  return originalParse(id, skipExist);
};

ragService.getFile = async (id: string) => {
  if (USE_CUSTOM_RAG) {
    const { RAGBackendAdapter } = require('./adapters/rag-backend-adapter');
    const adapter = new RAGBackendAdapter();
    return adapter.getFile(id);
  }
  return ragService.getFile(id);
};

ragService.deleteFile = async (id: string) => {
  if (USE_CUSTOM_RAG) {
    const { RAGBackendAdapter } = require('./adapters/rag-backend-adapter');
    const adapter = new RAGBackendAdapter();
    return adapter.deleteFile(id);
  }
  return ragService.deleteFile(id);
};
