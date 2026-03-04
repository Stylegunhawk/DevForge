"""CLI script for bootstrapping API keys.

Usage: 
    python scripts/generate_api_key.py --name "Admin Key" --integration admin-cli
"""

import asyncio
import argparse
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.api_key_store import api_key_store
from src.storage.db import PostgresPoolManager

async def main():
    parser = argparse.ArgumentParser(description="Generate a new API key for DevForge.")
    parser.add_argument("--name", required=True, help="Friendly name for the key")
    parser.add_argument("--integration", required=True, help="Integration name (e.g., cursor-ide, chat-ui)")
    parser.add_argument("--tenant", default="default", help="Tenant ID (default: default)")
    parser.add_argument("--tier", default="free", choices=["free", "pro", "enterprise"], help="Usage tier")
    parser.add_argument("--scopes", nargs="*", default=[], help="Allowed tool scopes")

    args = parser.parse_args()

    try:
        raw_key = await api_key_store.create_key(
            name=args.name,
            tenant_id=args.tenant,
            integration_name=args.integration,
            tier=args.tier,
            scopes=args.scopes
        )
        
        print("\n" + "="*50)
        print("API KEY GENERATED SUCCESSFULLY")
        print("="*50)
        print(f"Name:        {args.name}")
        print(f"Integration: {args.integration}")
        print(f"Tenant:      {args.tenant}")
        print(f"Tier:        {args.tier}")
        print(f"Scopes:      {args.scopes}")
        print("-" * 50)
        print(f"RAW KEY:     {raw_key}")
        print("-" * 50)
        print("CRITICAL: Copy this key now! It will never be shown again.")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"ERROR: Failed to generate API key: {e}")
    finally:
        await PostgresPoolManager.close_pool()

if __name__ == "__main__":
    asyncio.run(main())
