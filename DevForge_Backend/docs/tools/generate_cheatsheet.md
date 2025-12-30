# generate_cheatsheet - Context-Aware Cheat Sheet Generator

**Tool Name:** `generate_cheatsheet`  
**Version:** 1.0.0 (Hybrid Phase)  
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
- **Hard-Fail Validation**: LLM output is strictly validated for syntax and structure. Invalid output is never shown.
- **Web Search Integration**: Fetches real-time documentation for "latest" queries (e.g., "latest langchain").
- **Context Analysis**: Parses multi-block code to understand usage patterns.
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

1.  **Domain Detection**: `domain_detector.py` analyzes the request.
    - If language is fully supported (Python, JS) AND libraries are stable (Pandas, React) -> **Template Path**.
    - If language is unsupported (SQL, Go) OR library is fast-evolving (LangChain) -> **LLM Path**.
2.  **Template Path (Legacy)**:
    - Selects static templates from `enhanced_templates.py`.
    - Optionally enriches specific sections using `section_enricher.py`.
3.  **LLM Path (New)**:
    - **Search**: `brave_search.py` fetches docs if "latest" keywords found.
    - **Generate**: `llm_generator.py` calls **Ollama (gpt-oss:20b-cloud)**.
    - **Validate**: `validators.py` checks AST syntax and structure.
    - **Retry**: If validation fails, retries once with error feedback.
4.  **Return**: Unified JSON response with metadata.

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
    - **LLM Path**: If unsupported language (SQL) or fast-evolving lib (LangChain).
    - **Template Path**: Default for Python/JS + Stable Libs.

### B. LLM Cheatsheet Generator (`llm_generator.py`)
- **Key Features**:
    - **Ollama Client**: Uses standard `src.llm.ollama_client`.
    - **Search Strategy**: Uses `brave_search.py` for "latest" queries.
    - **Validators**: `validators.py` ensures output safety.

### C. Context Parser (`context_parser.py`)
*   **Input**: Raw string from frontend.
*   **Logic**: Splits into blocks, strips fences.
*   **Output**: Structured `{'blocks': [...], 'total_lines': N}`.

### D. Library Detector (`library_detector.py`)
*   **Input**: Code blocks.
*   **Output**: List of unique library names (e.g., `pandas`, `react`).

### E. Section Selector (`section_selector.py`)
*   **Role**: Template Path logic. Safe fallback.

---

## 5. API Specification

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
    
    // Legacy Fields (For backward compatibility in Template Path)
    "sections": [{ "title": "..." }],
    "complexity_score": 45
  }
}
```

---

## 6. Usage Examples

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
