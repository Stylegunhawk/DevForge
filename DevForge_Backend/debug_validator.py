
import sys
import os
import re

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.agents.cheatsheet.validators import CheatsheetValidator

validator = CheatsheetValidator()
code = "fn main() { let x = 5; }"

print(f"Testing code: {code}")

has_syntax = validator._has_rust_syntax(code)
print(f"Has Rust Syntax: {has_syntax}")

# Test individual patterns
rust_patterns = [
    r'\bfn\s+\w+',          # Function declarations
    r'\bimpl\s+\w+',        # Implementations
    r'\bstruct\s+\w+',      # Struct definitions
    r'\benum\s+\w+',        # Enum definitions
    r'\bpub\s+',            # Public visibility
    r'\blet\s+mut\s+',      # Mutable variables
    r'\buse\s+\w+',         # Use statements
    r'->',                   # Return type syntax
    r'\bimpl\b',            # Trait implementations
    r'println!',            # Macros
    r'\blet\s+\w+',         # Variable declaration
    r'\bmatch\s+',          # Match expressions
    r'::',                  # Path separator
    r'&[a-zA-Z_]',          # References
    r'\bString\b',          # String type
    r'\bVec\b',             # Vec type
]

for p in rust_patterns:
    match = re.search(p, code)
    if match:
        print(f"Match pattern '{p}': {match}")
