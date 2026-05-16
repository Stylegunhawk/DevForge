"""API key expiry calculation utilities."""

from datetime import datetime, timezone, timedelta
from typing import Optional

EXPIRY_DURATIONS = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
}

def calculate_expiry(duration: Optional[str]) -> Optional[datetime]:
    """Calculate expiry datetime from duration string.
    
    Args:
        duration: One of "30d", "90d", "180d", or None for no expiry
        
    Returns:
        Datetime in UTC or None if no expiry
        
    Raises:
        ValueError: If duration is not one of the allowed values
    """
    if not duration:
        return None
    
    days = EXPIRY_DURATIONS.get(duration)
    if not days:
        raise ValueError(
            f"Invalid duration: {duration}. "
            f"Must be one of: 30d, 90d, 180d"
        )
    
    return datetime.now(timezone.utc) + timedelta(days=days)

def validate_expiry_duration(duration: Optional[str]) -> bool:
    """Validate expiry duration string.
    
    Args:
        duration: Duration string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not duration:
        return True  # None is valid (no expiry)
    
    return duration in EXPIRY_DURATIONS

def days_remaining(expires_at: Optional[datetime]) -> Optional[int]:
    """Calculate days remaining until expiry.
    
    Args:
        expires_at: Expiry datetime or None
        
    Returns:
        Days remaining (0 if expired) or None if no expiry
    """
    if not expires_at:
        return None
    
    # Ensure expires_at is timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    delta = expires_at - datetime.now(timezone.utc)
    return max(0, delta.days)

def is_expired(expires_at: Optional[datetime]) -> bool:
    """Check if a key has expired.
    
    Args:
        expires_at: Expiry datetime or None
        
    Returns:
        True if expired, False otherwise
    """
    if not expires_at:
        return False
    
    # Ensure expires_at is timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    return datetime.now(timezone.utc) > expires_at
