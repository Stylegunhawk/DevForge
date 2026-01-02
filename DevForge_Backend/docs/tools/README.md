# DevForge Backend - Tools Documentation Index

**Version:** 0.7.0  
**Last Updated:** December 2, 2025  
**Total Tools:** 6

---

## Overview

This directory contains comprehensive documentation for all DevForge Backend tools. Each tool is documented with a standardized format designed for easy LLM understanding and human readability.

---

## Documentation Format

Each tool documentation follows this structure:

1. **Header** - Tool name, version, phase, status
2. **Overview** - Brief description and key features
3. **Folder Structure** - Complete file/folder organization
4. **Parameters** - Detailed parameter specifications
5. **API Usage** - curl examples and responses
6. **Lobe Chat Usage** - Natural language examples
7. **Use Cases** - Real-world scenarios
8. **Implementation Details** - Tech stack and architecture
9. **Error Handling** - Common errors and solutions
10. **Examples** - Code samples and outputs
11. **Testing** - Test commands and coverage
12. **Best Practices** - Recommended usage patterns
13. **Troubleshooting** - Common issues and fixes
14. **Related Tools** - Integration with other tools

---

## Available Tools

### 1. generate_data - Mock Data Generation
**File:** [`generate_data.md`](./generate_data.md)  
**Phase:** 1 (Foundation)  
**Status:** ✅ Production Ready

**Description:** Generate realistic mock CSV/JSON data using Faker and Pandas

**Key Features:**
- Multiple format support (CSV, JSON)
- Custom field selection
- 1-10,000 row generation
- Fast execution (< 1s for small datasets)

**Common Use Cases:**
- API testing
- Database seeding
- UI prototyping
- Performance testing

---

### 2. retrieve_docs - RAG Document Retrieval
**File:** [`retrieve_docs.md`](./retrieve_docs.md)  
**Phase:** 3.1 (RAG Agent)  
**Status:** ✅ Production Ready

**Description:** Semantic document search using RAG with ChromaDB or Qdrant

**Key Features:**
- Multi-format support (PDF, MD, TXT, DOCX)
- Dual vector store (ChromaDB local + Qdrant cloud)
- Automatic reranking
- Configurable top-k results

**Common Use Cases:**
- Codebase documentation search
- API reference lookup
- Architecture documentation
- Troubleshooting guides

---

### 3. github_operation - GitHub Automation
**File:** [`github_operation.md`](./github_operation.md)  
**Phase:** 3.3 (GitHub Operations)  
**Status:** ✅ Production Ready

**Description:** Automate GitHub operations using natural language commands

**Key Features:**
- Natural language query parsing
- Repository management
- Issue creation
- File commits
- Pull request automation

**Common Use Cases:**
- Automated issue creation
- Repository listing
- Quick commits
- PR workflow automation

---

### 4. rerank_docs - Document Reranking
**File:** [`rerank_docs.md`](./rerank_docs.md)  
**Phase:** 4 (Reranking)  
**Status:** ✅ Production Ready

**Description:** Improve search quality using Cross-Encoder reranking

**Key Features:**
- Cross-Encoder based scoring
- Standalone or RAG-integrated
- 10-20% relevance improvement
- Fast inference (< 200ms)

**Common Use Cases:**
- Search result refinement
- Question answering
- Code snippet selection
- Document prioritization

---

### 5. refine_prompt - Prompt Optimization
**File:** [`refine_prompt.md`](./refine_prompt.md)  
**Phase:** 6 (Prompt Refinement)  
**Status:** ✅ Production Ready

**Description:** Optimize prompts for specific domains using LLM enhancement

**Key Features:**
- 5 domain types (general, image, code, rag, llm)
- 3 skill levels (beginner, intermediate, expert)
- Context-aware refinement
- Template-based enhancement

**Common Use Cases:**
- Image generation optimization
- Code specification enhancement
- RAG query improvement
- General LLM prompting

---

### 6. generate_cheatsheet - Dynamic Cheat Sheets
**File:** [`generate_cheatsheet.md`](./generate_cheatsheet.md)  
**Phase:** 7 (Cheat Sheets)  
**Status:** ✅ Production Ready

**Description:** Generate skill-level appropriate programming cheat sheets

**Key Features:**
- Auto language detection
- 15+ languages supported
- Skill-level adaptation
- Markdown formatted output

**Common Use Cases:**
- Learning resources
- Quick reference
- Code review aid
- Team onboarding

---

## Quick Start

### For LLMs

To understand a tool:
1. Read the tool's `.md` file
2. Review **Folder Structure** for code organization
3. Check **Parameters** for API specifications
4. Study **API Usage** for examples
5. Review **Use Cases** for context

### For Developers

```bash
# Navigate to docs
cd DevForge_Backend/docs/tools

# Read any tool documentation
cat generate_data.md
cat retrieve_docs.md
# ... etc
```

### For Users

Access through Lobe Chat using natural language:
- "Generate 100 user records in JSON format"
- "Search documentation for authentication examples"
- "Create a GitHub issue about the login bug"
- "Rerank these search results"
- "Refine this code prompt"
- "Generate a Python cheat sheet for beginners"

