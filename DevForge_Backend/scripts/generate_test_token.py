import os
import sys
from datetime import datetime, timedelta, timezone
import jwt

# Add the project root to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Use the secret from .env.docker as a fallback for local testing
JWT_SECRET = os.environ.get("JWT_SECRET", "C6P5W7gPZbjwCEH0nQ9KlqUPrAKH7C8FcuM3SsMokj0=")
ALGORITHM = "HS256"

def create_test_token(tenant_id: str):
    """
    Generate a developer JWT token for testing RAG endpoints.
    Matches the schema in src/core/auth.py.
    """
    # 7 day expiration for convenience in testing
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    original_issued_at = datetime.now(timezone.utc)
    
    to_encode = {
        "tenant_id": tenant_id, 
        "exp": expire,
        "original_issued_at": original_issued_at.isoformat()
    }
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

if __name__ == "__main__":
    # Default to the tenant_id seen in the user's request logs
    tenant = sys.argv[1] if len(sys.argv) > 1 else "6989d05d6aef175968c3cae5"
    
    token = create_test_token(tenant)
    
    print("\n" + "="*60)
    print("DevForge RAG Testing Token Generator")
    print("="*60)
    print(f"Tenant ID: {tenant}")
    print(f"\nJWT Token:\n{token}")
    print("\n" + "="*60)
    print("Example API Usage:")
    print("="*60)
    print(f'curl -X GET "http://localhost:8001/api/v1/rag/files" \\')
    print(f'     -H "Authorization: Bearer {token}"')
    print("\n" + "="*60 + "\n")
