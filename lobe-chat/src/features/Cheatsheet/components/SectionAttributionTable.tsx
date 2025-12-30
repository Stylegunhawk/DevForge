import { Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { memo } from 'react';

import type { CheatsheetSection } from '@/features/Cheatsheet/types/cheatsheet';

interface SectionAttributionTableProps {
    sections?: CheatsheetSection[];
    enrichedSections?: string[];
}

interface SectionRow extends CheatsheetSection {
    key: string;
    source: 'template' | 'ai';
}

/**
 * Table of contents showing which sections are Template vs AI-enhanced
 * Follows principle: Never block markdown rendering - gracefully degrades if data missing
 */
const SectionAttributionTable = memo<SectionAttributionTableProps>(
    ({ sections = [], enrichedSections = [] }) => {
        // Defensive: Don't render if no sections
        if (!sections || sections.length === 0) return null;

        // Transform sections into table rows with source attribution
        const dataSource: SectionRow[] = sections.map((section, index) => ({
            ...section,
            key: `${section.title}-${index}`,
            source: enrichedSections.includes(section.title) ? 'ai' : 'template',
        }));

        const columns: ColumnsType<SectionRow> = [
            {
                dataIndex: 'title',
                key: 'title',
                render: (title: string) => <strong>{title}</strong>,
                title: 'Section',
                width: '70%',
            },
            {
                dataIndex: 'source',
                key: 'source',
                render: (source: 'template' | 'ai') =>
                    source === 'ai' ? (
                        <Tag color="purple">🤖 AI-Enhanced</Tag>
                    ) : (
                        <Tag color="blue">📄 Template</Tag>
                    ),
                title: 'Source',
                width: '30%',
            },
        ];

        return (
            <Table
                bordered
                columns={columns}
                dataSource={dataSource}
                pagination={false}
                size="small"
                style={{ marginTop: 12 }}
            />
        );
    },
);

SectionAttributionTable.displayName = 'SectionAttributionTable';

export default SectionAttributionTable;
