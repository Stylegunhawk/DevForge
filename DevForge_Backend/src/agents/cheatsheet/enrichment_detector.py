"""Determine when sections need LLM enrichment."""

from typing import List, Dict, Optional
import logging
from .config import config

logger = logging.getLogger(__name__)

def should_enrich_sections(
    detected_libraries: List[str],
    code_context: str = "",
    conversation_history: Optional[str] = None,
    supported_libraries: List[str] = []
) -> Dict:
    """
    Decide if sections need LLM enrichment.
    
    STRICT RULES:
    1. Feature flag must be enabled.
    2. Must detect a 'fast-evolving' library OR user asks for 'latest'.
    3. Library must NOT be in FULLY_TEMPLATED_LIBS (unless explicit override).
    4. Must have strong context signals (errors, complex usage, explicit request).
    
    Args:
        detected_libraries: List of libraries found in code.
        code_context: The user's code snippet.
        conversation_history: Recent chat messages (optional).
        supported_libraries: List of libraries we have templates for (optional reference).

    Returns:
        Dict with keys:
            'enrich' (bool): Whether to trigger enrichment.
            'reason' (str): Why enrichment was triggered or skipped.
            'target_libraries' (List[str]): Libraries to target for enrichment.
            'confidence' (float): Confidence score of the decision (0.0 - 1.0).
    """
    
    # Gate 1: Feature flag
    if not config.ENABLED:
        logger.debug("Enrichment disabled: Feature flag is OFF")
        return {'enrich': False, 'reason': 'feature_disabled', 'target_libraries': [], 'confidence': 0.0}
    
    # Gate 2: Check for fast-evolving libraries
    # Normalizing inputs
    detected_lower = [lib.lower() for lib in detected_libraries]
    
    fast_evolving_detected = [
        lib for lib in detected_lower
        if any(fast in lib for fast in config.FAST_EVOLVING_LIBS)
    ]
    
    # Helper: Check if user explicitly asks for "latest" or "new"
    signals = _analyze_context(code_context, conversation_history)
    
    # If no fast libraries AND user isn't strictly asking for "latest", skip.
    if not fast_evolving_detected and not signals['asks_latest']:
        logger.debug(f"Enrichment skipped: No fast-evolving libs {detected_libraries} and no 'latest' request")
        return {'enrich': False, 'reason': 'stable_libraries', 'target_libraries': [], 'confidence': 0.0}
    
    # Gate 3: Filter out libraries that are already fully templated
    # (Unless user specifically asks for latest versions of them)
    target_libs = []
    
    if fast_evolving_detected:
        # Standard flow: Enrich fast libraries that lack full templates
        target_libs = [
            lib for lib in fast_evolving_detected
            if lib not in config.FULLY_TEMPLATED_LIBS
        ]
        
    # Edge case: Enriched stable libraries if requested
    if signals['asks_latest']:
        # If user asks for "latest pandas", we might want to enrich even if stable.
        # For now, let's trust the detected fast check primarily, but allow 'asks_latest' to
        # boost confidence.
        # If we have fast_evolving_detected, we keep them.
        pass

    if not target_libs and not signals['asks_latest']:
        logger.info(f"Enrichment skipped: {fast_evolving_detected} are fully templated or covered.")
        return {'enrich': False, 'reason': 'templates_sufficient', 'target_libraries': [], 'confidence': 0.0}
    
    # If we have targets but no signals, we might still want to enrich if it's a REALLY new library
    # that we know has no templates at all.
    # But usually we rely on _analyze_context.
    
    # Gate 4: Context Signal Strength
    if not signals['should_enrich']:
        # If the code is trivial "import langchain", maybe don't burn tokens?
        # But if it's "fast-evolving", almost any usage might justify a tip.
        # Let's enforce that 'should_enrich' must be true (which requires errors, latest request, or complexity).
        logger.debug(f"Enrichment skipped: Context signals weak ({signals})")
        return {'enrich': False, 'reason': 'weak_signals', 'target_libraries': [], 'confidence': signals['confidence']}
    
    # Approval
    # If we have no target libs yet (e.g. asking for "latest" but no fast lib detected),
    # we might need to rely on what was passed in detected_libraries, essentially treating them as targets.
    if not target_libs and signals['asks_latest'] and detected_lower:
        target_libs = detected_lower
        
    reason = signals['reason']
    logger.info(f"Enrichment approved for {target_libs}: {reason}")
    
    return {
        'enrich': True,
        'reason': reason,
        'target_libraries': target_libs,
        'confidence': signals['confidence']
    }


def _analyze_context(code: str, conversation: Optional[str]) -> Dict:
    """Analyze code and conversation for enrichment signals."""
    
    signals = {
        'has_errors': False,
        'asks_latest': False,
        'complex_usage': False,
        'should_enrich': False,
        'reason': '',
        'confidence': 0.0
    }
    
    code = code.lower() if code else ""
    conversation = conversation.lower() if conversation else ""
    
    # Signal 1: Error/debugging keywords
    # Often users paste stack traces or ask "why is this failing"
    error_keywords = ['error', 'traceback', 'exception', 'failed', 'bug', 'debug', 'fix', 'issue']
    if any(kw in code for kw in error_keywords) or any(kw in conversation for kw in error_keywords):
        signals['has_errors'] = True
        signals['confidence'] += 0.4
    
    # Signal 2: User asks for latest/current
    latest_keywords = ['latest', 'current', 'new version', 'updated', 'v0.', 'recent', 'modern', '2024', '2025']
    if any(kw in conversation for kw in latest_keywords):
        signals['asks_latest'] = True
        signals['confidence'] += 0.6  # Strong signal
    
    # Signal 3: Complex API usage
    # Indicators that the user is doing something non-trivial
    complexity_indicators = ['@', 'async ', 'yield ', 'class ', 'metaclass', 'agent', 'graph', 'chain', 'tool', 'pipeline']
    if sum(ind in code for ind in complexity_indicators) >= 2:
        signals['complex_usage'] = True
        signals['confidence'] += 0.3
        
    # Decision Logic
    # 1. User asks for latest -> Always enrich
    if signals['asks_latest']:
        signals['should_enrich'] = True
        signals['reason'] = 'user_needs_latest'
        
    # 2. Errors + Fast Library -> High value to enrich with debugging tips
    elif signals['has_errors']:
        signals['should_enrich'] = True
        signals['reason'] = 'debugging_context'
        
    # 3. Complex usage of fast library -> Likely needs updated API syntax
    elif signals['complex_usage']:
        signals['should_enrich'] = True
        signals['reason'] = 'complex_usage'
        
    return signals
