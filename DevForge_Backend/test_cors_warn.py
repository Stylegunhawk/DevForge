import os
from src.core.config import Settings

# Fake the environment for this test
os.environ["ENVIRONMENT"] = "production"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["PORT"] = "8000"
os.environ["OLLAMA_HOST"] = "http://localhost:11434"
os.environ["DEFAULT_MODEL"] = "gemma-1b"
os.environ["FILE_BASE_URL"] = "http://localhost/uploads"
os.environ["POSTGRES_URL"] = "postgresql://a:b@c/d"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    s = Settings()
    if len(w) > 0 and "localhost" in str(w[-1].message):
        print("PASS: Warning correctly issued")
    else:
        print("FAIL: No warning issued")
