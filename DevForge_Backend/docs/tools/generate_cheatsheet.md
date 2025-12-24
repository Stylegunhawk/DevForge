# generate_cheatsheet - Dynamic Cheat Sheet Generator

**Tool Name:** `generate_cheatsheet`  
**Version:** 0.8.0  
**Phase:** 13 (Cheat Sheets)  
**Status:** ✅ Production Ready (Context-Aware)

---

## Overview

The `generate_cheatsheet` tool creates **context-aware**, skill-level appropriate programming cheatsheets. It analyzes your code to detect libraries, calculate complexity, and generates highly relevant markdown-formatted quick references with real-world examples.

**Currently Fully Supported:**
- ✅ **Python** - All skill levels (beginner fully implemented, intermediate/expert in development)
- ✅ **Library detection** - 15+ libraries (pandas, fastapi, asyncio have dedicated templates)
- ✅ **Other languages** - Quick reference tables only (no full templates yet)

---

## Features

- ✅ **Context-aware**: Analyzes code to detect libraries and complexity
- ✅ **Library detection**: 15+ libraries (pandas, fastapi, asyncio, etc.)
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
├── __init__.py
├── agent.py                 # Main CheatsheetAgent class (context-aware pipeline)
├── context_parser.py        # Parse multi-block code from frontend
├── library_detector.py      # Detect 15+ libraries with regex
├── complexity_scorer.py     # Score code complexity (10 features)
├── section_selector.py      # Smart section selection (library-first)
├── quick_reference.py       # Skill-level specific quick ref tables
├── enhanced_templates.py    # Real code examples (pandas, fastapi, asyncio)
├── generator.py             # Legacy content generation (fallback)
├── formatter.py             # Markdown formatting utilities
└── language_profiles.py     # Language configurations

src/tools/cheatsheet/
├── __init__.py
└── tools.py                 # Language detection helpers

Related Files:
├── src/api/routers.py       # Gateway endpoint registration
├── tests/test_cheatsheet.py # Unit tests (58 total)
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

**Basic Support (Quick Reference Only):**
- `javascript`, `typescript`, `java`, `go`, `rust`
- `c`, `cpp`, `csharp`, `html`, `css`
- `react`, `vue`, `ruby`, `php`, `swift`, `kotlin`, `bash`, `sql`

> [!NOTE]
> Basic support languages will return quick reference tables and detected libraries, but without full cheatsheet sections. Full template support planned for future versions.

### Skill Levels

| Level | Target Audience | Content Focus |
|-------|----------------|---------------|
| `beginner` | New learners | Basics, syntax, simple examples |
| `intermediate` | Working developers | Patterns, best practices, common tasks |
| `expert` | Advanced users | Advanced features, optimization, concurrency |

---

## API Usage

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

The tool uses regex patterns to detect programming languages:

```python
LANGUAGE_PATTERNS = {
    "python": r"(def |import |class |if __name__|print\()",
    "javascript": r"(function |const |let |var |=>|console\.log)",
    "typescript": r"(interface |type |: string|: number|<T>)",
    "java": r"(public class |public static void|import java\.)",
    "go": r"(package |func |import \(|defer |go )",
    "rust": r"(fn |let mut|impl |pub |match |use )",
    # ... more languages
}
```

---

## Library Detection (New in v0.8.0)

The tool automatically detects 15+ libraries from your code:

**Supported Libraries:**
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

## Language Profiles

```python
LANGUAGE_PROFILES = {
    "python": {
        "name": "Python",
        "version": "3.x",
        "topics": {
            "beginner": ["syntax", "types", "loops", "functions"],
            "intermediate": ["oop", "decorators", "comprehensions"],
            "expert": ["metaclasses", "async", "gil", "optimization"]
        }
    },
    "javascript": {
        "name": "JavaScript",
        "version": "ES6+",
        "topics": {
            "beginner": ["variables", "functions", "arrays", "objects"],
            "intermediate": ["promises", "async/await", "closures"],
            "expert": ["event-loop", "prototypes", "optimization"]
        }
    },
    # ... more languages
}
```

---

## Implementation Details

### Technology Stack
- **Jinja2** - Templating (if needed)
- **Regex** - Language detection
- **Python** - Content generation

### Generation Flow

```
User Request
    ↓
Language Detection (if code_context)
    ↓
Skill Level Selection
    ↓
Profile Loading
    ↓
Topic Selection
    ↓
Content Generation
    ↓
Markdown Formatting
    ↓
Cheat Sheet Output
```

### Code Location
- Agent: `src/agents/cheatsheet/agent.py`
- Generator: `src/agents/cheatsheet/generator.py`
- Profiles: `src/agents/cheatsheet/language_profiles.py`
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

### Unsupported Language

```json
{
  "language": "cobol"  // Not supported
}
```

**Response:**
```json
{
  "success": false,
  "message": "Language 'cobol' is not supported. Supported: python, javascript, ..."
}
```

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

### Detection Failed

```json
{
  "code_context": "some random text"  // Can't detect
}
```

**Response:**
```json
{
  "success": false,
  "message": "Could not detect language from code context"
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

## Customization

### Adding New Languages

```python
# In language_profiles.py
LANGUAGE_PROFILES["kotlin"] = {
    "name": "Kotlin",
    "version": "1.9+",
    "topics": {
        "beginner": ["syntax", "null-safety", "functions"],
        "intermediate": ["coroutines", "extensions", "dsl"],
        "expert": ["inline-functions", "reified", "contracts"]
    },
    "file_extensions": [".kt", ".kts"]
}
```

### Custom Topics

```python
# Override default topics
custom_topics = {
    "python": {
        "beginner": ["basics", "my-custom-topic"]
    }
}
```

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

**Last Updated:** December 23, 2025  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
