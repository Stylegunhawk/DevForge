# generate_cheatsheet - Dynamic Cheat Sheet Generator

**Tool Name:** `generate_cheatsheet`  
**Version:** 0.7.0  
**Phase:** 7 (Cheat Sheets)  
**Status:** ✅ Production Ready

---

## Overview

The `generate_cheatsheet` tool creates dynamic, skill-level appropriate programming language cheat sheets. It auto-detects languages from code context and generates markdown-formatted quick references tailored to beginner, intermediate, or expert developers.

---

## Features

- ✅ Auto-detect language from code context
- ✅ Skill-level based content generation
- ✅ Support for 15+ programming languages
- ✅ Markdown-formatted output
- ✅ Quick reference sections
- ✅ Code examples included
- ✅ Best practices and common patterns

---

## Folder Structure

```
src/agents/cheatsheet/
├── __init__.py
├── agent.py              # Main CheatsheetAgent class
├── generator.py          # Content generation logic
├── formatter.py          # Markdown formatting utilities
└── language_profiles.py  # Language configurations (LANGUAGE_PROFILES)

src/tools/cheatsheet/
├── __init__.py
└── tools.py             # Language detection and template helpers

Related Files:
├── src/api/routers.py    # Gateway endpoint registration
├── tests/test_cheatsheet.py  # Unit tests
└── manifests/devforge.json   # Tool definition (lines 176-204)
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

**Popular:**
- `python` - Python 3.x
- `javascript` - JavaScript ES6+
- `typescript` - TypeScript
- `java` - Java 17+
- `go` - Go 1.20+
- `rust` - Rust 1.70+

**Web:**
- `html` - HTML5
- `css` - CSS3
- `react` - React.js
- `vue` - Vue.js

**Systems:**
- `c` - C programming
- `cpp` - C++
- `csharp` - C#

**Others:**
- `ruby`, `php`, `swift`, `kotlin`, `bash`, `sql`

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
    "cheatsheet": "# Python Cheat Sheet - Beginner\n\n## Basic Syntax\n...",
    "language": "python",
    "skill_level": "beginner"
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

**Last Updated:** December 2, 2025  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
