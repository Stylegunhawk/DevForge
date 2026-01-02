
import sys
import os
import asyncio

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.agents.cheatsheet.agent import cheatsheet_agent
from src.agents.cheatsheet.config import config
from src.agents.cheatsheet.context_parser import parse_code_context

print(f"Config ENABLE_LLM_FALLBACK: {config.ENABLE_LLM_FALLBACK}")
print(f"Agent LLM Generator: {cheatsheet_agent.llm_generator}")

if cheatsheet_agent.llm_generator is None:
    print("❌ LLM Generator is NONE")
else:
    print("✅ LLM Generator is Initialized")
    
# Test primary language determination
code = "fn main() { let x = 5; }"
parsed = parse_code_context(code)
primary = cheatsheet_agent._determine_primary_language(parsed)
print(f"Rust code primary language: {primary}")
