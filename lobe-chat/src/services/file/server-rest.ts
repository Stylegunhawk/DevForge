import { LOBE_CHAT_AUTH_HEADER } from '@lobechat/const';

import { useUserStore } from '@/store/user';
import { keyVaultsConfigSelectors, userProfileSelectors } from '@/store/user/selectors';
import { obfuscatePayloadWithXOR } from '@/utils/client/xor-obfuscation';

import { RAGFileListItem } from '@lobechat/types';

const BASE_URL = process.env.NEXT_PUBLIC_RAG_API_URL!;

export class ServerFileRESTService {
    async getFileItem(id: string): Promise<RAGFileListItem> {
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

    async removeFile(id: string): Promise<void> {
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
