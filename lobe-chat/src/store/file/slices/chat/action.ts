import { StateCreator } from 'zustand/vanilla';

import { FILE_UPLOAD_BLACKLIST } from '@/const/file';
import { fileService } from '@/services/file';
import { ServerFileRESTService } from '@/services/file/server-rest';
import { ragService } from '@/services/rag';
import {
  UploadFileListDispatch,
  uploadFileListReducer,
} from '@/store/file/reducers/uploadFileList';
import { FileListItem } from '@/types/files';
import { UploadFileItem } from '@/types/files/upload';
import { isChunkingUnsupported } from '@/utils/isChunkingUnsupported';
import { sleep } from '@/utils/sleep';
import { setNamespace } from '@/utils/storeDebug';

import { FileStore } from '../../store';

const n = setNamespace('chat');

const serverFileService = new ServerFileRESTService();

export interface FileAction {
  clearChatUploadFileList: () => void;
  dispatchChatUploadFileList: (payload: UploadFileListDispatch) => void;

  removeChatUploadFile: (id: string) => Promise<void>;
  startAsyncTask: (
    fileId: string,
    runner: (id: string) => Promise<string>,
    onFileItemChange: (fileItem: FileListItem) => void,
  ) => Promise<void>;

  uploadChatFiles: (files: File[]) => Promise<void>;
}

export const createFileSlice: StateCreator<
  FileStore,
  [['zustand/devtools', never]],
  [],
  FileAction
> = (set, get) => ({
  clearChatUploadFileList: () => {
    set({ chatUploadFileList: [] }, false, n('clearChatUploadFileList'));
  },
  dispatchChatUploadFileList: (payload) => {
    const nextValue = uploadFileListReducer(get().chatUploadFileList, payload);
    if (nextValue === get().chatUploadFileList) return;

    set({ chatUploadFileList: nextValue }, false, `dispatchChatFileList/${payload.type}`);
  },
  removeChatUploadFile: async (id) => {
    const { dispatchChatUploadFileList } = get();

    dispatchChatUploadFileList({ id, type: 'removeFile' });

    const USE_CUSTOM_RAG = process.env.NEXT_PUBLIC_USE_CUSTOM_RAG === 'true';

    if (USE_CUSTOM_RAG) {
      await ragService.deleteFile(id);
    } else {
      await fileService.removeFile(id);
    }
  },

  startAsyncTask: async (id, runner, onFileItemUpdate) => {
    await runner(id);

    let isFinished = false;

    while (!isFinished) {
      // 每间隔 2s 查询一次任务状态
      await sleep(2000);

      let fileItem: any = undefined;

      try {
        fileItem = await serverFileService.getFileItem(id);
      } catch (e) {
        console.error('getFileItem Error:', e);
        continue;
      }

      if (!fileItem) return;

      onFileItemUpdate(fileItem);

      if (fileItem.finishEmbedding) {
        isFinished = true;
      }

      // if error, also break
      else if (fileItem.chunkingStatus === 'error' || fileItem.embeddingStatus === 'error') {
        isFinished = true;
      }
    }
  },

  uploadChatFiles: async (rawFiles) => {
    const { dispatchChatUploadFileList } = get();
    // 0. skip file in blacklist
    const files = rawFiles.filter((file) => !FILE_UPLOAD_BLACKLIST.includes(file.name));

    // 1. add files with base64 (Optimistic UI)
    const uploadFiles: UploadFileItem[] = await Promise.all(
      files.map(async (file) => {
        let previewUrl: string | undefined = undefined;
        let base64Url: string | undefined = undefined;

        if (file.type.startsWith('image') || file.type.startsWith('video')) {
          const data = await file.arrayBuffer();
          previewUrl = URL.createObjectURL(new Blob([data!], { type: file.type }));
          const base64 = Buffer.from(data!).toString('base64');
          base64Url = `data:${file.type};base64,${base64}`;
        }

        return { base64Url, file, id: file.name, previewUrl, status: 'pending' } as UploadFileItem;
      }),
    );

    dispatchChatUploadFileList({ files: uploadFiles, type: 'addFiles' });

    // 2. Process Uploads
    const pools = files.map(async (file) => {
      const USE_CUSTOM_RAG = process.env.NEXT_PUBLIC_USE_CUSTOM_RAG === 'true';

      if (USE_CUSTOM_RAG) {
        try {
          // A. Upload to Python Backend
          const res = await ragService.uploadFile(file);

          // B. Update UI: Swap "Filename ID" -> "UUID" & Set Status to Uploading
          dispatchChatUploadFileList({
            id: file.name, // Find item by old ID (filename)
            type: 'updateFile',
            value: {
              fileUrl: res.url,
              id: res.id, // Swap to new UUID
              status: 'uploading',
              uploadState: { progress: 50, restTime: 0, speed: 0 },
            },
          });

          // C. Custom Polling Loop (Replaces startAsyncTask)
          const pollStatus = async () => {
            const MAX_ATTEMPTS = 60; // 2 minutes
            let attempts = 0;

            while (attempts < MAX_ATTEMPTS) {
              await sleep(2000); // Wait 2s

              try {
                // Poll your Custom Backend
                const fileItem = await ragService.getFile(res.id);

                const isFinished = fileItem.finishEmbedding || fileItem.embeddingStatus === 'success';
                const isError = fileItem.chunkingStatus === 'error' || fileItem.embeddingStatus === 'error';

                if (isFinished) {
                  // ✅ Success: Enable Send Button
                  dispatchChatUploadFileList({
                    finishEmbedding: true, 
                    id: res.id,
                    
status: 'success',
                    // Use UUID now
type: 'updateFileStatus',
                  });
                  break;
                }

                if (isError) {
                  dispatchChatUploadFileList({ id: res.id, status: 'error', type: 'updateFileStatus' });
                  break;
                }
              } catch (e) {
                console.error("Polling check failed", e);
              }
              attempts++;
            }
          };

          // Trigger polling (Fire & Forget)
          pollStatus();

        } catch (error) {
          console.error('Custom RAG upload error:', error);
          dispatchChatUploadFileList({ id: file.name, type: 'removeFile' });
          return;
        }
      } else {
        // ... Standard Lobe Chat Logic ...
        let fileResult;
        try {
          fileResult = await get().uploadWithProgress({
            file,
            onStatusUpdate: dispatchChatUploadFileList,
          });
        } catch {
          // ... Error handling ...
          dispatchChatUploadFileList({ id: file.name, type: 'removeFile' });
          return;
        }

        if (!fileResult) return;
        if (isChunkingUnsupported(file.type)) return;

        // Standard startAsyncTask (Lobe default)
        const { startAsyncTask } = get();
        await startAsyncTask(fileResult.id, async (id) => {
          const data = await fileService.parseFileContent(id);
          return data;
        }, (fileItem) => {
          dispatchChatUploadFileList({
            id: fileResult!.id,
            type: 'updateFile',
            value: fileItem,
          });
        });
      }
    });

    await Promise.all(pools);
  },
});
