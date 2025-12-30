import { Tooltip } from '@lobehub/ui';
import { Progress } from 'antd';
import { memo } from 'react';

import { getComplexityColor } from '@/features/Cheatsheet/types/cheatsheet';

interface ComplexityScoreBadgeProps {
    score?: number;
    suggestedLevel?: 'beginner' | 'intermediate' | 'expert';
    validationScore?: number;
}

/**
 * Visual widget showing code complexity score and optional validation quality
 */
const ComplexityScoreBadge = memo<ComplexityScoreBadgeProps>(({ score, suggestedLevel, validationScore }) => {
    // Defensive: Don't render if no score provided
    if (score === undefined || score === null) return null;

    // Determine level if not provided
    const level = suggestedLevel || (score < 10 ? 'beginner' : score < 30 ? 'intermediate' : 'expert');
    const colorType = getComplexityColor(score);

    return (
        <div style={{ display: 'flex', gap: 8 }}>
            <Tooltip
                placement="top"
                title={`Code Complexity: ${score}/100 (${level.charAt(0).toUpperCase() + level.slice(1)} level)`}
            >
                <div>
                    <Progress
                        percent={score}
                        size="small"
                        status={colorType}
                        strokeColor={
                            colorType === 'success' ? '#52c41a' : colorType === 'normal' ? '#1890ff' : '#722ed1'
                        }
                        type="circle"
                        width={50}
                    />
                </div>
            </Tooltip>

            {/* Validation Score (LLM Quality) */}
            {validationScore !== undefined && (
                <Tooltip title="LLM Output Quality Confidence">
                    <div>
                        <Progress
                            percent={validationScore}
                            size="small"
                            strokeColor={validationScore > 80 ? '#52c41a' : '#faad14'}
                            type="circle"
                            width={50}
                            format={(percent) => (
                                <span style={{ fontSize: 10 }}>{percent}%<br />Valid</span>
                            )}
                        />
                    </div>
                </Tooltip>
            )}
        </div>
    );
});

ComplexityScoreBadge.displayName = 'ComplexityScoreBadge';

export default ComplexityScoreBadge;
