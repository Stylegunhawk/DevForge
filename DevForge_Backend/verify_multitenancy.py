
import asyncio
import time
from src.agents.rag.agent import get_rag_agent, RAGAgent

async def test_multi_tenancy_and_caching():
    print(f"\n{'='*50}\n🔎 TESTING RAG MULTI-TENANCY & PERFORMANCE\n{'='*50}")

    # =========================================================================
    # 1. TEST ISOLATION (User A vs User B)
    # =========================================================================
    user_a = "user_A"
    user_b = "user_B"
    
    # Get agents (simulating factory usage)
    agent_a = get_rag_agent(tenant_id=user_a)
    agent_b = get_rag_agent(tenant_id=user_b)
    
    print(f"\n[1] Testing Isolation:")
    print(f"    Agent A Collection: {agent_a.collection_name}")
    print(f"    Agent B Collection: {agent_b.collection_name}")
    
    assert agent_a.collection_name == f"user_{user_a}"
    assert agent_b.collection_name == f"user_{user_b}"
    assert agent_a != agent_b, "❌ Agents should be different instances"
    print("    ✅ Factory created scoped agents correctly")

    # =========================================================================
    # 2. TEST GRAPH CACHING PERFORMANCE
    # =========================================================================
    print(f"\n[2] Testing Graph Performance:")
    
    # Force rebuild (delete cache)
    import redis.asyncio as redis
    from src.core.config import settings
    r = redis.from_url(settings.REDIS_URL)
    await r.delete(f"rag_graph:user_{user_a}")
    
    print("    Initializing Graph (Cold Start)...")
    t0 = time.time()
    await agent_a.init_graph()
    t1 = time.time()
    cold_start_time = t1 - t0
    print(f"    ⏱️ Cold Start Time: {cold_start_time:.4f}s")
    
    print("    Initializing Graph (Warm Start / Cache Hit)...")
    # Reset instance graph to force load from Redis
    agent_a._code_graph = None 
    t2 = time.time()
    await agent_a.init_graph()
    t3 = time.time()
    warm_start_time = t3 - t2
    print(f"    ⏱️ Warm Start Time: {warm_start_time:.4f}s")
    
    if warm_start_time < cold_start_time * 0.5: # Expect at least 2x speedup (usually 100x)
         print(f"    ✅ CACHE HIT CONFIRMED! ({cold_start_time/warm_start_time:.1f}x faster)")
    else:
         print(f"    ⚠️ Cache might have missed or overhead is high.")

    await r.close()

if __name__ == "__main__":
    asyncio.run(test_multi_tenancy_and_caching())
