# generate_cheatsheet - Context-Aware Cheat Sheet Generator

**Tool Name:** `generate_cheatsheet`  
**Version:** 1.1.0 (Multi-Context Language Support)  
**Status:** ✅ Production Ready  
**Architecture:** Hybrid (Rule-Based + LLM Fallback)  
**Response Time:** 
- Template Path: <200ms
- LLM Path: <5s

---

## 1. Overview

The `generate_cheatsheet` tool generates high-quality programming cheatsheets tailored to the user's code context. It uses a **Hybrid Architecture** that combines the speed of static templates for popular libraries (Pandas, React) with the flexibility of **Ollama-powered LLM generation** for unsupported languages (SQL, Rust) or fast-evolving libraries (LangChain).

### Key Capabilities
- **Hybrid Routing**: Intelligently routes requests to either:
    - **Template Engine**: For stable libraries (Zero cost, <200ms).
    - **LLM Generator**: For unsupported languages or complex queries (High coverage, <5s).
- **Multi-Context Language Support**: Supports Primary/Secondary/Auxiliary languages with 60% dominance rule.
- **Authoritative Language Detection**: Backend is the single source of truth for language detection, validates/overrides frontend language.
- **Hard-Fail Validation**: LLM output is strictly validated for syntax and structure. Invalid output is never shown.
- **Web Search Integration**: Fetches real-time documentation for "latest" queries (e.g., "latest langchain").
- **Context Analysis**: Parses multi-block code to understand usage patterns and language hints from frontend comments.
- **Complexity Scoring**: Auto-suggests skill levels (Beginner/Intermediate/Expert).

---

## 2. Detailed Workflow (The Hybrid Pipeline)

The tool follows a branched pipeline to ensure the best balance of speed and coverage.

```mermaid
graph TD
    A[Request] --> B[Domain Detector]
    B -- "Stable Lib / Simple" --> C[Template Path]
    B -- "Unsupported / Complex" --> D[LLM Path]
    
    subgraph "Template Path (<200ms)"
    C --> C1[Library Detector]
    C1 --> C2[Section Selector]
    C2 --> C3[Enricher (Optional)]
    C3 --> E[Final Response]
    end
    
    subgraph "LLM Path (<5s)"
    D --> D1{Need Search?}
    D1 -- Yes --> D2[Brave Search]
    D1 -- No --> D3[Ollama Generation]
    D2 --> D3
    D3 --> D4[Syntactic Validator]
    D4 -- Pass --> E
    D4 -- Fail --> D5[Retry w/ Feedback]
    D5 --> E
    end
```

### Step-by-Step Logic

1.  **Context Parsing**: `context_parser.py` extracts code blocks and language hints from frontend comments (`// language`).
2.  **Language Detection**: `tools.py` detects language from code patterns:
    - **Supported Languages**: Python, JavaScript, TypeScript, Ruby, SQL, Rust, Go
    - **Detection Order**: Rust → Go → JavaScript/TypeScript → Ruby → SQL → Python
    - **Language Hints**: Falls back to frontend comment hints if detection fails
3.  **Language Contract Validation**: `agent.py` enforces backend authority:
    - If frontend language differs from detected, backend overrides with detected language
    - Logs contract violations for debugging
4.  **Multi-Context Identification**: `agent.py` identifies Primary/Secondary/Auxiliary languages:
    - **Primary**: Must be >60% of meaningful code blocks
    - **Secondary**: Max 2, allowed for interop examples
    - **Auxiliary**: bash, shell, json, yaml, toml, text (always allowed, never dominant)
5.  **Domain Detection**: `domain_detector.py` analyzes the request.
    - If language is fully supported (Python, JS) AND libraries are stable (Pandas, React) -> **Template Path**.
    - If language is unsupported (SQL, Ruby, Rust, Go) OR library is fast-evolving (LangChain) -> **LLM Path**.
6.  **Template Path (Legacy)**:
    - Selects static templates from `enhanced_templates.py`.
    - Optionally enriches specific sections using `section_enricher.py`.
7.  **LLM Path (New)**:
    - **Search**: `brave_search.py` fetches docs if "latest" keywords found.
    - **Generate**: `llm_generator.py` calls **Ollama (gpt-oss:20b-cloud)** with primary/secondary language context.
    - **Validate**: `validators.py` checks AST syntax, structure, and 60% language dominance rule.
    - **Retry**: If validation fails, retries once with error feedback.
