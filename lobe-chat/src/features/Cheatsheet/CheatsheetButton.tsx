import { ActionIcon } from '@lobehub/ui';
import { BookOpenText } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useChatStore } from '@/store/chat';
import { chatSelectors } from '@/store/chat/selectors';

import CheatsheetModal from '@/features/Cheatsheet/CheatsheetModal';


const CheatsheetButton = memo(() => {
    const { t } = useTranslation('cheatsheet');
    const [open, setOpen] = useState(false);

    const recentMessages = useChatStore(chatSelectors.mainAIChats)
        .filter(msg => msg.role === 'user' || msg.role === 'assistant')
        .slice(-10);

    return (
        <>
            <ActionIcon
                icon={BookOpenText}
                onClick={() => setOpen(true)}
                title={t('title')}
                tooltipProps={{ placement: 'bottom' }}
            />
            <CheatsheetModal
                onCancel={() => setOpen(false)}
                open={open}
                recentMessages={recentMessages}
            />
        </>
    );
});

export default CheatsheetButton;
