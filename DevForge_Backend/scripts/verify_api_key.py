import requests
import json
import time
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings

API_KEY = "df_uIphiovY4S8FrXBbGenpK9t5P2le9pmO4HzSWAIvdi8"
BASE_URL = settings.GATEWAY_URL or "http://localhost:8001"

def test_gateway_auth():
    print(f"\nTesting /api/gateway with valid key...")
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "name": "refine_prompt",
        "arguments": {"prompt": "Check if API key auth works"}
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/gateway", headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_missing_key():
    print(f"\nTesting /api/gateway with missing key...")
    payload = {"name": "refine_prompt", "arguments": {"prompt": "test"}}
    response = requests.post(f"{BASE_URL}/api/gateway", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 401

def test_invalid_key():
    print(f"\nTesting /api/gateway with invalid key...")
    headers = {"X-API-Key": "df_invalid_key"}
    payload = {"name": "refine_prompt", "arguments": {"prompt": "test"}}
    response = requests.post(f"{BASE_URL}/api/gateway", headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 401

if __name__ == "__main__":
    s1 = test_gateway_auth()
    s2 = test_missing_key()
    s3 = test_invalid_key()
    
    if all([s1, s2, s3]):
        print("\n" + "="*30)
        print("ALL AUTH TESTS PASSED!")
        print("="*30)
    else:
        print("\n" + "!"*30)
        print("SOME TESTS FAILED!")
        print("!"*30)
