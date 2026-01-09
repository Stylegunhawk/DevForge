import { BuiltinRenderProps } from '@lobechat/types';
import { ActionIcon, PreviewGroup } from '@lobehub/ui';
import { Download } from 'lucide-react';
import { memo, useRef } from 'react';
import { Flexbox } from 'react-layout-kit';

import { fileService } from '@/services/file';
import { DallEImageItem } from '@/types/tool/dalle';

import GalleyGrid from './GalleyGrid';
import ImageItem from './Item';

const DallE = memo<BuiltinRenderProps<DallEImageItem[]>>(({ content, messageId }) => {
  const currentRef = useRef<number>(0);

  const handleDownload = async () => {
    const id = content[currentRef.current]?.imageId;
    if (!id) return;

    const { url, name } = await fileService.getFile(id);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
  };

  return (
    <Flexbox gap={16}>
      <PreviewGroup
        preview={{
          toolbarAddon: (
            <ActionIcon
              color="#fff"
              icon={Download}
              onClick={handleDownload}
            />
          ),
        }}
      >
        <GalleyGrid
          items={content.map((c, index) => ({
            ...c,
            messageId,
            // ✅ track index at render time instead
            onClick: () => {
              currentRef.current = index;
            },
          }))}
          renderItem={ImageItem}
        />
      </PreviewGroup>
    </Flexbox>
  );
});

export default DallE;
