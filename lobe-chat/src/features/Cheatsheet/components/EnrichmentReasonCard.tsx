import { Alert } from 'antd';
import { memo } from 'react';
import { Flexbox } from 'react-layout-kit';

import { getEnrichmentReasonMessage } from '@/features/Cheatsheet/types/cheatsheet';

interface EnrichmentReasonCardProps {
    reason?: string;
    targetLibraries?: string[];
    routingReason?: string;
}

const ROUTING_REASONS: Record<string, string> = {
    'unsupported_language:sql': '🗄️ SQL is not supported by templates (Using LLM)',
    'fast_evolving_lib:langchain': '🚀 LangChain changes frequently (Using Live Data)',
    'template_available': '⚡ Using optimized template',
    'complex_query': '🧠 Complex query requires reasoning',
};

/**
 * Maps backend enrichment/routing codes to user-friendly messages
 */
const EnrichmentReasonCard = memo<EnrichmentReasonCardProps>(({ reason, targetLibraries = [], routingReason }) => {
    // Determine which message to show (Enrichment Reason OR Routing Reason)
    const effectiveReason = routingReason || reason;

    // Defensive: Don't render if no reason provided
    if (!effectiveReason) return null;

    // Use specific routing message map, or fallback to generic enrichment map
    let message = ROUTING_REASONS[effectiveReason];
    if (!message) {
        message = getEnrichmentReasonMessage(effectiveReason);
    }

    // If routing reason looks like "unsupported_language:x", format it nicely
    if (!message && effectiveReason.startsWith('unsupported_language')) {
        const lang = effectiveReason.split(':')[1] || 'Detected';
        message = `🗄️ ${lang.toUpperCase()} uses standard generation (No templates)`;
    }

    const hasLibraries = targetLibraries && targetLibraries.length > 0;

    return (
        <Alert
            description={
                hasLibraries && (
                    <Flexbox gap={4} style={{ marginTop: 8 }}>
                        <div style={{ fontSize: '12px', opacity: 0.8 }}>
                            Target libraries: {targetLibraries.join(', ')}
                        </div>
                    </Flexbox>
                )
            }
            message={message || effectiveReason}
            showIcon
            type="info"
        />
    );
});

EnrichmentReasonCard.displayName = 'EnrichmentReasonCard';

export default EnrichmentReasonCard;
