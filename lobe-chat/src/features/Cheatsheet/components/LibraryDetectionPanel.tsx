import { Alert, Tag } from 'antd';
import { memo } from 'react';
import { Flexbox } from 'react-layout-kit';

interface LibraryDetectionPanelProps {
    detectedLibraries?: string[];
    supportedLibraries?: string[];
    webSearchUsed?: boolean;
    sources?: string[];
}

/**
 * Panel showing detected libraries and web sources (if applicable)
 */
const LibraryDetectionPanel = memo<LibraryDetectionPanelProps>(
    ({ detectedLibraries = [], supportedLibraries = [], webSearchUsed = false, sources = [] }) => {
        // Defensive: Don't render if no libraries detected
        if (!detectedLibraries || detectedLibraries.length === 0) {
            return null;
        }

        // Helper to check if library is fully supported
        const isSupported = (lib: string) => supportedLibraries.includes(lib);

        return (
            <>
                <Alert
                    closable
                    message={
                        <Flexbox gap={8}>
                            <div style={{ fontWeight: 'bold' }}>
                                📚 Detected Libraries ({detectedLibraries.length})
                            </div>
                            <Flexbox gap={4} horizontal style={{ flexWrap: 'wrap' }}>
                                {detectedLibraries.map((lib) => (
                                    <Tag
                                        color={isSupported(lib) ? 'success' : 'warning'}
                                        icon={isSupported(lib) ? '✅' : '⚠️'}
                                        key={lib}
                                    >
                                        {lib}
                                        {isSupported(lib) ? ' (Full Support)' : ' (Basic)'}
                                    </Tag>
                                ))}
                            </Flexbox>
                        </Flexbox>
                    }
                />

                {/* Web Search Sources - Only show if search was actually used */}
                {webSearchUsed && sources && sources.length > 0 && (
                    <Alert
                        message={
                            <Flexbox gap={8}>
                                <div style={{ fontWeight: 'bold' }}>
                                    🌐 Web Sources Used
                                </div>
                                <ul style={{ listStyleType: 'disc', margin: 0, paddingLeft: 20 }}>
                                    {sources.slice(0, 3).map((url, i) => (
                                        <li key={i}>
                                            <a href={url} target="_blank" rel="noopener noreferrer">
                                                {/* Simple domain extraction logic */}
                                                {(() => {
                                                    try {
                                                        const { hostname } = new URL(url);
                                                        return hostname.replace('www.', '');
                                                    } catch {
                                                        return url; // Fallback
                                                    }
                                                })()}
                                            </a>
                                        </li>
                                    ))}
                                    {sources.length > 3 && (
                                        <li><i>...and {sources.length - 3} more</i></li>
                                    )}
                                </ul>
                            </Flexbox>
                        }
                        type="info"
                        style={{ marginTop: 8 }}
                    />
                )}
            </>
        );
    },
);

LibraryDetectionPanel.displayName = 'LibraryDetectionPanel';

export default LibraryDetectionPanel;
