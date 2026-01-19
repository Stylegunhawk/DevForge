import { LOBE_CHAT_AUTH_HEADER } from '@lobechat/const';
import { SemanticSearchSchemaType, SemanticSearchResponse } from '@lobechat/types';

import { useUserStore } from '@/store/user';
import { keyVaultsConfigSelectors, userProfileSelectors } from '@/store/user/selectors';
import { obfuscatePayloadWithXOR } from '@/utils/client/xor-obfuscation';

const BASE_URL = process.env.NEXT_PUBLIC_RAG_API_URL!;

export class RAGBackendAdapter {
    async semanticSearchForChat(params: SemanticSearchSchemaType): Promise<SemanticSearchResponse> {
        const userId = userProfileSelectors.userId(useUserStore.getState());
        if (!userId) throw new Error('USER_ID_NOT_FOUND');

        const res = await fetch(`${BASE_URL}/api/v1/rag/chunk/semanticSearchForChat`, {
            body: JSON.stringify({
                messageId: params.messageId,
                rewriteQuery: params.rewriteQuery,
                top_k: 6,
                userQuery: params.userQuery,
            }),
            headers: {
                'Content-Type': 'application/json',
                [LOBE_CHAT_AUTH_HEADER]: this.getAuthHeader(),
                'X-User-ID': userId,
            } as HeadersInit,
            method: 'POST',
        });

        if (!res.ok) throw new Error('RAG_SEARCH_FAILED');

        const data = await res.json();

        return {
            // Strip unsupported fields like 'role' to match strictly formatted UI types
            chunks: (data.chunks || []).map(({ role, ...chunk }: any) => chunk),

            queryId: data.queryId,
        };
    }

    async uploadFile(file: File): Promise<{ id: string; url: string }> {
        const userId = userProfileSelectors.userId(useUserStore.getState());
        if (!userId) throw new Error('USER_ID_NOT_FOUND');

        const formData = new FormData();
        formData.append('files', file);

        const res = await fetch(`${BASE_URL}/api/v1/rag/file/upload`, {
            body: formData,
            headers: {
                [LOBE_CHAT_AUTH_HEADER]: this.getAuthHeader(),
                'X-User-ID': userId,
            } as HeadersInit,
            method: 'POST',
        });

        if (!res.ok) throw new Error('UPLOAD_FAILED');

        const data = await res.json();
        const uploadedFile = data.files?.[0];

        if (!uploadedFile) throw new Error('UPLOAD_FAILED: NO_FILE_RETURNED');

        return {
            id: uploadedFile.id,
            url: uploadedFile.url,
        };
    }

    async getFile(id: string): Promise<any> {
        const userId = userProfileSelectors.userId(useUserStore.getState());
        if (!userId) throw new Error('USER_ID_NOT_FOUND');

        const res = await fetch(`${BASE_URL}/api/v1/rag/file/${id}`, {
            headers: {
                [LOBE_CHAT_AUTH_HEADER]: this.getAuthHeader(),
                'X-User-ID': userId,
            } as HeadersInit,
        });

        if (!res.ok) throw new Error('FILE_NOT_FOUND');
        return res.json();
    }

    async deleteFile(id: string): Promise<void> {
        const userId = userProfileSelectors.userId(useUserStore.getState());
        if (!userId) throw new Error('USER_ID_NOT_FOUND');

        await fetch(`${BASE_URL}/api/v1/rag/file/${id}`, {
            headers: {
                [LOBE_CHAT_AUTH_HEADER]: this.getAuthHeader(),
                'X-User-ID': userId,
            } as HeadersInit,
            method: 'DELETE',
        });
    }

    private getAuthHeader() {
        const accessCode = keyVaultsConfigSelectors.password(useUserStore.getState());
        const userId = userProfileSelectors.userId(useUserStore.getState());

        return obfuscatePayloadWithXOR({ accessCode, userId });
    }
}
