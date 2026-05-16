
import asyncio
import argparse
import sys
import uuid
from src.core.auth import hash_password
from src.storage.db import PostgresPoolManager
from src.core.config import settings

async def create_admin(email: str, password: str, name: str = None):
    """Create an admin user in the database."""
    pool = await PostgresPoolManager.get_pool()
    
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())
    
    try:
        async with pool.acquire() as conn:
            # Check if user already exists
            existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
            if existing:
                print(f"Error: User with email {email} already exists.")
                return

            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, name, is_admin, auth_provider)
                VALUES ($1, $2, $3, $4, TRUE, 'local')
                """,
                user_id, email, password_hash, name
            )
            print(f"Successfully created admin user: {email} (ID: {user_id})")
            
    except Exception as e:
        print(f"Failed to create admin: {e}")
    finally:
        await PostgresPoolManager.close_pool()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a DevForge admin user.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", help="Admin display name")
    
    args = parser.parse_args()
    
    asyncio.run(create_admin(args.email, args.password, args.name))
