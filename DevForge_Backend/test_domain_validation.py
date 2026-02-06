import sys
import os
import asyncio

# Add src to path
sys.path.append(os.getcwd())

from src.core.schemas import DataGenArgs
from pydantic import ValidationError

def test_domain_validation():
    print("Testing Domain Validation...")
    
    # Test valid domains
    valid_domains = ["ecommerce", "saas", "iot_devices"]
    for d in valid_domains:
        try:
            args = DataGenArgs(rows=10, domain=d)
            print(f"PASS: '{d}' is valid.")
        except ValidationError as e:
            print(f"FAIL: '{d}' failed validation: {e}")
            sys.exit(1)

    # Test invalid domain
    invalid_domain = "finance"
    try:
        args = DataGenArgs(rows=10, domain=invalid_domain)
        print(f"FAIL: '{invalid_domain}' should have failed.")
        sys.exit(1)
    except ValidationError:
        print(f"PASS: '{invalid_domain}' was rejected as expected.")

    print("Domain Validation Verified.")

if __name__ == "__main__":
    test_domain_validation()
