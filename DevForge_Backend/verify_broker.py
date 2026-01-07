import sys
import os
from unittest.mock import MagicMock

# Mock fastapi modules to avoid needing full running environment
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.staticfiles"] = MagicMock()
sys.modules["fastapi.middleware.cors"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()

# Import main (which now imports celery_app)
try:
    # We need to mock settings before importing main, or let it load
    # It will load from .env or defaults.
    import src.main
    
    # Check the Celery app in rag_tasks or celery_app module
    from src.workers.celery_app import app
    
    print(f"Broker: {app.conf.broker_url}")
    print(f"Backend: {app.conf.result_backend}")
    
    if "redis" in app.conf.broker_url:
        print("SUCCESS: Broker configured to Redis")
    else:
        print("FAILURE: Broker is NOT Redis")

except Exception as e:
    print(f"Verification failed: {e}")
