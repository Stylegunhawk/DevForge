import { Tag, Tooltip } from '@lobehub/ui';
import { memo } from 'react';

interface MethodBadgeProps {
    method?: 'template' | 'enriched';
    enrichmentEnabled?: boolean;
}

/**
 * Badge showing generation method (Template vs AI-Enhanced)
 * Follows principle: Never block markdown rendering - gracefully degrades if data missing
 */
const MethodBadge = memo<MethodBadgeProps>(({ method, enrichmentEnabled }) => {
    // Defensive: Don't render if no method provided
    if (!method) return null;

    const isEnriched = method === 'enriched';

    return (
        <Tooltip
            placement="top"
            title={
                isEnriched
                    ? 'AI-Enhanced: This content was generated with LLM assistance for latest syntax and debugging tips'
                    : 'Template: Fast rule-based generation using static templates (<200ms)'
            }
        >
            <Tag color={isEnriched ? 'purple' : 'blue'}>
                {isEnriched ? '🤖 AI-Enhanced' : '⚡ Template'}
            </Tag>
        </Tooltip>
    );
});

MethodBadge.displayName = 'MethodBadge';

export default MethodBadge;
