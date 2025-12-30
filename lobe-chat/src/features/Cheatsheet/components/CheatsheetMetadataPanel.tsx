import { Collapse } from '@lobehub/ui';
import { memo, useState } from 'react';
import { Flexbox } from 'react-layout-kit';

import type { CheatsheetResponse } from '@/features/Cheatsheet/types/cheatsheet';
import EnrichmentReasonCard from '@/features/Cheatsheet/components/EnrichmentReasonCard';
import SectionAttributionTable from '@/features/Cheatsheet/components/SectionAttributionTable';

interface CheatsheetMetadataPanelProps {
    data: CheatsheetResponse;
}

const STORAGE_KEY = 'cheatsheet:v1:metadata_expanded';

/**
 * Collapsible metadata panel showing analysis summary, enrichment details, and sections
 * Follows principle: Never block markdown rendering - gracefully degrades if data missing
 */
const CheatsheetMetadataPanel = memo<CheatsheetMetadataPanelProps>(({ data }) => {
    // Load expanded state from localStorage
    const [activeKeys, setActiveKeys] = useState<string[]>(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    });

    // Save expanded state to localStorage
    const handleChange = (keys: string | string[]) => {
        const newKeys = Array.isArray(keys) ? keys : [keys];
        setActiveKeys(newKeys);
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(newKeys));
        } catch {
            // Fail silently if localStorage is not available
        }
    };

    const items = [
        // Analysis Summary Panel
        {
            children: (
                <Flexbox gap={8}>
                    <div>
                        <strong>Language:</strong> {data.language}
                    </div>
                    <div>
                        <strong>Skill Level:</strong> {data.skill_level}
                    </div>
                    {data.detected_libraries && data.detected_libraries.length > 0 && (
                        <div>
                            <strong>Libraries Detected:</strong> {data.detected_libraries.length}
                        </div>
                    )}
                    {data.complexity_score !== undefined && (
                        <div>
                            <strong>Complexity Score:</strong> {data.complexity_score}/100
                        </div>
                    )}
                </Flexbox>
            ),
            key: 'analysis',
            label: '📊 Analysis Summary',
        },
        // Enrichment/LLM Details Panel
        ...((['enriched', 'llm_primary', 'llm_with_search'].includes(data.method || '') || data.enrichment || data.routing_reason)
            ? [
                {
                    children: (
                        <Flexbox gap={12}>
                            <EnrichmentReasonCard
                                reason={data.enrichment?.reason}
                                targetLibraries={data.enrichment?.target_libraries}
                                routingReason={data.routing_reason}
                            />
                            {data.enrichment?.promotable && (
                                <div style={{ color: '#52c41a', fontSize: '12px' }}>
                                    ✨ This content may become a permanent template soon!
                                </div>
                            )}
                        </Flexbox>
                    ),
                    key: 'enrichment',
                    label: '🤖 Enrichment Details',
                },
            ]
            : []),
        // Section Overview Panel
        ...(data.sections && data.sections.length > 0
            ? [
                {
                    children: (
                        <SectionAttributionTable
                            enrichedSections={data.enrichment?.enriched_sections}
                            sections={data.sections}
                        />
                    ),
                    key: 'sections',
                    label: `📑 Sections (${data.sections.length})`,
                },
            ]
            : []),
    ];

    // Don't render if no panels to show
    if (items.length === 0) return null;

    return (
        <Collapse
            activeKey={activeKeys}
            items={items}
            onChange={handleChange}
            style={{ marginTop: 16 }}
        />
    );
});

CheatsheetMetadataPanel.displayName = 'CheatsheetMetadataPanel';

export default CheatsheetMetadataPanel;
