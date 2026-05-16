
import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.core.model_router import model_router
from src.agents.prompt_refiner.agent import prompt_refiner_agent
from src.storage.db import PostgresPoolManager

async def verify_tracking():
    print("🚀 Starting Phase 2 Token Tracking Verification...")
    
    test_tenant = f"test-tenant-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    test_integration = "verification-script"
    
    print(f"1. Triggering Prompt Refiner with tenant: {test_tenant}")
    
    # We call the agent directly (which now has our instrumented enhancer)
    result = await prompt_refiner_agent.refine(
        prompt="Explain quantum computing like I'm five",
        domain="general",
        tenant_id=test_tenant,
        integration_name=test_integration
    )
    
    if result.get("success"):
        print("✅ Agent invocation successful.")
    else:
        print(f"❌ Agent invocation failed: {result.get('error')}")
        return

    print("2. Waiting for Celery task to persist usage data (5s)...")
    await asyncio.sleep(5)
    
    print("3. Checking llm_usage table for record...")
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM llm_usage WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 1",
            test_tenant
        )
        
        if row:
            print("✅ Usage record found in database!")
            print(f"   Model: {row['model_name']}")
            print(f"   Task: {row['task_type']}")
            print(f"   Tokens: {row['prompt_tokens']} prompt, {row['completion_tokens']} completion, {row['total_tokens']} total")
            print(f"   Estimated Cost: ${row['cost_usd']:.6f}")
            
            if row['prompt_tokens'] > 0 and row['total_tokens'] > 0:
                print("✅ Token counts are positive and look valid.")
            else:
                print("⚠️ Token counts are zero - check ModelRouter._extract_usage fallback.")
        else:
            print("❌ No usage record found for test tenant. Check Celery logs.")

    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(verify_tracking())