8.  **Return**: Unified JSON response with metadata.

---

## 3. Project Structure

```
src/agents/cheatsheet/
├── agent.py               # Main entry point (CheatsheetAgent)
├── config.py              # Settings (OLLAMA_MODEL, Feature Flags)
├── domain_detector.py     # Routing Logic (Template vs LLM)
├── llm_generator.py       # Async Ollama Orchestrator
├── validators.py          # Hard-Fail Safety Checks
├── section_enricher.py    # Async Scope-Limited Enricher
├── brave_search.py        # Web Search Client
├── search_strategy.py     # Query Builder
├── enhanced_templates.py  # Static Templates Database
├── library_detector.py    # Regex-based Detector
├── context_parser.py      # Code Block Extractor
└── tools/                 # Tool Definitions
```

## 4. Component Architecture (Actual Flows)

### A. Domain Detector (`domain_detector.py`)
- **Input**: Query, Detected Language, Libraries.
- **Logic**: Decides routing.
    - **LLM Path**: If unsupported language (SQL, Ruby, Rust, Go) or fast-evolving lib (LangChain).
    - **Template Path**: Default for Python/JS/TypeScript + Stable Libs.
- **Unsupported Languages**: SQL, Ruby, Rust, Go, TOML, YAML, Dockerfile, Nginx, Bash

### B. LLM Cheatsheet Generator (`llm_generator.py`)
- **Key Features**:
    - **Ollama Client**: Uses standard `src.llm.ollama_client`.
    - **Search Strategy**: Uses `brave_search.py` for "latest" queries.
    - **Validators**: `validators.py` ensures output safety.
    - **Multi-Context Support**: Accepts primary and secondary languages for interop examples.
    - **Language Contract**: Enforces primary language must be >60% of code blocks.

### C. Context Parser (`context_parser.py`)
*   **Input**: Raw string from frontend with `// language` comments.
*   **Logic**: Splits into blocks, extracts language hints from comments, strips fences.
*   **Output**: Structured `{'blocks': [...], 'total_lines': N, 'language_hints': [...]}`.
*   **Language Hints**: Preserves frontend's explicit language declarations for fallback detection.

### D. Library Detector (`library_detector.py`)
*   **Input**: Code blocks.
*   **Output**: List of unique library names (e.g., `pandas`, `react`).

### E. Section Selector (`section_selector.py`)
*   **Role**: Template Path logic. Safe fallback.

### F. Language Detection (`tools.py`)
*   **Input**: Code block strings.
*   **Output**: Detected language (Python, JavaScript, TypeScript, Ruby, SQL, Rust, Go, or None).
*   **Patterns**:
    - **JavaScript**: MongoDB patterns (`db.getMongo()`, `session.startTransaction()`, `$inc`, `$set`), Node.js (`require()`, `module.exports`), Promises (`.then()`, `.catch()`)
    - **Ruby**: `puts`, `gets`, `.class`, `.chomp`, `.to_i`, `.each`, symbols (`:symbol`), instance variables (`@var`)
    - **SQL**: SQL keywords (`SELECT`, `INSERT`, `UPDATE`, `CREATE`, etc.)
    - **Rust**: `fn`, `impl`, `struct`, `enum`, `pub`, `let mut`
    - **Go**: `func`, `package`, `import`, `:=`, `chan`
    - **Python**: `def`, `import`, `from ... import`, `print()`
*   **Language Hints**: Falls back to frontend comment hints if detection fails.

---

## 5. Language Support & Detection

### Supported Languages

**Full Support (Templates Available)**:
- Python ✅
- JavaScript ✅
- TypeScript ✅

**Experimental (LLM-Generated)**:
- Ruby 🧪
- SQL 🧪
- Rust 🧪
- Go 🧪

**Coming Soon**:
- Java, C++, C#, PHP, Swift, Kotlin, Bash, HTML, CSS

### Language Detection Priority

