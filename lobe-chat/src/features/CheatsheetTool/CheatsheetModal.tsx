import { Markdown, Modal, Segmented } from '@lobehub/ui';
import { Alert, Badge, Button, Input, Select, message } from 'antd';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Flexbox } from 'react-layout-kit';
import { UIChatMessage } from '@lobechat/types';

import { useStyles } from '@/features/Cheatsheet/style';

const { TextArea } = Input;

interface CheatsheetModalProps {
    onCancel: () => void;
    open: boolean;
    recentMessages?: UIChatMessage[];
}

const LANGUAGES = [
    'python',
    'javascript',
    'typescript',
    'java',
    'go',
    'rust',
    'html',
    'css',
    'cpp',
    'csharp',
    'ruby',
    'php',
    'swift',
    'kotlin',
    'bash',
    'sql',
].map((lang) => ({ label: lang.charAt(0).toUpperCase() + lang.slice(1), value: lang }));

// Helper to extract code blocks from markdown content
const extractCodeBlocks = (messages: UIChatMessage[]) => {
    if (!messages || !Array.isArray(messages)) return '';
    const codeBlocks: string[] = [];
    const regex = /```(\w+)?\n([\S\s]*?)```/g;

    try {
        // Loop through last 10 messages, newest first
        messages.slice(-10).reverse().forEach(msg => {
            if (msg && typeof msg.content === 'string' && msg.content) {
                let match;
                // reset regex index
                regex.lastIndex = 0;
                while ((match = regex.exec(msg.content)) !== null) {
                    const language = match[1] || '';
                    const code = match[2]?.trim();
                    if (code) {
                        codeBlocks.push(`// ${language}\n${code}`);
                    }
                }
            }
        });

        // Limit to 2000 chars
        const combined = codeBlocks.join('\n\n---\n\n');
        return combined.slice(0, 2000);
    } catch (e) {
        console.error('Error extracting code blocks:', e);
        return '';
    }
};

// Function to count code blocks for the badge
const countCodeBlocks = (text: string) => {
    if (!text) return 0;
    return (text.match(/\n\n---\n\n/g) || []).length + 1;
};

const CheatsheetModal = memo<CheatsheetModalProps>(({ open, onCancel, recentMessages }) => {
    const { t } = useTranslation('cheatsheet');
    const { styles } = useStyles();
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState('');

    // Form State
    const [language, setLanguage] = useState<string | undefined>(undefined);
    const [skillLevel, setSkillLevel] = useState<string>('beginner');
    const [codeContext, setCodeContext] = useState('');

    // Auto-populate context from recent messages on open
    useEffect(() => {
        if (open && recentMessages && recentMessages.length > 0) {
            const extracted = extractCodeBlocks(recentMessages);
            if (extracted) {
                setCodeContext(extracted);

                // Auto-detect language if not set
                if (!language) {
                    const firstBlockMatch = /^\/\/ (\w+)/.exec(extracted);
                    if (firstBlockMatch && firstBlockMatch[1]) {
                        const detected = firstBlockMatch[1].toLowerCase();
                        if (LANGUAGES.some(l => l.value === detected)) {
                            setLanguage(detected);
                        }
                    }
                }
            }
        }
    }, [open, recentMessages]);

    const codeBlockCount = useMemo(() => {
        if (!codeContext) return 0;
        return countCodeBlocks(codeContext);
    }, [codeContext]);

    const handleGenerate = async () => {
        if (!language && !codeContext) {
            message.error(t('error.generateFailed') + ' (Please select a language or provide code context)');
            return;
        }

        setLoading(true);
        setResult('');

        try {
            const response = await fetch('http://localhost:8001/api/gateway', {
                body: JSON.stringify({
                    arguments: {
                        code_context: codeContext || undefined,
                        language,
                        skill_level: skillLevel,
                    },
                    name: 'generate_cheatsheet',
                }),
                headers: {
                    'Content-Type': 'application/json',
                },
                method: 'POST',
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            // Backend returns: { success: true, data: { markdown: "...", ... } }
            setResult(data.data.markdown || data.data.cheatsheet || JSON.stringify(data.data, null, 2));
        } catch (error) {
            console.error('Failed to generate cheatsheet:', error);
            message.error(t('error.generateFailed'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal
            destroyOnHidden
            footer={null}
            onCancel={onCancel}
            open={open}
            title={t('title')}
            width={1000}
        >
            <Flexbox className={styles.container}>
                <Flexbox className={styles.form}>
                    <Flexbox gap={16} horizontal>
                        <Select
                            allowClear
                            onChange={setLanguage}
                            options={LANGUAGES}
                            placeholder={t('placeholders.language')}
                            style={{ width: 200 }}
                            value={language}
                        />
                        <Segmented
                            onChange={(v) => setSkillLevel(v as string)}
                            options={[
                                { label: t('options.beginner'), value: 'beginner' },
                                { label: t('options.intermediate'), value: 'intermediate' },
                                { label: t('options.expert'), value: 'expert' },
                            ]}
                            value={skillLevel}
                        />
                    </Flexbox>

                    <Flexbox align="center" distribution="space-between" horizontal style={{ marginTop: 16 }}>
                        <Flexbox align="center" gap={8} horizontal>
                            <div style={{ fontWeight: 'bold' }}>{t('labels.context')}</div>
                            <Badge
                                count={codeBlockCount}
                                showZero={false}
                                style={{ backgroundColor: '#108ee9' }}
                                title={t('status.codeBlocksFound', { count: codeBlockCount })}
                            />
                        </Flexbox>
                        <Button
                            danger
                            onClick={() => setCodeContext('')}
                            size="small"
                            type="link"
                        >
                            {t('action.clearContext')}
                        </Button>
                    </Flexbox>

                    <TextArea
                        autoSize={{ maxRows: 12, minRows: 6 }}
                        className={styles.codeEditor}
                        onChange={(e) => setCodeContext(e.target.value)}
                        placeholder={t('placeholders.context')}
                        style={{ marginTop: 8 }}
                        value={codeContext}
                    />

                    {!codeContext && (
                        <Alert
                            message={t('status.noCodeFound')}
                            showIcon
                            style={{ marginTop: 8 }}
                            type="warning"
                        />
                    )}

                    <Flexbox className={styles.actions}>
                        <Button onClick={onCancel}>{t('action.cancel')}</Button>
                        <Button loading={loading} onClick={handleGenerate} type="primary">
                            {t('action.generate')}
                        </Button>
                    </Flexbox>
                </Flexbox>

                {result && (
                    <>
                        <div style={{ fontWeight: 'bold', marginTop: 16 }}>{t('labels.generatedTitle')}</div>
                        <div className={styles.outputContainer}>
                            <Markdown>{result}</Markdown>
                        </div>
                    </>
                )}
            </Flexbox>
        </Modal>
    );
});

export default CheatsheetModal;
