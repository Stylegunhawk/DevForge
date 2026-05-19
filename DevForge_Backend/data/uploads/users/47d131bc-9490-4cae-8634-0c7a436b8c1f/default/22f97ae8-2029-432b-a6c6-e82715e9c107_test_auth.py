import hashlib
import re

def validate_token(token: str) -> bool:
    """Check if the token format is valid."""
    pattern = r'^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$'
    return bool(re.match(pattern, token))

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username: str, token: str, password: str) -> dict:
    """Authenticate a user by validating token and hashing password."""
    if not validate_token(token):
        return {"success": False, "error": "invalid_token"}
    hashed = hash_password(password)
    return {"success": True, "user": username, "hash": hashed}

def create_session(username: str, token: str) -> dict:
    """Create a session after authentication."""
    if not validate_token(token):
        return {"session": None, "error": "invalid_token"}
    return {"session": f"sess_{username}_{token[:8]}", "active": True}
