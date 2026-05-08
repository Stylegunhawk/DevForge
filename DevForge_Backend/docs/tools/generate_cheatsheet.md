# generate_cheatsheet - Dynamic Cheat Sheet Generator

**Tool Name:** `generate_cheatsheet`  
**Version:** 0.8.0  
**Phase:** 7 (Cheat Sheets)  
**Status:** ✅ Production Ready (Context-Aware)

---

## Overview

The `generate_cheatsheet` tool creates **context-aware**, skill-level appropriate programming cheatsheets. It analyzes your code to detect libraries, calculate complexity, and generates highly relevant markdown-formatted quick references with real-world examples.

**Currently Fully Supported:**
- ✅ **Python** - Only language with full templates (beginner fully implemented; intermediate/expert in development)
- ✅ **Library detection** - 14 libraries (pandas, fastapi, asyncio have dedicated templates)
- ⚠️ **Other languages** - No per-language templates exist. Requesting a non-Python language returns Python content under a relabelled header (e.g., `# Javascript Cheat Sheet - Beginner` followed by Python code). Quick-reference tables also emit Python syntax regardless of the requested language.

---

## Features

- ✅ **Context-aware**: Analyzes code to detect libraries and complexity
- ✅ **Library detection**: 14 libraries (pandas, fastapi, asyncio, etc.)
- ✅ **Complexity scoring**: Auto-suggests skill level based on code features
- ✅ **Library-specific sections**: Dedicated content for detected libraries
- ✅ Auto-detect language from code context
- ✅ Skill-level based content generation
- ✅ Markdown-formatted output with real code examples
- ✅ Quick reference tables (skill-level specific)
- ✅ Best practices and common pitfalls
- ✅ Fast response (<500ms, rule-based)

---

## Folder Structure

```
src/agents/cheatsheet/
├── agent.py                 # Main CheatsheetAgent class (context-aware pipeline)
├── context_parser.py        # Parse multi-block code from frontend
├── library_detector.py      # Detect 14 libraries with regex
├── complexity_scorer.py     # Score code complexity (10 features)
├── section_selector.py      # Smart section selection (library-first)
├── quick_reference.py       # Skill-level specific quick ref tables
└── enhanced_templates.py    # Real code examples (pandas, fastapi, asyncio)

src/tools/cheatsheet/
└── tools.py                 # Language detection helpers

Related Files:
├── src/api/routers.py       # Gateway endpoint registration
├── tests/test_cheatsheet.py # Unit tests (4 in this file; 47 across all cheatsheet-related suites)
└── manifests/devforge.json  # Tool definition (lines 240-267)
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No* | Auto-detect | Programming language name |
| `skill_level` | string | No | `"beginner"` | Target skill level |
| `code_context` | string | No | `null` | Code snippet for language detection |

*Note: Either `language` or `code_context` should be provided

### Supported Languages

**Fully Supported (Enhanced Templates):**
- `python` - Python 3.x
  - Beginner: ✅ Complete
  - Intermediate: ⚠️ In development
  - Expert: ⚠️ In development
  - Libraries: pandas, fastapi, asyncio

> [!IMPORTANT]
> Python is the **only** language with implemented templates. Any other language string (e.g., `javascript`, `rust`, `go`) is accepted but the agent silently falls back to Python content — the markdown header is relabelled (e.g., `# Rust Cheat Sheet - Beginner`) and the code-fence language tag echoes the input, but the body and quick-reference rows are Python syntax. Per-language templates and quick-reference variants are planned for future versions.

### Skill Levels

| Level | Target Audience | Content Focus |
|-------|----------------|---------------|
| `beginner` | New learners | Basics, syntax, simple examples |
| `intermediate` | Working developers | Patterns, best practices, common tasks |
| `expert` | Advanced users | Advanced features, optimization, concurrency |

---

## API Usage

