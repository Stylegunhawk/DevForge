import os
import asyncio

# Setup API-Only minimal environment
os.environ["ENVIRONMENT"] = "production"
os.environ["CORS_ORIGINS"] = "http://devforge.onrender.com"
os.environ["PORT"] = "8000"
os.environ["OLLAMA_HOST"] = "https://api.ollama.com"
os.environ["OLLAMA_API_KEY"] = "fake-key"
os.environ["DEFAULT_MODEL"] = "gemma-1b"
os.environ["FILE_BASE_URL"] = "http://devforge.onrender.com/uploads"
# Explicitly ensuring databases are unset
if "POSTGRES_URL" in os.environ: del os.environ["POSTGRES_URL"]
if "REDIS_URL" in os.environ: del os.environ["REDIS_URL"]

# Test Config Initialization
from src.core.config import Settings
try:
    s = Settings()
    print("PASS: Settings initialized without DBs.")
except Exception as e:
    print(f"FAIL: Settings threw an exception: {e}")
    exit(1)

# Test Healthcheck Execution
from src.main import health_check

async def test_health():
    try:
        res = await health_check()
        print(f"PASS: Healthcheck output: {res}")
        if res["status"] == "healthy" and res["services"]["redis"] == "disabled" and res["services"]["postgres"] == "disabled":
            print("PASS: Healthcheck correctly reports DBs as disabled and app as healthy.")
        else:
            print("FAIL: Healthcheck output abnormal.")
    except Exception as e:
        print(f"FAIL: Healthcheck threw an exception: {e}")

asyncio.run(test_health())
