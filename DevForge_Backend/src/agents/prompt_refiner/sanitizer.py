"""Sanitizer for securing prompt context.

Redacts secrets and neutralizes potential prompt injection attempts.
"""

import re
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class Sanitizer:
    """Sanitizes text content for security."""

    # Patterns for sensitive data - comprehensive coverage
    SECRET_PATTERNS = [
        # Generic patterns (key=value, token=value, etc.)
        r"(api_key|apikey|api-key|secret|token|password|passwd|pwd|auth_token|access_token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{6,})['\"]?",
        
        # Stripe keys
        r"(sk_live_[a-zA-Z0-9]{6,})",  # Stripe secret live key
        r"(sk_test_[a-zA-Z0-9]{6,})",  # Stripe secret test key
        r"(pk_live_[a-zA-Z0-9]{6,})",  # Stripe publishable live key
        r"(pk_test_[a-zA-Z0-9]{6,})",  # Stripe publishable test key
        
        # GitHub tokens
        r"(ghp_[a-zA-Z0-9]{6,})",       # GitHub Personal Access Token
        r"(gho_[a-zA-Z0-9]{6,})",       # GitHub OAuth token
        r"(ghu_[a-zA-Z0-9]{6,})",       # GitHub User-to-server token
        r"(ghs_[a-zA-Z0-9]{6,})",       # GitHub Server-to-server token
        r"(ghr_[a-zA-Z0-9]{6,})",       # GitHub Refresh token
        
        # OpenAI / Anthropic keys
        r"(sk-[a-zA-Z0-9]{20,})",       # OpenAI API key
        r"(sk-ant-[a-zA-Z0-9\-]{30,})", # Anthropic API key
        
        # AWS keys
        r"(AKIA[0-9A-Z]{16})",          # AWS Access Key ID
        
        # Generic bearer tokens
        r"(Bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*)",  # Bearer token
        
        # Query parameter tokens
        r"([?&]token=[a-zA-Z0-9_\-\.]{6,})",  # URL query param token

        # Database connection strings with embedded credentials
        # Matches postgresql://user:pass@host, mysql://, mongodb://, redis://
        r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s]+:[^@\s]+@[^\s]+)",
    ]

    # Patterns for prompt injection - comprehensive variants
    INJECTION_PATTERNS = [
        # Ignore/disregard instructions variants
        r"(ignore\s+(all\s+)?(previous|prior|earlier)\s+(instructions|rules|prompts|commands))",
        r"(disregard\s+(all\s+)?(previous|prior|earlier)\s+(instructions|rules|prompts|commands))",
        r"(forget\s+(all\s+)?(previous|prior|earlier)\s+(instructions|rules|prompts|commands))",
        
        # Override/replace variants
        r"(override\s+(all\s+)?(previous|system|existing)\s+(instructions|rules|settings))",
        r"(replace\s+(the\s+)?(system\s+)?(prompt|instructions|rules))",
        
        # System manipulation
        r"(you\s+are\s+not\s+)",
        r"(your\s+role\s+is\s+now)",
        r"(new\s+system\s+prompt)",
        r"(ignore\s+all\s+rules)",
        r"(bypass\s+(security|restrictions|filters))",
        
        # Developer mode / jailbreak attempts  
        r"(enable\s+developer\s+mode)",
        r"(DAN\s+mode)",  # "Do Anything Now" jailbreak
    ]

    def sanitize(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Sanitize text by redacting secrets and neutralizing injections.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (sanitized_text, sanitization_log)
            sanitization_log contains metadata only, never actual secret values
        """
        if not text:
            return "", []
            
        sanitization_log = []
        sanitized = text
        
        # Redact secrets
        sanitized, secret_log = self._redact_secrets(sanitized)
        sanitization_log.extend(secret_log)
        
        # Neutralize injections
        sanitized, injection_log = self._neutralize_injection(sanitized)
        sanitization_log.extend(injection_log)
        
        return sanitized, sanitization_log

    def _redact_secrets(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Redact detected secrets.
        
        Returns:
            Tuple of (sanitized_text, log_entries)
        """
        log = []
        sanitized = text
        
        for pattern in self.SECRET_PATTERNS:
            matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
            for match in matches:
                # Log metadata only (type, location) - NEVER the actual secret
                log.append({
                    "type": "secret_redacted",
                    "pattern": "sensitive_credential",
                    "position": match.start(),
                    "length": len(match.group(0))
                })
            # Replace entire match with [REDACTED] (not partial replacement with \1)
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        
        return sanitized, log

    def _neutralize_injection(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Neutralize prompt injection attempts.
        
        Returns:
            Tuple of (sanitized_text, log_entries)
        """
        log = []
        sanitized = text
        
        for pattern in self.INJECTION_PATTERNS:
            matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
            for match in matches:
                log.append({
                    "type": "injection_blocked",
                    "pattern": match.group(0)[:30],  # First 30 chars only
                    "position": match.start()
                })
            sanitized = re.sub(pattern, r"[POTENTIAL INJECTION BLOCKED]", sanitized, flags=re.IGNORECASE)
        
        return sanitized, log
    
    def summarize_files(self, files: List[str]) -> Tuple[str, List[Dict[str, Any]]]:
        """Create a safe summary of file contents.
        
        Truncates large files and sanitizes content.
        
        Returns:
            Tuple of (summary, sanitization_log)
        """
        summary = []
        all_logs = []
        
        for i, content in enumerate(files):
            sanitized, log = self.sanitize(content)
            all_logs.extend(log)
            
            # Truncate if too long (simple heuristic for now)
            if len(sanitized) > 2000:
                sanitized = sanitized[:2000] + "\n...[TRUNCATED]"
            summary.append(f"--- File {i+1} ---\n{sanitized}")
        
        return "\n\n".join(summary), all_logs