> [!NOTE]
> The markdown code-fence language tag in the output (e.g., ` ```rust `) echoes the `language` value supplied in the request, but the **code inside the fence is Python** until per-language templates are added.

### Auto-Detect Language

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "code_context": "def hello():\n    print(\"Hello World\")",
      "skill_level": "beginner"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "markdown": "# Python Cheat Sheet - Beginner\n\n## Variables & Types\n...",
    "language": "python",
    "skill_level": "beginner",
    "detected_libraries": [],
    "supported_libraries": [],
    "complexity_score": 3,
    "sections": [
      {"title": "Variables & Types"},
      {"title": "Control Flow"},
      {"title": "Functions"}
    ]
  }
}
```

### Explicit Language

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "language": "javascript",
      "skill_level": "intermediate"
    }
  }'
```

### Expert Level

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "language": "rust",
      "skill_level": "expert"
    }
  }'
```

---

## Lobe Chat Usage

### Simple Request
```
"Generate a Python cheat sheet for beginners"
```

### With Code Context
```
"Create a cheat sheet for this code"
[Attach TypeScript file]
```

### Advanced Request
```
"I need an expert-level Go cheat sheet covering concurrency"
```

---

## Language Detection

The tool uses regex heuristics to detect the language. Only Python and JavaScript/TypeScript have detection branches — anything unrecognised defaults to `"python"` (no error is raised):

```python
# src/tools/cheatsheet/tools.py
def detect_language_from_code(code: str) -> str:
    code = code.strip()

    # Python
    if re.search(r'def\s+\w+\s*\(|import\s+\w+|from\s+\w+\s+import|print\(', code):
        return "python"

    # JavaScript / TypeScript
    if re.search(r'function\s+\w+\s*\(|const\s+\w+\s*=|let\s+\w+\s*=|console\.log\(', code):
        if re.search(r':\s*\w+(\[\])?\s*[=,)]|interface\s+\w+', code):
            return "typescript"
        return "javascript"

    # Default fallback
    return "python"
```

---

## Library Detection (New in v0.8.0)

The tool automatically detects 14 libraries from your code (the full set of keys in `LIBRARY_SIGNATURES`):

**Supported Libraries (14 total):** `pandas`, `numpy`, `matplotlib`, `scikit-learn`, `fastapi`, `flask`, `django`, `pydantic`, `asyncio`, `aiohttp`, `sqlalchemy`, `requests`, `httpx`, `pytest`.

Grouped by domain:
- **Data Science**: pandas, numpy, matplotlib, scikit-learn
- **Web Frameworks**: fastapi, flask, django
- **Data Validation**: pydantic
- **Async**: asyncio, aiohttp
- **Database**: sqlalchemy
- **HTTP Clients**: requests, httpx
- **Testing**: pytest

**Example:**
```python
import pandas as pd
from fastapi import FastAPI

df = pd.read_csv('data.csv')
```
→ Detects: `["pandas", "fastapi"]`  
→ Generates: Pandas-specific + FastAPI-specific sections

---

## Complexity Scoring (New in v0.8.0)

The tool analyzes code complexity to suggest appropriate skill levels:

**Features Analyzed:**
- Imports, functions, classes
- Async functions, decorators
- Comprehensions, context managers
- Type hints, lambdas, generators

**Scoring Thresholds:**
- `<10` → Beginner
- `<30` → Intermediate
- `≥30` → Expert

**Example:**
```python
# Simple code (score: 3)
def add(a, b):
    return a + b
```
→ Suggested level: **Beginner**

```python
# Complex code (score: 45)
import asyncio
import aiohttp

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
```
→ Suggested level: **Expert**

---

## Cheat Sheet Content

### Beginner Level

**Sections:**
1. Basic Syntax
2. Variables and Data Types
3. Control Flow (if/for/while)
4. Functions basics
5. Common operations
6. Simple examples

**Example (Python):**
```markdown
# Python Cheat Sheet - Beginner

## Variables
```python
name = "Alice"  # String
age = 25        # Integer
price = 19.99   # Float
is_active = True  # Boolean
```

## Control Flow
```python
# If statement
if age >= 18:
    print("Adult")
else:
    print("Minor")

# For loop
for i in range(5):
    print(i)
```
```

### Intermediate Level

**Sections:**
1. Advanced syntax
2. Data structures
3. Functions and lambdas
4. File operations
5. Error handling
6. Common patterns
7. Best practices

### Expert Level

**Sections:**
1. Advanced features
2. Performance optimization
3. Concurrency/Async
4. Memory management
5. Design patterns
6. Metaprogramming
7. Production practices

