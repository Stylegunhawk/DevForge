"""Input sanitization utilities for secure logging.

Removes sensitive data from arguments before logging and truncates
to prevent storage of large payloads.
"""

import json
from typing import Dict, Any


def sanitize_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive data from arguments before logging.
    
    Args:
        args: Dictionary of arguments to sanitize
        
    Returns:
        Sanitized dictionary with sensitive values replaced
    """
    if not isinstance(args, dict):
        return args
    
    sensitive_keys = {'token', 'secret', 'key', 'auth', 'password'}
    sanitized = {}
    
    for key, value in args.items():
        # Check for sensitive field names
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = '[REDACTED]'
        # Special handling for nested context objects
        elif key == 'context' and isinstance(value, dict):
            sanitized_context = {}
            for ctx_key, ctx_value in value.items():
                if ctx_key == 'github_token' or any(sensitive in ctx_key.lower() for sensitive in sensitive_keys):
                    sanitized_context[ctx_key] = '[REDACTED]'
                else:
                    sanitized_context[ctx_key] = ctx_value
            sanitized[key] = sanitized_context
        else:
            sanitized[key] = value
    
    return sanitized


def truncate_input(args: Dict[str, Any], max_chars: int = 500) -> str:
    """Convert args to truncated string for logging.
    
    Args:
        args: Arguments dictionary to convert
        max_chars: Maximum character limit for truncation
        
    Returns:
        Truncated string representation of sanitized arguments
    """
    sanitized = sanitize_arguments(args)
    input_str = json.dumps(sanitized, default=str, separators=(',', ':'))
    
    if len(input_str) <= max_chars:
        return input_str
    
    # Truncate and add ellipsis
    return input_str[:max_chars] + '...'


def strip_sensitive_fields(args: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for sanitize_arguments for backward compatibility.
    
    Args:
        args: Dictionary to strip sensitive fields from
        
    Returns:
        Sanitized dictionary
    """
    return sanitize_arguments(args)