Detection order is critical to avoid false positives:
1. **Rust** (to avoid `let` confusion with TypeScript)
2. **Go** (distinctive `func`, `package`, `:=` patterns)
3. **JavaScript/TypeScript** (includes MongoDB, Node.js patterns)
4. **Ruby** (checked after JavaScript to avoid false positives)
5. **SQL** (SQL keywords)
6. **Python** (fallback for general scripting)

### Multi-Context Language Rules

- **Primary Language**: Must populate >60% of meaningful code blocks
- **Secondary Languages**: Max 2, allowed only for interop/setup sections
- **Auxiliary Languages**: bash, shell, json, yaml, toml, text (always allowed, never dominant)
- **Validation**: `validators.py` enforces 60% rule when `meaningful_blocks >= 2`

### Language Contract

**Backend is Authoritative**: The backend always validates and can override frontend language:
- If frontend sends `language: "sql"` but code detects `javascript` → Backend uses `javascript`
- Language hints from frontend comments (`// javascript`) are used as fallback if detection fails
- Contract violations are logged for debugging

## 6. API Specification

### Endpoint
`POST /api/gateway`

### Request Schema

```json
{
  "name": "generate_cheatsheet",
  "arguments": {
    "language": "python",          // Optional
    "skill_level": "intermediate", // Optional
    "code_context": "import pandas..." // Optional
  }
}
```

### Response Schema

```json
{
  "success": true,
  "data": {
    "language": "python",
    "skill_level": "intermediate",
    "detected_libraries": ["pandas"],
    "markdown": "# Python Cheat Sheet...",
    
    // Metadata (Universal)
    "method": "llm_with_search", // "template" | "llm_primary" | "llm_with_search" | "enriched"
    "generation_method": "llm_with_search",
    "web_search_used": true,
    "sources": ["https://docs.langchain.com/..."],
    "validation_score": 95.0,
    "routing_reason": "fast_evolving_lib:langchain",
    "quality_indicators": {
      "code_blocks": 9,
      "language_contract_honored": true,
      "headings": 19,
      "syntax_valid": true,
      "has_table": true
    },
    
    // Legacy Fields (For backward compatibility in Template Path)
    "sections": [{ "title": "..." }],
    "complexity_score": 45
  }
}
```

---

## 7. Usage Examples

### Scenario 1: The Learner (Beginner)
**Input**:
```json
{"language": "python", "skill_level": "beginner"}
```
**Result**:
- **Topics**: syntax, loops, basic functions.
- **Focus**: Syntax memorization.

### Scenario 2: The Data Scientist (Context-Aware)
**Input**:
```json
{
  "code_context": "df = pd.read_csv('data.csv')\ndf.groupby('id').sum()", 
  "skill_level": "intermediate"
}
```
**Result**:
- **Detected**: `pandas`.
- **Topics**: **Pandas Loading**, **Pandas Grouping**, Python Data Structures.
- **Focus**: Library API usage.

### Scenario 3: The System Architect (Expert)
**Input**:
```json
{
  "code_context": "@app.get('/')\nasync def root():...", 
  "skill_level": "expert"
}
```
**Result**:
- **Detected**: `fastapi`, `asyncio`.
- **Score**: 35 (Expert).
- **Topics**: **FastAPI Routes**, **Async/Await**, Decorators, Context Managers.
- **Focus**: Performance and Architecture.

### Scenario 4: Multi-Context Request (Ruby + SQL)
**Input**:
```json
{
  "code_context": "// ruby\nputs 'Hello'\n\n---\n\n// sql\nSELECT * FROM users", 
  "skill_level": "beginner"
}
```
**Result**:
- **Primary Language**: Ruby (first meaningful language detected)
- **Secondary Languages**: SQL (allowed for interop examples)
- **Routing**: LLM Path (`unsupported_language:ruby`)
- **Validation**: Enforces Ruby must be >60% of code blocks
- **Topics**: Ruby cheatsheet with SQL interop examples

### Scenario 5: Language Contract Enforcement
**Input**:
```json
{
  "language": "sql",
  "code_context": "// javascript\ndb.getMongo().startSession()"
}
```
**Result**:
- **Contract Violation**: Frontend sent `sql` but code detected `javascript`
- **Backend Override**: Uses `javascript` (backend is authoritative)
- **Logging**: Warning logged: "LANGUAGE CONTRACT VIOLATION"
- **Topics**: JavaScript cheatsheet (not SQL)