---

## Use Cases

### 1. Learning Resource

```json
{
  "language": "python",
  "skill_level": "beginner"
}
```

**Output:** Quick reference for Python learners

### 2. Quick Lookup

```json
{
  "language": "typescript",
  "skill_level": "intermediate"
}
```

**Output:** Common TypeScript patterns and syntax

### 3. Code Review Aid

```json
{
  "code_context": "package main\nimport \"fmt\"...",
  "skill_level": "expert"
}
```

**Output:** Advanced Go patterns and best practices

### 4. Onboarding Tool

```json
{
  "language": "rust",
  "skill_level": "beginner"
}
```

**Output:** Rust basics for new team members

---

## Implementation Details

### Technology Stack
- **Regex** - Language detection
- **Python** - Content generation (string concatenation; no templating engine)

### Generation Flow

```
User Request
    ↓
Language Detection (if code_context)
    ↓
Skill Level Selection
    ↓
Content Generation
    ↓
Markdown Formatting
    ↓
Cheat Sheet Output
```

### Code Location
- Agent: `src/agents/cheatsheet/agent.py`
- Templates: `src/agents/cheatsheet/enhanced_templates.py`
- Tests: `tests/test_cheatsheet.py`

---

## Output Format

### Structure

```markdown
# [Language] Cheat Sheet - [Skill Level]

## 1. Topic Name
Brief explanation
```[language]
code example
```

## 2. Next Topic
...

## Quick Reference
- Key points
- Common gotchas
- Best practices
```

---

## Examples

### Python Beginner

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "language": "python",
      "skill_level": "beginner"
    }
  }'
```

**Output:** Basic Python syntax, variables, loops, functions

### JavaScript Intermediate

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "language": "javascript",
      "skill_level": "intermediate"
    }
  }'
```

**Output:** Promises, async/await, array methods, ES6+ features

### Rust Expert

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "language": "rust",
      "skill_level": "expert"
    }
  }'
```

**Output:** Ownership, lifetimes, unsafe, concurrency patterns

---

## Error Handling

### No Language or Context

```json
{
  "skill_level": "beginner"  // Missing language/context
}
```

**Response:**
```json
{
  "success": false,
  "message": "Either 'language' or 'code_context' must be provided"
}
```

---

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Language detection | < 10ms | Regex based |
| Content generation | < 500ms | Template based |
| Markdown formatting | < 50ms | String operations |
| **Total** | **< 1s** | Typical case |

---

## Testing

### Run Tests
```bash
pytest tests/test_cheatsheet.py -v
```

### Test Coverage
- ✅ Language detection
- ✅ Skill level adaptation
- ✅ Content generation
- ✅ Markdown formatting
- ✅ Error cases

---

## Best Practices

1. **Provide Context When Possible**
   - More accurate language detection
   - Context-specific examples

2. **Choose Appropriate Skill Level**
   - Beginner: Learning fundamentals
   - Intermediate: Daily development
   - Expert: Advanced optimization

3. **Save and Reuse**
   - Cache generated cheat sheets
   - Update as language evolves

4. **Combine With Other Tools**
   - Use with `refine_prompt` for targeted sections
   - Use with `retrieve_docs` for documentation

---

## Integration Examples

### With Lobe Chat Workflow

1. User uploads Python file
2. Lobe Chat detects it's Python
3. Suggests: "Generate a cheat sheet?"
4. Tool auto-generates beginner Python reference
5. User can ask for intermediate/expert versions

### With Documentation System

1. Generate cheat sheets for all project languages
2. Store in docs/ folder
3. Update on language version changes
4. Include in onboarding materials

---

## Troubleshooting

**Issue:** Wrong language detected  
**Solution:** Explicitly specify `language` parameter

**Issue:** Content too basic/advanced  
**Solution:** Adjust `skill_level` parameter

**Issue:** Missing sections  
**Solution:** Request specific topics in custom request

---

## Related Tools

- `refine_prompt` - Optimize cheat sheet requests
- `retrieve_docs` - Search official documentation
- `generate_data` - Create sample data for examples

---

**Last Updated:** 2026-05-08  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
