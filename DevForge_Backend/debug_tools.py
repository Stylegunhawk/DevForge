
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.tools.cheatsheet.tools import detect_language_from_code

code = "fn main() { let x = 5; }"
print(f"Testing code: {code}")

detected = detect_language_from_code(code)
print(f"Detected: {detected}")

code2 = "import pandas as pd"
print(f"Testing code: {code2}")
print(f"Detected: {detect_language_from_code(code2)}")
