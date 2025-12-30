import { Markdown, Modal, Segmented } from '@lobehub/ui';
import { Alert, Badge, Button, Input, Select, Spin, message } from 'antd';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Flexbox } from 'react-layout-kit';
import { UIChatMessage } from '@lobechat/types';

import type { CheatsheetAPIResponse, CheatsheetResponse, SupportedLanguage } from '@/features/Cheatsheet/types/cheatsheet';
import CheatsheetMetadataPanel from '@/features/Cheatsheet/components/CheatsheetMetadataPanel';
import ComplexityScoreBadge from '@/features/Cheatsheet/components/ComplexityScoreBadge';
import LibraryDetectionPanel from '@/features/Cheatsheet/components/LibraryDetectionPanel';
import MethodBadge from '@/features/Cheatsheet/components/MethodBadge';
import PromotionSignalBanner from '@/features/Cheatsheet/components/PromotionSignalBanner';

import { useStyles } from '@/features/Cheatsheet/style';

const { TextArea } = Input;

interface CheatsheetModalProps {
    onCancel: () => void;
    open: boolean;
    recentMessages?: UIChatMessage[];
}

const SUPPORTED_LANGUAGES: SupportedLanguage[] = [
    // Full Support - Backend has comprehensive templates
    { label: 'Python ✅', value: 'python', maturity: 'full' },
    { label: 'JavaScript ✅', value: 'javascript', maturity: 'full' },
    { label: 'TypeScript ✅', value: 'typescript', maturity: 'full' },

    // Coming Soon - Planned but not yet supported
    { label: 'Java (Coming Soon)', value: 'java', maturity: 'coming_soon', disabled: true },
    { label: 'Go (Coming Soon)', value: 'go', maturity: 'coming_soon', disabled: true },
    { label: 'Rust (Coming Soon)', value: 'rust', maturity: 'coming_soon', disabled: true },
    { label: 'C++ (Coming Soon)', value: 'cpp', maturity: 'coming_soon', disabled: true },
    { label: 'C# (Coming Soon)', value: 'csharp', maturity: 'coming_soon', disabled: true },
    { label: 'Ruby (Coming Soon)', value: 'ruby', maturity: 'coming_soon', disabled: true },
    { label: 'PHP (Coming Soon)', value: 'php', maturity: 'coming_soon', disabled: true },
    { label: 'Swift (Coming Soon)', value: 'swift', maturity: 'coming_soon', disabled: true },
    { label: 'Kotlin (Coming Soon)', value: 'kotlin', maturity: 'coming_soon', disabled: true },
    { label: 'Bash (Coming Soon)', value: 'bash', maturity: 'coming_soon', disabled: true },
    { label: 'SQL (Coming Soon)', value: 'sql', maturity: 'coming_soon', disabled: true },
    { label: 'HTML (Coming Soon)', value: 'html', maturity: 'coming_soon', disabled: true },
    { label: 'CSS (Coming Soon)', value: 'css', maturity: 'coming_soon', disabled: true },
];

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
    const [responseData, setResponseData] = useState<CheatsheetResponse | null>(null);

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
                        // Only set if it's a supported language
                        const supportedLang = SUPPORTED_LANGUAGES.find(l => l.value === detected && l.maturity === 'full');
                        if (supportedLang) {
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
        setResponseData(null);

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

            const apiResponse: CheatsheetAPIResponse = await response.json();

            if (apiResponse.success && apiResponse.data) {
                // Store full response data for metadata components
                setResponseData(apiResponse.data);

                // Extract markdown for display (with JSON fallback for debugging)
                const markdown = apiResponse.data.markdown ||
                    JSON.stringify(apiResponse.data, null, 2);
                setResult(markdown);
            } else {
                throw new Error(apiResponse.error || 'Unknown error');
            }
        } catch (error) {
            console.error('Failed to generate cheatsheet:', error);
            message.error(t('error.generateFailed'));
            // Clear state on error
            setResponseData(null);
            setResult('');
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
                            options={[
                                {
                                    label: '✅ Full Support',
                                    options: SUPPORTED_LANGUAGES.filter(l => l.maturity === 'full'),
                                },
                                {
                                    label: '🔜 Coming Soon',
                                    options: SUPPORTED_LANGUAGES.filter(l => l.maturity === 'coming_soon'),
                                },
                            ]}
                            placeholder={t('placeholders.language')}
                            style={{ width: 250 }}
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

                    {loading && (
                        <Flexbox align="center" style={{ marginTop: 16 }}>
                            <Spin tip="Generating cheatsheet..." />
                        </Flexbox>
                    )}
                </Flexbox>

                {/* Metadata Dashboard - Only renders if responseData exists */}
                {responseData && (
                    <Flexbox gap={12} style={{ marginTop: 16 }}>
                        {/* Badge Row */}
                        <Flexbox gap={8} horizontal style={{ alignItems: 'center', flexWrap: 'wrap' }}>
                            <MethodBadge method={responseData.method} enrichmentEnabled={responseData.enrichment?.enabled} />
                            <ComplexityScoreBadge
                                score={responseData.complexity_score}
                                suggestedLevel={responseData.skill_level}
                                validationScore={responseData.validation_score}
                            />
                        </Flexbox>

                        {/* Library Detection */}
                        <LibraryDetectionPanel
                            detectedLibraries={responseData.detected_libraries}
                            supportedLibraries={responseData.supported_libraries}
                            webSearchUsed={responseData.web_search_used}
                            sources={responseData.sources}
                        />

                        {/* Collapsible Metadata Panel */}
                        <CheatsheetMetadataPanel data={responseData} />

                        {/* Promotion Signal Banner */}
                        <PromotionSignalBanner
                            enrichedSections={responseData.enrichment?.enriched_sections}
                            promotable={responseData.enrichment?.promotable}
                        />
                    </Flexbox>
                )}

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