---

## Architecture Overview

### Project Structure

```
DevForge_Backend/
├── docs/
│   └── tools/               # THIS DIRECTORY
│       ├── README.md        # This file
│       ├── generate_data.md
│       ├── retrieve_docs.md
│       ├── github_operation.md
│       ├── rerank_docs.md
│       ├── refine_prompt.md
│       └── generate_cheatsheet.md
│
├── src/
│   ├── agents/              # Agent implementations
│   │   ├── datagen/
│   │   ├── rag/
│   │   ├── github/
│   │   ├── reranker.py
│   │   ├── prompt_refiner/
│   │   └── cheatsheet/
│   │
│   ├── tools/               # Tool functions
│   │   ├── datagen/
│   │   ├── rag/
│   │   ├── github/
│   │   └── cheatsheet/
│   │
│   ├── api/routers.py       # Gateway endpoints
│   └── main.py              # FastAPI app
│
├── manifests/
│   └── devforge.json        # MCP manifest (all tools)
│
└── tests/                   # Test suites
    ├── test_datagen.py
    ├── test_rag.py
    ├── test_github.py
    ├── test_reranker.py
    ├── test_prompt_refiner.py
    └── test_cheatsheet.py
```

---

## Tool Comparison

| Tool | Phase | Speed | Complexity | Use Frequency |
|------|-------|-------|------------|---------------|
| generate_data | 1 | ⚡ Fast | ⭐ Low | ⭐⭐⭐ High |
| retrieve_docs | 3 | ⚡ Fast | ⭐⭐ Medium | ⭐⭐⭐ High |
| github_operation | 3 | 🔄 Medium | ⭐⭐ Medium | ⭐⭐ Medium |
| rerank_docs | 4 | ⚡ Fast | ⭐⭐ Medium | ⭐ Low |
| refine_prompt | 6 | 🔄 Medium | ⭐⭐⭐ High | ⭐⭐ Medium |
| generate_cheatsheet | 7 | ⚡ Fast | ⭐ Low | ⭐⭐ Medium |

---

## Integration Patterns

### Tool Chains

**Data Generation + RAG:**
```
1. generate_data (create sample docs)
2. retrieve_docs (ingest and search)
```

**Prompt Optimization + Code Gen:**
```
1. refine_prompt (optimize code request)
2. Use refined prompt with Cursor/Copilot
```

**Search + Rerank + Learn:**
```
1. retrieve_docs (search documentation)
2. rerank_docs (improve results)
3. generate_cheatsheet (create reference)
```

**GitHub Workflow:**
```
1. refine_prompt (optimize issue description)
2. github_operation (create issue)
```

---

## API Gateway

All tools are accessed through a unified gateway:

**Endpoint:** `POST /api/gateway`

**Request Format:**
```json
{
  "name": "tool_name",
  "arguments": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

**Response Format:**
```json
{
  "success": true,
  "data": { ... },
  "message": "tool_name executed successfully"
}
```

---

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Tool Tests
```bash
pytest tests/test_datagen.py -v
pytest tests/test_rag.py -v
pytest tests/test github.py -v
pytest tests/test_reranker.py -v
pytest tests/test_prompt_refiner.py -v
pytest tests/test_cheatsheet.py -v
```

### Test Coverage
**Total:** 100+ tests across all tools

---

## Development Phases

| Phase | Features | Status |
|-------|----------|--------|
| Phase 1 | Foundation (DataGen, MCP) | ✅ Complete |
| Phase 2 | Multi-Model Routing | ✅ Complete |
| Phase 3 | RAG + GitHub | ✅ Complete |
| Phase 4 | Reranking | ✅ Complete |
| Phase 5 | Deployment | ⏳ Deferred |
| Phase 6 | Prompt Refinement | ✅ Complete |
| Phase 7 | Cheat Sheets | ✅ Complete |

---

## Contributing

### Adding New Tool Documentation

1. Create new `.md` file in `docs/tools/`
2. Follow standardized format (see existing docs)
3. Include all sections:
   - Overview
   - Folder Structure
   - Parameters
   - API Usage
   - Examples
   - Testing
4. Update this README with new tool
5. Update manifest (`manifests/devforge.json`)

---

## Support

**Documentation Issues:**
- Check individual tool `.md` files
- Review **Troubleshooting** sections
- See **Best Practices** for guidance

**Code Issues:**
- Run tests: `pytest tests/ -v`
- Check server logs
- Review **Error Handling** sections

**Feature Requests:**
- Create GitHub issue
- Reference tool documentation
- Provide use case examples

---

## Resources

- **Main README:** [`../../README.md`](../../README.md)
- **Backend Plan:** [`../../BACKEND_PLAN.md`](../../BACKEND_PLAN.md)
- **Phase Status:** [`../../PHASE_STATUS.md`](../../PHASE_STATUS.md)
- **Manifest:** [`../../manifests/devforge.json`](../../manifests/devforge.json)

---

**Documentation Version:** 1.0  
**Backend Version:** 0.7.0  
**Last Updated:** December 2, 2025  
**Maintained By:** DevForge Team
