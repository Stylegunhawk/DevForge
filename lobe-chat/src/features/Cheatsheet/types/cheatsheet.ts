/**
 * TypeScript type definitions for the Cheatsheet feature
 * Matches backend API response schema from generate_cheatsheet tool (v0.9.0)
 */

/**
 * Section information in the generated cheatsheet
 */
export interface CheatsheetSection {
    /** Section title (e.g., "Pandas DataFrames", "FastAPI Routes") */
    title: string;
}

/**
 * Enrichment metadata returned when LLM enhancement is used (Tier 2)
 */
export interface EnrichmentMetadata {
    /** Whether LLM enrichment was enabled for this request */
    enabled: boolean;

    /** 
     * Reason code for triggering enrichment
     * - 'fast_evolving_lib': Library changes frequently (e.g., langchain)
     * - 'user_needs_latest': User explicitly requested latest syntax
     * - 'debugging_context': Code contains error/debugging keywords
     * - 'complex_usage': Advanced usage patterns detected
     */
    reason?: string;

    /** Libraries that were targeted for enrichment */
    target_libraries?: string[];

    /** Section titles that were enhanced with LLM-generated content */
    enriched_sections?: string[];

    /** 
     * Promotion signal: true if this content has been enriched >3 times
     * Indicates it may become a permanent static template (Tier 3)
     */
    promotable?: boolean;
}

/**
 * Complete API response from generate_cheatsheet tool
 */
export interface CheatsheetResponse {
    /** Programming language detected or specified */
    language: string;

    /** User's skill level: 'beginner', 'intermediate', or 'expert' */
    skill_level: 'beginner' | 'intermediate' | 'expert';

    /** 
     * Libraries detected in the code context
     * Examples: ['pandas', 'fastapi', 'langchain', 'react']
     */
    detected_libraries?: string[];

    /** 
     * Subset of detected_libraries that have full static templates
     * Others may have partial support or require enrichment
     */
    supported_libraries?: string[];

    /** 
     * Code complexity score (0-100)
     * - 0-9: Beginner
     * - 10-29: Intermediate
     * - 30+: Expert
     */
    complexity_score?: number;

    /** 
     * Generation method
     * - 'template': Fast rule-based generation (<200ms, zero cost)
     * - 'enriched': LLM-enhanced content (<5s, API cost)
     */
    method?: 'template' | 'enriched';

    /** List of sections included in the cheatsheet */
    sections?: CheatsheetSection[];

    /** Generated markdown cheatsheet content */
    markdown: string;

    /** Enrichment metadata (only present if method === 'enriched') */
    enrichment?: EnrichmentMetadata;

    // --- NEW: Hybrid Backend Fields (Phase E) ---
    /** 
     * How the content was generated
     * - 'template': Static template (fast)
     * - 'llm_primary': Direct LLM generation
     * - 'llm_with_search': LLM + Web Search
     */
    generation_method?: 'template' | 'llm_primary' | 'llm_with_search';

    /** True if LLM was involved in generation */
    llm_generated?: boolean;

    /** Why the specific routing path was chosen */
    routing_reason?: string;

    /** Whether web search was performed */
    web_search_used?: boolean;

    /** List of URLs used as sources/context */
    sources?: string[];

    /** Internal validation score (0-100) */
    validation_score?: number;

    /** Detailed quality metrics */
    quality_indicators?: {
        code_blocks: number;
        headings: number;
        syntax_valid: boolean;
        has_table: boolean;
    };

    /** Number of validation retries needed */
    retry_count?: number;

    /** Reason for falling back to template (if applicable) */
    fallback_reason?: string | null;
}

/**
 * API gateway response wrapper
 */
export interface CheatsheetAPIResponse {
    success: boolean;
    data: CheatsheetResponse;
    error?: string;
}

/**
 * Language maturity level for UI grouping
 */
export interface SupportedLanguage {
    label: string;
    value: string;
    /** 
     * Maturity level
     * - 'full': Comprehensive templates available
     * - 'experimental': Basic support, may have gaps
     * - 'coming_soon': Planned but not yet supported
     */
    maturity: 'full' | 'experimental' | 'coming_soon';
    disabled?: boolean;
}

/**
 * Type guard to check if response has enrichment metadata
 */
export function hasEnrichment(
    response: CheatsheetResponse,
): response is CheatsheetResponse & { enrichment: EnrichmentMetadata } {
    return response.method === 'enriched' && !!response.enrichment;
}

/**
 * Type guard to check if enrichment is promotable
 */
export function isPromotable(enrichment?: EnrichmentMetadata): boolean {
    return enrichment?.enabled === true && enrichment?.promotable === true;
}

/**
 * Helper to get user-friendly reason message
 */
export function getEnrichmentReasonMessage(reason?: string): string {
    const messages: Record<string, string> = {
        fast_evolving_lib: '🆕 Using latest syntax for fast-evolving libraries',
        user_needs_latest: '⚡ Generated with latest API updates',
        debugging_context: '🐛 Enhanced with debugging tips',
        complex_usage: '🎯 Advanced usage patterns detected',
    };

    return messages[reason || ''] || '🤖 AI-enhanced content';
}

/**
 * Helper to determine complexity color
 */
export function getComplexityColor(score: number): 'success' | 'normal' | 'exception' {
    if (score < 10) return 'success'; // Green (Beginner)
    if (score < 30) return 'normal'; // Blue (Intermediate)
    return 'exception'; // Purple (Expert)
}
