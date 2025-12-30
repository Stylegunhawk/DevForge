import { Alert } from 'antd';
import { memo } from 'react';

interface PromotionSignalBannerProps {
    enrichedSections?: string[];
    promotable?: boolean;
}

/**
 * Banner shown when content is promotable (enriched >3 times)
 * Signals that this content may become a permanent template
 * Follows principle: Never block markdown rendering - gracefully degrades if data missing
 */
const PromotionSignalBanner = memo<PromotionSignalBannerProps>(
    ({ enrichedSections = [], promotable = false }) => {
        // Defensive: Don't render if not promotable
        if (!promotable) return null;

        return (
            <Alert
                closable
                description={
                    <div style={{ fontSize: '12px', marginTop: 4 }}>
                        This content has been AI-enhanced multiple times and may graduate to a permanent
                        static template. Thank you for helping improve the system!
                        {enrichedSections.length > 0 && (
                            <div style={{ marginTop: 8, opacity: 0.8 }}>
                                Enhanced sections: {enrichedSections.join(', ')}
                            </div>
                        )}
                    </div>
                }
                message="🎉 Popular Content - Template Candidate"
                showIcon
                type="success"
            />
        );
    },
);

PromotionSignalBanner.displayName = 'PromotionSignalBanner';

export default PromotionSignalBanner;
