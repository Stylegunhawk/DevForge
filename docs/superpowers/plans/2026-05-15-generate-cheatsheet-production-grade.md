# generate_cheatsheet v0.11 Production-Grade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python-only string-template cheatsheet pipeline with an activity-driven, AI-personalized, deterministically-grounded system backed by curated YAML knowledge packs.

**Architecture:** Three layers — (1) ground-truth YAML packs in `data/cheatsheet_packs/`, (2) single LLM personalization call that ranks/annotates (never writes code), (3) deterministic markdown render. Reuses existing `model_router.invoke_with_usage`, `context_parser`, `library_detector`, `complexity_scorer`.

**Tech Stack:** Python 3.12, Pydantic 2.12, PyYAML, tree-sitter 0.21 + tree-sitter-languages 1.10.2, LangChain Ollama via `model_router`, pytest 8.

**Spec:** `docs/superpowers/specs/2026-05-15-generate-cheatsheet-production-grade-design.md`

**Branch:** `rag_resolve` (current)

---

## Out-of-band ops (user runs, NOT in this plan)

| Step | When | Who |
|------|------|-----|
| Run `scripts/bootstrap_cheatsheet_packs.py --all` to seed all 69 packs | After Task 6 lands in the working tree | User (requires running Ollama, ~30 min) |
| Manual PR-style review of bootstrap output | After bootstrap run | User |
| Live MCP verification (5 scenarios) | After Task 13 | User |

Tasks 1–13 in this plan are the agent-implementable scope. Tasks 4 and 5 ship a **manual seed pack** (Python beginner only) + the **bootstrap script** so the pipeline can be end-to-end tested with one pack before the user runs the full bootstrap.

---

## File map

```
NEW:
  data/cheatsheet_packs/languages/python/beginner.yaml   # Seed pack only
  src/agents/cheatsheet/pack_models.py
  src/agents/cheatsheet/pack_loader.py
  src/agents/cheatsheet/language_detector.py
  src/agents/cheatsheet/request_model.py
  src/agents/cheatsheet/personalizer.py
  src/agents/cheatsheet/markdown_renderer.py
  scripts/bootstrap_cheatsheet_packs.py
  scripts/validate_cheatsheet_packs.py
  tests/test_cheatsheet_pack_models.py
  tests/test_cheatsheet_pack_loader.py
  tests/test_cheatsheet_personalizer.py
  tests/test_cheatsheet_renderer.py
  tests/test_cheatsheet_language_detector.py
  tests/test_cheatsheet_request_model.py

REWRITTEN:
  src/agents/cheatsheet/agent.py

UNCHANGED (kept as-is):
  src/agents/cheatsheet/context_parser.py
  src/agents/cheatsheet/library_detector.py
  src/agents/cheatsheet/complexity_scorer.py

DELETED:
  src/agents/cheatsheet/enhanced_templates.py
  src/agents/cheatsheet/section_selector.py
  src/agents/cheatsheet/quick_reference.py
  src/tools/cheatsheet/tools.py
  src/tools/cheatsheet/  (whole directory)

MODIFIED:
  src/api/routers/__init__.py             # TOOL_DESCRIPTIONS + _get_tool_schema
  manifests/devforge.json                  # version 0.10.0 → 0.11.0
  tests/test_cheatsheet.py                 # rewrite high-level tests
  docs/tools/generate_cheatsheet.md        # rewrite for v0.11
  DevForge_Backend/CLAUDE.md               # bump generate_cheatsheet row
```

---

## Task 1: Pack Pydantic models

**Files:**
- Create: `src/agents/cheatsheet/pack_models.py`
- Test: `tests/test_cheatsheet_pack_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cheatsheet_pack_models.py
from datetime import date
import pytest
from pydantic import ValidationError
from src.agents.cheatsheet.pack_models import Example, Entry, PackMeta, Pack


def _valid_example():
    return {"title": "Basic", "language": "python", "code": "x = 1"}


def _valid_entry():
    return {
        "id": "py.beginner.variables",
        "title": "Variables",
        "explanation": "Dynamic typing.",
        "examples": [_valid_example()],
        "pitfalls": ["Mind tabs vs spaces."],
    }


def _valid_meta(library=None):
    return {
        "language": "python",
        "skill_level": "beginner",
        "version": 1,
        "last_reviewed": date(2026, 5, 15),
        "reviewer": "sid",
        **({"library": library} if library else {}),
    }


def test_example_round_trip():
    ex = Example(**_valid_example())
    assert ex.language == "python"


def test_entry_requires_at_least_one_example_and_pitfall():
    entry = Entry(**_valid_entry())
    assert len(entry.examples) == 1
    assert len(entry.pitfalls) == 1


def test_entry_rejects_zero_examples():
    bad = _valid_entry()
    bad["examples"] = []
    with pytest.raises(ValidationError):
        Entry(**bad)


def test_entry_rejects_zero_pitfalls():
    bad = _valid_entry()
    bad["pitfalls"] = []
    with pytest.raises(ValidationError):
        Entry(**bad)


def test_pack_requires_3_to_12_entries():
    base = {"pack": _valid_meta(), "entries": [_valid_entry()] * 3}
    Pack(**base)
    base["entries"] = [_valid_entry()] * 12
    Pack(**base)
    base["entries"] = [_valid_entry()] * 2
    with pytest.raises(ValidationError):
        Pack(**base)
    base["entries"] = [_valid_entry()] * 13
    with pytest.raises(ValidationError):
        Pack(**base)


def test_pack_skill_level_enum():
    bad = {"pack": {**_valid_meta(), "skill_level": "novice"},
           "entries": [_valid_entry()] * 3}
    with pytest.raises(ValidationError):
        Pack(**bad)


def test_library_pack_carries_library_field():
    meta = _valid_meta(library="pandas")
    meta["library_version_floor"] = "2.0"
    pack = Pack(pack=meta, entries=[_valid_entry()] * 3)
    assert pack.pack.library == "pandas"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet_pack_models.py -v`
Expected: FAIL with `ModuleNotFoundError: src.agents.cheatsheet.pack_models`

- [ ] **Step 3: Implement pack_models.py**

```python
# src/agents/cheatsheet/pack_models.py
"""Pydantic models for cheatsheet knowledge packs."""

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    language: str
    code: str


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    explanation: str
    tags: list[str] = []
    when_to_use: str = ""
    examples: list[Example] = Field(min_length=1)
    pitfalls: list[str] = Field(min_length=1)


class PackMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str
    skill_level: Literal["beginner", "intermediate", "expert"]
    version: int = 1
    library: Optional[str] = None
    library_version_floor: Optional[str] = None
    last_reviewed: date
    reviewer: str


class Pack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack: PackMeta
    entries: list[Entry] = Field(min_length=3, max_length=12)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cheatsheet_pack_models.py -v`
Expected: 7 PASSED

---

## Task 2: Seed pack (Python beginner) — manual ground truth for testing

**Files:**
- Create: `data/cheatsheet_packs/languages/python/beginner.yaml`

- [ ] **Step 1: Write the seed pack**

```yaml
# data/cheatsheet_packs/languages/python/beginner.yaml
pack:
  language: python
  skill_level: beginner
  version: 1
  last_reviewed: 2026-05-15
  reviewer: sid

entries:
  - id: py.beginner.variables
    title: "Variables & Types"
    explanation: "Python uses dynamic typing — variables don't declare types up front."
    tags: [syntax, fundamentals]
    when_to_use: "Always — the foundation of any Python program."
    examples:
      - title: "Basic assignment"
        language: python
        code: |
          name = "Alice"
          age = 25
          price = 19.99
          is_active = True
      - title: "Type hints (optional, modern style)"
        language: python
        code: |
          name: str = "Alice"
          age: int = 25
    pitfalls:
      - "Reassigning to a different type is legal but error-prone — use type hints to make intent explicit."
      - "`is` checks identity, not equality. Use `==` for value comparison."

  - id: py.beginner.control_flow
    title: "Control Flow"
    explanation: "Branching and looping over collections."
    tags: [syntax, fundamentals]
    when_to_use: "Conditional logic, iteration over lists/dicts."
    examples:
      - title: "If/elif/else"
        language: python
        code: |
          if age >= 18:
              print("Adult")
          elif age >= 13:
              print("Teen")
          else:
              print("Child")
      - title: "For loop"
        language: python
        code: |
          for i in range(5):
              print(i)
    pitfalls:
      - "Python uses indentation for blocks — mixing tabs and spaces breaks code."
      - "`for ... else:` runs when the loop exits without break."

  - id: py.beginner.functions
    title: "Functions"
    explanation: "Reusable named blocks of code."
    tags: [syntax, fundamentals]
    when_to_use: "Any logic used more than once, or worth naming."
    examples:
      - title: "Basic function"
        language: python
        code: |
          def greet(name: str) -> str:
              return f"Hello, {name}!"
      - title: "Default arguments"
        language: python
        code: |
          def power(base, exponent=2):
              return base ** exponent
    pitfalls:
      - "Default arguments evaluate once at definition time — never use a mutable default like `[]` or `{}`."
      - "Functions without `return` implicitly return `None`."

  - id: py.beginner.collections
    title: "Lists, Dicts, Tuples, Sets"
    explanation: "Python's four built-in collection types."
    tags: [data-structures, fundamentals]
    when_to_use: "Lists for ordered, dicts for keyed lookup, tuples for fixed records, sets for uniqueness."
    examples:
      - title: "List operations"
        language: python
        code: |
          nums = [1, 2, 3]
          nums.append(4)
          first = nums[0]
      - title: "Dict operations"
        language: python
        code: |
          person = {"name": "Alice", "age": 25}
          age = person.get("age", 0)
          person["email"] = "alice@example.com"
    pitfalls:
      - "Dicts preserve insertion order since Python 3.7 — but don't rely on this for keyed access semantics."
      - "Tuples are immutable; lists are mutable. Use tuples for fixed records and dict keys."

  - id: py.beginner.io
    title: "Basic I/O"
    explanation: "Reading from stdin, writing to stdout, and file handling."
    tags: [io, fundamentals]
    when_to_use: "Interacting with the user or persisting data."
    examples:
      - title: "Print and input"
        language: python
        code: |
          name = input("Your name: ")
          print(f"Hello, {name}!")
      - title: "Read a file"
        language: python
        code: |
          with open("data.txt", "r") as f:
              contents = f.read()
    pitfalls:
      - "Always use `with` for file handles — it closes the file even if an exception is raised."
      - "`input()` returns a string. Convert with `int(...)` or `float(...)` if you need a number."
```

- [ ] **Step 2: Verify YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('data/cheatsheet_packs/languages/python/beginner.yaml'))"`
Expected: no output (exit 0)

---

## Task 3: Pack loader with L1/L2 cache

**Files:**
- Create: `src/agents/cheatsheet/pack_loader.py`
- Test: `tests/test_cheatsheet_pack_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cheatsheet_pack_loader.py
import pytest
from pathlib import Path
from src.agents.cheatsheet.pack_loader import (
    PackLoader,
    SUPPORTED_LANGUAGES,
    PackNotFoundError,
)


@pytest.fixture
def loader():
    root = Path(__file__).parent.parent / "data" / "cheatsheet_packs"
    return PackLoader(root=root)


def test_supported_languages_contains_9():
    assert set(SUPPORTED_LANGUAGES) == {
        "python", "javascript", "typescript", "go", "rust",
        "java", "ruby", "php", "csharp",
    }


def test_load_seed_python_beginner_pack(loader):
    pack = loader.load_language_pack("python", "beginner")
    assert pack.pack.language == "python"
    assert pack.pack.skill_level == "beginner"
    assert len(pack.entries) >= 3
    assert any(e.id == "py.beginner.variables" for e in pack.entries)


def test_load_missing_pack_raises(loader):
    with pytest.raises(PackNotFoundError):
        loader.load_language_pack("python", "intermediate")


def test_load_unsupported_language_raises(loader):
    with pytest.raises(PackNotFoundError):
        loader.load_language_pack("cobol", "beginner")


def test_l2_cache_returns_same_object(loader):
    p1 = loader.load_language_pack("python", "beginner")
    p2 = loader.load_language_pack("python", "beginner")
    assert p1 is p2


def test_load_library_pack_missing_returns_none(loader):
    # No library packs exist yet in seed
    assert loader.load_library_pack("pandas", "beginner") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet_pack_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement pack_loader.py**

```python
# src/agents/cheatsheet/pack_loader.py
"""Load + cache cheatsheet knowledge packs from disk."""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import yaml

from src.agents.cheatsheet.pack_models import Pack

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = (
    "python", "javascript", "typescript", "go", "rust",
    "java", "ruby", "php", "csharp",
)


class PackNotFoundError(Exception):
    """Raised when a required pack file is missing."""


class PackLoader:
    """Disk-cached loader for YAML knowledge packs.

    L2 cache: maps (file_path, mtime_ns) -> parsed Pack object.
    Reload on file modification without process restart.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._cache: Dict[Tuple[str, int], Pack] = {}

    def load_language_pack(self, language: str, skill_level: str) -> Pack:
        if language not in SUPPORTED_LANGUAGES:
            raise PackNotFoundError(
                f"Language {language!r} not supported. "
                f"Supported: {', '.join(SUPPORTED_LANGUAGES)}."
            )
        path = self.root / "languages" / language / f"{skill_level}.yaml"
        return self._load(path)

    def load_library_pack(self, library: str, skill_level: str) -> Optional[Pack]:
        path = self.root / "libraries" / library / f"{skill_level}.yaml"
        if not path.exists():
            return None
        return self._load(path)

    def _load(self, path: Path) -> Pack:
        if not path.exists():
            raise PackNotFoundError(f"Pack file missing: {path}")
        mtime = path.stat().st_mtime_ns
        key = (str(path), mtime)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        pack = Pack(**raw)
        self._cache[key] = pack
        logger.info(f"Loaded pack {path.relative_to(self.root)}")
        return pack
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cheatsheet_pack_loader.py -v`
Expected: 6 PASSED

---

## Task 4: Tree-sitter validation script (CI gate)

**Files:**
- Create: `scripts/validate_cheatsheet_packs.py`

- [ ] **Step 1: Implement the validator**

```python
# scripts/validate_cheatsheet_packs.py
"""CI gate: validate all cheatsheet packs.

Runs:
  1. YAML parses and matches Pack pydantic schema.
  2. Every example's `code` parses cleanly under its declared language grammar
     via tree-sitter-languages. 0 syntax errors required.
  3. Entry ids are globally unique across all packs.

Exit code 0 on success, non-zero on any failure.
"""

import sys
from pathlib import Path
import yaml

from src.agents.cheatsheet.pack_models import Pack

# tree-sitter-languages exposes a single get_parser() per language name
try:
    from tree_sitter_languages import get_parser
    HAVE_TREE_SITTER = True
except ImportError:
    HAVE_TREE_SITTER = False

# Map our pack language strings to tree-sitter-languages grammar names
TS_GRAMMAR_MAP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "go": "go",
    "rust": "rust",
    "java": "java",
    "ruby": "ruby",
    "php": "php",
    "csharp": "c_sharp",
}


def _has_errors(node) -> bool:
    """Walk the AST; return True if any node is an ERROR or is_missing."""
    if node.has_error or node.is_missing:
        return True
    for child in node.children:
        if _has_errors(child):
            return True
    return False


def validate_pack(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        pack = Pack(**raw)
    except Exception as e:
        return [f"{path}: schema error: {e}"]

    if not HAVE_TREE_SITTER:
        return errors

    for entry in pack.entries:
        for ex in entry.examples:
            grammar = TS_GRAMMAR_MAP.get(ex.language)
            if grammar is None:
                errors.append(
                    f"{path}::{entry.id}::{ex.title}: "
                    f"no tree-sitter grammar mapped for language {ex.language!r}"
                )
                continue
            try:
                parser = get_parser(grammar)
                tree = parser.parse(ex.code.encode("utf-8"))
                if _has_errors(tree.root_node):
                    errors.append(
                        f"{path}::{entry.id}::{ex.title}: syntax error in {ex.language} example"
                    )
            except Exception as e:
                errors.append(
                    f"{path}::{entry.id}::{ex.title}: tree-sitter parse failed: {e}"
                )
    return errors


def main(root: str) -> int:
    root_path = Path(root)
    all_errors: list[str] = []
    all_ids: dict[str, str] = {}  # id -> first pack file that declared it

    for path in sorted(root_path.rglob("*.yaml")):
        errors = validate_pack(path)
        all_errors.extend(errors)

        try:
            with path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            for entry in raw.get("entries", []):
                eid = entry.get("id")
                if eid in all_ids:
                    all_errors.append(
                        f"{path}: duplicate entry id {eid!r} "
                        f"(first seen in {all_ids[eid]})"
                    )
                else:
                    all_ids[eid] = str(path)
        except Exception:
            pass  # already reported above

    if all_errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: validated {len(all_ids)} entries across all packs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/cheatsheet_packs"))
```

- [ ] **Step 2: Run validator against seed pack**

Run: `python scripts/validate_cheatsheet_packs.py data/cheatsheet_packs/`
Expected: `OK: validated N entries across all packs` (where N is entry count in seed pack)

---

## Task 5: Bootstrap script (CLI, not run in CI)

**Files:**
- Create: `scripts/bootstrap_cheatsheet_packs.py`

- [ ] **Step 1: Implement the bootstrap CLI**

```python
# scripts/bootstrap_cheatsheet_packs.py
"""One-shot LLM bootstrap for cheatsheet packs.

Run once per (language|library, skill_level) combination. Writes YAML to
data/cheatsheet_packs/. Idempotent: skips existing files unless --overwrite.

NOT in CI. Offline ops script run by humans, output reviewed via PR.

Usage:
  python scripts/bootstrap_cheatsheet_packs.py --all
  python scripts/bootstrap_cheatsheet_packs.py --language python --skill beginner
  python scripts/bootstrap_cheatsheet_packs.py --library pandas --skill expert
  python scripts/bootstrap_cheatsheet_packs.py --all --overwrite
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from src.agents.cheatsheet.pack_models import Pack
from src.agents.cheatsheet.pack_loader import SUPPORTED_LANGUAGES
from src.agents.cheatsheet.library_detector import LIBRARY_SIGNATURES
from src.core.model_router import model_router

logger = logging.getLogger(__name__)

PACK_ROOT = Path("data/cheatsheet_packs")
REPORT_PATH = Path("scripts/bootstrap_report.md")
SKILL_LEVELS = ("beginner", "intermediate", "expert")

SYSTEM_PROMPT = """You are a senior software engineer writing a cheat sheet pack.

Output STRICT YAML matching this schema:

pack:
  language: <lang>                 # tree-sitter grammar name
  skill_level: <beginner|intermediate|expert>
  version: 1
  last_reviewed: <YYYY-MM-DD>
  reviewer: bootstrap
  # library packs ONLY:
  # library: <name>
  # library_version_floor: <semver>

entries:
  - id: <stable-kebab-or-dotted-id>
    title: <short title>
    explanation: <1-2 sentence overview>
    tags: [<tag1>, <tag2>]
    when_to_use: <one sentence — used for activity-driven ranking>
    examples:
      - title: <short>
        language: <lang>
        code: |
          <canonical idiomatic code, syntactically valid>
    pitfalls:
      - <one common mistake>
      - <another>

Constraints:
- 5 to 8 entries.
- Each example must compile/parse — use canonical idioms only.
- For libraries: assume the latest stable version, state library_version_floor.
- Output ONLY the YAML — no markdown fences, no prose."""


def _user_prompt(target_kind: str, target_name: str, skill: str) -> str:
    if target_kind == "language":
        return (
            f"Generate a {skill}-level cheat sheet pack for the {target_name} programming language. "
            f"Use {target_name} for all examples. "
            f"Today's date is {date.today().isoformat()}."
        )
    else:
        return (
            f"Generate a {skill}-level cheat sheet pack for the {target_name} Python library. "
            f"All examples must use Python and import {target_name}. "
            f"Today's date is {date.today().isoformat()}."
        )


async def _bootstrap_one(
    target_kind: str,
    target_name: str,
    skill: str,
    overwrite: bool,
) -> tuple[Path, str]:
    """Returns (path_written, outcome_string)."""
    sub = "languages" if target_kind == "language" else "libraries"
    path = PACK_ROOT / sub / target_name / f"{skill}.yaml"
    if path.exists() and not overwrite:
        return path, "skipped (exists)"

    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 4):  # 1 initial + 2 retries
        prompt = _user_prompt(target_kind, target_name, skill)
        try:
            response = await model_router.invoke_with_usage(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                task_type="cheatsheet_bootstrap",
                tenant_id="bootstrap",
                integration_name="bootstrap_cli",
                user_id="bootstrap",
                temperature=0,
            )
            content = response.content if hasattr(response, "content") else str(response)
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith(("yaml\n", "yml\n")):
                    content = content.split("\n", 1)[1]
            raw = yaml.safe_load(content)
            pack = Pack(**raw)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(pack.model_dump(mode="json"), f, sort_keys=False, allow_unicode=True)
            return path, f"ok (attempt {attempt})"
        except Exception as e:
            logger.warning(f"{target_kind}/{target_name}/{skill} attempt {attempt} failed: {e}")
            if attempt == 3:
                return path, f"FAILED after 3 attempts: {e}"
    return path, "unreachable"


async def _run(args) -> int:
    targets: list[tuple[str, str, str]] = []
    if args.all:
        for lang in SUPPORTED_LANGUAGES:
            for skill in SKILL_LEVELS:
                targets.append(("language", lang, skill))
        for lib in LIBRARY_SIGNATURES.keys():
            for skill in SKILL_LEVELS:
                targets.append(("library", lib, skill))
    elif args.language:
        skills = [args.skill] if args.skill else SKILL_LEVELS
        for skill in skills:
            targets.append(("language", args.language, skill))
    elif args.library:
        skills = [args.skill] if args.skill else SKILL_LEVELS
        for skill in skills:
            targets.append(("library", args.library, skill))
    else:
        print("Specify --all, --language, or --library", file=sys.stderr)
        return 1

    print(f"Bootstrapping {len(targets)} packs...")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("a", encoding="utf-8") as report:
        report.write(f"\n## Bootstrap run {date.today().isoformat()}\n\n")
        for i, (kind, name, skill) in enumerate(targets, 1):
            path, outcome = await _bootstrap_one(kind, name, skill, args.overwrite)
            line = f"{i:3d}/{len(targets)} | {kind:8s} | {name:20s} | {skill:12s} | {outcome}"
            print(line)
            report.write(f"- {line}\n")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--language", choices=list(SUPPORTED_LANGUAGES))
    ap.add_argument("--library", choices=list(LIBRARY_SIGNATURES.keys()))
    ap.add_argument("--skill", choices=list(SKILL_LEVELS))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify CLI parses without running**

Run: `python scripts/bootstrap_cheatsheet_packs.py --help`
Expected: argparse help text, exit 0

---

## Task 6: Language detector (tree-sitter-backed, returns Optional[str])

**Files:**
- Create: `src/agents/cheatsheet/language_detector.py`
- Test: `tests/test_cheatsheet_language_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cheatsheet_language_detector.py
from src.agents.cheatsheet.language_detector import detect_language


def test_detect_python():
    code = "def add(a, b):\n    return a + b\n"
    assert detect_language(code) == "python"


def test_detect_javascript():
    code = "const greet = (name) => console.log(`Hello, ${name}`);\n"
    assert detect_language(code) == "javascript"


def test_detect_typescript_via_annotation():
    code = "function add(a: number, b: number): number { return a + b; }\n"
    assert detect_language(code) == "typescript"


def test_detect_go():
    code = "package main\nimport \"fmt\"\nfunc main() { fmt.Println(\"hi\") }\n"
    assert detect_language(code) == "go"


def test_detect_rust():
    code = "fn main() { let x: i32 = 5; println!(\"{}\", x); }\n"
    assert detect_language(code) == "rust"


def test_returns_none_on_unknown():
    code = "????? not real code ????? @@@@ ####"
    assert detect_language(code) is None


def test_returns_none_on_empty():
    assert detect_language("") is None
    assert detect_language("   \n  ") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet_language_detector.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement language_detector.py**

```python
# src/agents/cheatsheet/language_detector.py
"""Heuristic language detection for cheat sheet code context.

Returns Optional[str] — None on failure (no silent python fallback).
Uses regex-based heuristics for speed. Tree-sitter is reserved for the
pack validator where false positives are unacceptable.
"""

import re
from typing import Optional


_SIGNATURES = [
    # (language, list of regex patterns; ANY match wins)
    ("go", [
        r"^\s*package\s+\w+\s*$",
        r"\bfunc\s+\w+\s*\(",
        r":=",
        r'\bimport\s+"',
    ]),
    ("rust", [
        r"\bfn\s+\w+\s*\(",
        r"\blet\s+(mut\s+)?\w+\s*:",
        r"\b(println|print|eprintln)!\s*\(",
        r"\b(impl|trait|enum)\s+\w+",
    ]),
    ("typescript", [
        r":\s*(string|number|boolean|any|unknown|void)\b",
        r"\binterface\s+\w+\s*\{",
        r"\btype\s+\w+\s*=",
        r"\bas\s+(string|number|boolean|const)\b",
    ]),
    ("javascript", [
        r"\bconst\s+\w+\s*=",
        r"\blet\s+\w+\s*=",
        r"\bfunction\s+\w+\s*\(",
        r"\bconsole\.log\s*\(",
        r"=>",
    ]),
    ("java", [
        r"\bpublic\s+(static\s+)?(class|void|int|String)\b",
        r"\bSystem\.out\.println\s*\(",
        r"\bimport\s+java\.",
    ]),
    ("csharp", [
        r"\busing\s+System(\.|;)",
        r"\bnamespace\s+\w+",
        r"\bConsole\.WriteLine\s*\(",
        r"\bpublic\s+(static\s+)?(void|int|string)\b",
    ]),
    ("ruby", [
        r"^\s*def\s+\w+(\s|$)",
        r"\bputs\s+",
        r"\brequire\s+['\"]",
        r"\bend\s*$",
    ]),
    ("php", [
        r"<\?php",
        r"\$\w+\s*=",
        r"\bfunction\s+\w+\s*\(",
        r"\becho\s+",
    ]),
    ("python", [
        r"^\s*def\s+\w+\s*\(",
        r"^\s*import\s+\w+",
        r"^\s*from\s+\w+\s+import",
        r"\bprint\s*\(",
        r":\s*$",  # colon-at-end-of-line (block intro)
    ]),
]


def detect_language(code: str) -> Optional[str]:
    """Return language name or None if not recognised."""
    if not code or not code.strip():
        return None
    # Score each language by number of matched patterns; return highest non-zero.
    scores: dict[str, int] = {}
    for lang, patterns in _SIGNATURES:
        n = 0
        for p in patterns:
            if re.search(p, code, flags=re.MULTILINE):
                n += 1
        if n:
            scores[lang] = n
    if not scores:
        return None
    # On tie, the earlier entry in _SIGNATURES wins (TS > JS, etc.)
    best_lang = None
    best_score = 0
    for lang, _ in _SIGNATURES:
        if scores.get(lang, 0) > best_score:
            best_score = scores[lang]
            best_lang = lang
    return best_lang
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cheatsheet_language_detector.py -v`
Expected: 7 PASSED

---

## Task 7: Request model (Pydantic validation gate)

**Files:**
- Create: `src/agents/cheatsheet/request_model.py`
- Test: `tests/test_cheatsheet_request_model.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cheatsheet_request_model.py
import pytest
from pydantic import ValidationError
from src.agents.cheatsheet.request_model import CheatsheetRequest


def test_accepts_language_only():
    req = CheatsheetRequest(language="python")
    assert req.skill_level == "beginner"
    assert req.intent is None


def test_accepts_code_context_only():
    CheatsheetRequest(code_context="def foo(): pass")


def test_accepts_intent_only():
    CheatsheetRequest(intent="debugging async deadlock")


def test_rejects_all_three_missing():
    with pytest.raises(ValidationError):
        CheatsheetRequest()


def test_skill_level_enum():
    with pytest.raises(ValidationError):
        CheatsheetRequest(language="python", skill_level="novice")


def test_intent_max_length():
    with pytest.raises(ValidationError):
        CheatsheetRequest(intent="x" * 401)


def test_code_context_max_length():
    with pytest.raises(ValidationError):
        CheatsheetRequest(code_context="x" * 20001)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet_request_model.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement request_model.py**

```python
# src/agents/cheatsheet/request_model.py
"""Pydantic gate for /generate_cheatsheet requests."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class CheatsheetRequest(BaseModel):
    language: Optional[str] = None
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    code_context: Optional[str] = Field(default=None, max_length=20000)
    intent: Optional[str] = Field(default=None, max_length=400)

    @model_validator(mode="after")
    def validate_at_least_one(self) -> "CheatsheetRequest":
        if not (self.language or self.code_context or self.intent):
            raise ValueError(
                "Must provide at least one of: language, code_context, or intent."
            )
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cheatsheet_request_model.py -v`
Expected: 7 PASSED

---

## Task 8: Personalizer (LLM call + retry + deterministic fallback)

**Files:**
- Create: `src/agents/cheatsheet/personalizer.py`
- Test: `tests/test_cheatsheet_personalizer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cheatsheet_personalizer.py
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.cheatsheet.pack_models import Pack, PackMeta, Entry, Example
from src.agents.cheatsheet.personalizer import (
    Personalizer,
    PersonalizationOutput,
    RankedEntry,
)
from datetime import date


def _entry(eid: str, tags: list[str] = None) -> Entry:
    return Entry(
        id=eid,
        title=f"Title for {eid}",
        explanation="Explanation.",
        tags=tags or [],
        when_to_use="When useful.",
        examples=[Example(title="t", language="python", code="x = 1")],
        pitfalls=["Pitfall."],
    )


def _pack(language: str = "python", skill: str = "beginner", entry_ids: list[str] = None) -> Pack:
    meta = PackMeta(
        language=language, skill_level=skill, version=1,
        last_reviewed=date(2026, 5, 15), reviewer="test",
    )
    entries = [_entry(eid) for eid in (entry_ids or ["e1", "e2", "e3"])]
    return Pack(pack=meta, entries=entries)


@pytest.fixture
def personalizer():
    return Personalizer()


@pytest.fixture
def mock_router_response():
    def _make(content: str):
        resp = AsyncMock()
        resp.content = content
        return resp
    return _make


@pytest.mark.asyncio
async def test_happy_path_returns_ranked_entries(personalizer, mock_router_response):
    pack = _pack(entry_ids=["a", "b", "c", "d"])
    payload = json.dumps({
        "intro": "Test intro.",
        "ranked": [
            {"id": "a", "relevance_note": "Note A"},
            {"id": "b", "relevance_note": "Note B"},
        ],
    })
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(return_value=mock_router_response(payload))
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[],
            detected_libraries=[], complexity_score=0,
            complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert result.quality == "curated"
    assert len(result.ranked) == 2
    assert result.ranked[0].id == "a"
    assert result.intro == "Test intro."


@pytest.mark.asyncio
async def test_retry_on_bad_json(personalizer, mock_router_response):
    pack = _pack(entry_ids=["a", "b", "c"])
    bad = mock_router_response("NOT JSON")
    good = mock_router_response(json.dumps({
        "intro": "Recovered.",
        "ranked": [{"id": "a", "relevance_note": "n"}],
    }))
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(side_effect=[bad, good])
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[],
            detected_libraries=[], complexity_score=0,
            complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert result.quality == "curated"
    assert result.intro == "Recovered."


@pytest.mark.asyncio
async def test_fallback_on_all_failures(personalizer, mock_router_response):
    pack = _pack(entry_ids=["a", "b", "c"])
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(return_value=mock_router_response("NOT JSON"))
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[],
            detected_libraries=[], complexity_score=0,
            complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert result.quality == "curated_unpersonalized"
    assert result.intro == ""
    # Falls back to pre-filter order (first 7 entries from packs)
    assert [r.id for r in result.ranked] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_hallucinated_ids_are_dropped(personalizer, mock_router_response):
    pack = _pack(entry_ids=["a", "b", "c"])
    payload = json.dumps({
        "intro": "intro",
        "ranked": [
            {"id": "a", "relevance_note": "real"},
            {"id": "made-up-id", "relevance_note": "hallucinated"},
            {"id": "b", "relevance_note": "real"},
        ],
    })
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(return_value=mock_router_response(payload))
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[],
            detected_libraries=[], complexity_score=0,
            complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert [r.id for r in result.ranked] == ["a", "b"]


@pytest.mark.asyncio
async def test_pre_filter_drops_async_tag_when_no_async_in_code(personalizer):
    pack = _pack(entry_ids=["sync_entry"])
    pack.entries.append(_entry("async_entry", tags=["async"]))
    # No async in code blocks
    candidates = personalizer._build_candidates(
        packs=[pack], code_context_blocks=["x = 1\nprint(x)"],
        detected_libraries=[], intent="",
    )
    candidate_ids = {c["id"] for c in candidates}
    assert "sync_entry" in candidate_ids
    assert "async_entry" not in candidate_ids


@pytest.mark.asyncio
async def test_pre_filter_keeps_async_tag_when_async_in_code(personalizer):
    pack = _pack(entry_ids=["sync_entry"])
    pack.entries.append(_entry("async_entry", tags=["async"]))
    candidates = personalizer._build_candidates(
        packs=[pack], code_context_blocks=["async def foo():\n    await bar()"],
        detected_libraries=[], intent="",
    )
    candidate_ids = {c["id"] for c in candidates}
    assert "async_entry" in candidate_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet_personalizer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement personalizer.py**

```python
# src/agents/cheatsheet/personalizer.py
"""Single LLM call that ranks pack entries and writes relevance notes.

NEVER invents code. Layer 2 of the three-layer architecture.
"""

import json
import logging
import re
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError

from src.agents.cheatsheet.pack_models import Pack
from src.core.model_router import model_router

logger = logging.getLogger(__name__)


class RankedEntry(BaseModel):
    id: str
    relevance_note: str = Field(default="", max_length=200)


class PersonalizationOutput(BaseModel):
    intro: str = Field(default="", max_length=400)
    ranked: List[RankedEntry] = Field(min_length=1, max_length=7)
    quality: str = "curated"  # "curated" | "curated_unpersonalized"


SYSTEM_PROMPT = """You are a cheat-sheet curator. You are NOT a code writer.

Given a list of pre-written cheat-sheet entries, your job is to:
1. Pick at most 7 entries that best match the user's intent and code context.
2. For each picked entry, write ONE short sentence (<=25 words) explaining how it relates to what the user is doing right now. This is the `relevance_note`.
3. Write a 1-2 sentence intro paragraph that frames the cheat sheet around the user's activity.

You MUST NOT:
- Invent new entries or new ids
- Rewrite code examples or modify titles
- Output anything outside the JSON object

You MUST return entries by their `id` exactly as given in candidate_entries.

Output STRICT JSON only, matching this schema:
{
  "intro": "<1-2 sentences>",
  "ranked": [
    {"id": "<exact id from candidates>", "relevance_note": "<short>"},
    ...
  ]
}"""

_ASYNC_RE = re.compile(r"\b(async\s+def|await\s+|asyncio\.|\.create_task|\.gather)")


class Personalizer:
    """Layer 2: LLM personalization with retry + deterministic fallback."""

    MAX_CANDIDATES = 20

    def _build_candidates(
        self,
        packs: List[Pack],
        code_context_blocks: List[str],
        detected_libraries: List[str],
        intent: str,
    ) -> List[dict]:
        """Deterministic pre-filter. Returns candidate dicts in stable order."""
        code_blob = "\n".join(code_context_blocks)
        has_async = bool(_ASYNC_RE.search(code_blob))
        intent_lower = intent.lower()

        candidates: list[dict] = []
        for pack in packs:
            is_library_pack = pack.pack.library is not None
            for entry in pack.entries:
                # Tag exclusion: drop async-tagged entries if no async in code
                if not has_async and "async" in entry.tags:
                    continue
                # Library gating: library entries require detection or intent mention
                if is_library_pack:
                    lib = pack.pack.library
                    if lib not in detected_libraries and lib.lower() not in intent_lower:
                        continue
                # Score: library_pack weight + tag overlap with intent
                tag_overlap = sum(1 for t in entry.tags if t.lower() in intent_lower)
                score = (3 if is_library_pack else 1) + tag_overlap
                candidates.append({
                    "id": entry.id,
                    "title": entry.title,
                    "when_to_use": entry.when_to_use,
                    "tags": entry.tags,
                    "_score": score,
                })

        # Stable sort: score desc, then original order
        candidates.sort(key=lambda c: -c["_score"])
        candidates = candidates[: self.MAX_CANDIDATES]
        # Strip _score before sending to LLM
        for c in candidates:
            c.pop("_score", None)
        return candidates

    def _summarize_code(self, blocks: List[str]) -> List[str]:
        """Return up to 3 short snippets, each <=200 chars."""
        snippets: list[str] = []
        for b in blocks:
            stripped = b.strip()
            if not stripped:
                continue
            snippets.append(stripped[:200])
            if len(snippets) >= 3:
                break
        return snippets

    def _parse_output(
        self, content: str, candidate_ids: set[str]
    ) -> Optional[PersonalizationOutput]:
        """Extract JSON, validate, drop hallucinated ids. Returns None on failure."""
        # Strip markdown fences if the LLM wrapped its output
        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith(("json\n", "yaml\n")):
                    content = content.split("\n", 1)[1]
        try:
            raw = json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Personalizer JSON parse failed: {e}")
            return None
        try:
            # Drop hallucinated ids BEFORE pydantic validates min_length=1
            ranked_raw = raw.get("ranked", [])
            filtered = [r for r in ranked_raw if r.get("id") in candidate_ids]
            if not filtered:
                logger.warning("Personalizer returned 0 valid ids")
                return None
            raw["ranked"] = filtered
            return PersonalizationOutput(**raw)
        except ValidationError as e:
            logger.warning(f"Personalizer schema validation failed: {e}")
            return None

    def _fallback(self, candidates: List[dict]) -> PersonalizationOutput:
        ranked = [
            RankedEntry(id=c["id"], relevance_note="")
            for c in candidates[:7]
        ]
        return PersonalizationOutput(
            intro="", ranked=ranked, quality="curated_unpersonalized"
        )

    async def personalize(
        self,
        packs: List[Pack],
        code_context_blocks: List[str],
        detected_libraries: List[str],
        complexity_score: int,
        complexity_suggested_level: str,
        requested_language: str,
        requested_skill: str,
        intent: str,
        tenant_id: str,
        integration_name: str,
        user_id: Optional[str],
    ) -> PersonalizationOutput:
        candidates = self._build_candidates(
            packs, code_context_blocks, detected_libraries, intent
        )
        if not candidates:
            return PersonalizationOutput(
                intro="", ranked=[RankedEntry(id="__none__")],
                quality="curated_unpersonalized",
            )

        candidate_ids = {c["id"] for c in candidates}
        payload = {
            "user_intent": intent,
            "code_context_summary": {
                "detected_libraries": detected_libraries,
                "complexity_score": complexity_score,
                "complexity_suggested_level": complexity_suggested_level,
                "key_snippets": self._summarize_code(code_context_blocks),
            },
            "requested": {
                "language": requested_language,
                "skill_level": requested_skill,
            },
            "candidate_entries": candidates,
        }

        last_content = ""
        for attempt in range(2):  # 1 initial + 1 retry
            try:
                user_msg = json.dumps(payload, ensure_ascii=False)
                if attempt > 0:
                    user_msg = (
                        f"Your previous output was invalid JSON: {last_content[:200]}. "
                        f"Return valid JSON only matching the schema.\n\n" + user_msg
                    )
                response = await model_router.invoke_with_usage(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    task_type="cheatsheet_personalization",
                    tenant_id=tenant_id,
                    integration_name=integration_name,
                    user_id=user_id,
                    temperature=0,
                )
                content = response.content if hasattr(response, "content") else str(response)
                last_content = content
                parsed = self._parse_output(content, candidate_ids)
                if parsed is not None:
                    return parsed
            except Exception as e:
                logger.warning(f"Personalizer attempt {attempt + 1} raised: {e}")
                continue

        logger.warning("Personalizer exhausted retries; using deterministic fallback")
        return self._fallback(candidates)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cheatsheet_personalizer.py -v`
Expected: 6 PASSED

---

## Task 9: Markdown renderer (pure function, no LLM)

**Files:**
- Create: `src/agents/cheatsheet/markdown_renderer.py`
- Test: `tests/test_cheatsheet_renderer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cheatsheet_renderer.py
from datetime import date
from src.agents.cheatsheet.pack_models import Pack, PackMeta, Entry, Example
from src.agents.cheatsheet.personalizer import PersonalizationOutput, RankedEntry
from src.agents.cheatsheet.markdown_renderer import render_markdown


def _make_pack():
    meta = PackMeta(
        language="python", skill_level="intermediate", version=1,
        last_reviewed=date(2026, 5, 15), reviewer="test",
    )
    entries = [
        Entry(
            id="py.x", title="X Title", explanation="X explanation.",
            tags=[], when_to_use="",
            examples=[Example(title="X ex", language="python", code="x = 1")],
            pitfalls=["X pitfall"],
        ),
        Entry(
            id="py.y", title="Y Title", explanation="Y explanation.",
            tags=[], when_to_use="",
            examples=[Example(title="Y ex", language="rust", code="fn main() {}")],
            pitfalls=["Y pitfall"],
        ),
    ]
    return Pack(pack=meta, entries=entries)


def test_header_uses_requested_language_and_skill():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="Some intro.",
        ranked=[RankedEntry(id="py.x", relevance_note="note")],
    )
    md = render_markdown(
        requested_language="python", requested_skill="intermediate",
        packs=[pack], personalization=output,
    )
    assert md.startswith("# Python Cheat Sheet - Intermediate")


def test_intro_is_included_when_present():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="Custom intro paragraph.",
        ranked=[RankedEntry(id="py.x", relevance_note="")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "Custom intro paragraph." in md


def test_intro_omitted_when_empty():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="", ranked=[RankedEntry(id="py.x", relevance_note="")],
        quality="curated_unpersonalized",
    )
    md = render_markdown("python", "intermediate", [pack], output)
    # No empty intro paragraph
    assert "\n\n_\n\n" not in md


def test_fence_tag_tracks_entry_language_not_request():
    """If the request was 'python' but an entry's example is in Rust,
    the fence MUST say ```rust, not ```python."""
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[RankedEntry(id="py.y", relevance_note="")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "```rust" in md
    assert "```python" not in md  # entry y has no python examples


def test_ranking_order_is_respected():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[
            RankedEntry(id="py.y", relevance_note=""),
            RankedEntry(id="py.x", relevance_note=""),
        ],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert md.find("Y Title") < md.find("X Title")


def test_unknown_ranked_id_is_skipped():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[
            RankedEntry(id="py.x", relevance_note=""),
            RankedEntry(id="does.not.exist", relevance_note=""),
        ],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "X Title" in md
    assert "does.not.exist" not in md


def test_relevance_note_appears_inline():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[RankedEntry(id="py.x", relevance_note="Matches your code.")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "Matches your code." in md


def test_pitfalls_section_rendered():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="", ranked=[RankedEntry(id="py.x", relevance_note="")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "X pitfall" in md
    assert "Common Pitfalls" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet_renderer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement markdown_renderer.py**

```python
# src/agents/cheatsheet/markdown_renderer.py
"""Layer 3: deterministic markdown render. No LLM."""

from typing import List

from src.agents.cheatsheet.pack_models import Pack, Entry
from src.agents.cheatsheet.personalizer import PersonalizationOutput


def _lookup_entry(packs: List[Pack], entry_id: str) -> Entry | None:
    for pack in packs:
        for entry in pack.entries:
            if entry.id == entry_id:
                return entry
    return None


def render_markdown(
    requested_language: str,
    requested_skill: str,
    packs: List[Pack],
    personalization: PersonalizationOutput,
) -> str:
    lines: list[str] = [
        f"# {requested_language.title()} Cheat Sheet - {requested_skill.title()}"
    ]

    if personalization.intro:
        lines.append("")
        lines.append(f"_{personalization.intro}_")

    section_no = 0
    for ranked in personalization.ranked:
        entry = _lookup_entry(packs, ranked.id)
        if entry is None:
            continue
        section_no += 1
        lines.append("")
        lines.append(f"## {section_no}. {entry.title}")
        if ranked.relevance_note:
            lines.append("")
            lines.append(f"> {ranked.relevance_note}")
        lines.append("")
        lines.append(entry.explanation)

        for ex in entry.examples:
            lines.append("")
            lines.append(f"### {ex.title}")
            lines.append("")
            lines.append(f"```{ex.language}")
            lines.append(ex.code.rstrip())
            lines.append("```")

        if entry.pitfalls:
            lines.append("")
            lines.append("### Common Pitfalls")
            for p in entry.pitfalls:
                lines.append(f"- {p}")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cheatsheet_renderer.py -v`
Expected: 8 PASSED

---

## Task 10: Rewrite agent.py as orchestrator

**Files:**
- Modify: `src/agents/cheatsheet/agent.py`
- Test: `tests/test_cheatsheet.py` (rewrite)

- [ ] **Step 1: Replace tests/test_cheatsheet.py**

```python
# tests/test_cheatsheet.py
import pytest
from src.agents.cheatsheet.agent import generate_cheatsheet_invoke


@pytest.mark.asyncio
async def test_python_beginner_explicit_language_returns_curated():
    """End-to-end with seed pack; LLM may or may not succeed.
    The response must be curated (with seed pack present) and markdown must include header."""
    result = await generate_cheatsheet_invoke(
        {"language": "python", "skill_level": "beginner",
         "intent": "learning python basics"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is True
    data = result["data"]
    assert data["language"] == "python"
    assert data["skill_level"] == "beginner"
    assert data["quality"] in ("curated", "curated_unpersonalized")
    assert data["markdown"].startswith("# Python Cheat Sheet - Beginner")


@pytest.mark.asyncio
async def test_unsupported_language_returns_failure():
    result = await generate_cheatsheet_invoke(
        {"language": "cobol", "skill_level": "beginner"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is False
    assert "cobol" in result["data"]["message"].lower() or "not supported" in result["data"]["message"].lower()


@pytest.mark.asyncio
async def test_no_inputs_returns_failure():
    result = await generate_cheatsheet_invoke(
        {}, tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is False
    assert "language" in result["data"]["message"].lower() or "intent" in result["data"]["message"].lower()


@pytest.mark.asyncio
async def test_auto_detect_language_from_code_context():
    result = await generate_cheatsheet_invoke(
        {"code_context": "def hello():\n    print('hi')\n",
         "skill_level": "beginner"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is True
    assert result["data"]["language"] == "python"


@pytest.mark.asyncio
async def test_intent_only_request_with_language():
    result = await generate_cheatsheet_invoke(
        {"language": "python", "intent": "refactoring to typed code"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cheatsheet.py -v`
Expected: FAIL — old `agent.py` still imports deleted-soon modules / new API not implemented

- [ ] **Step 3: Replace src/agents/cheatsheet/agent.py**

```python
# src/agents/cheatsheet/agent.py
"""Cheatsheet agent v0.11 — Curated Packs + LLM Personalization.

Three-layer pipeline:
  1. Pack loader (deterministic ground truth from data/cheatsheet_packs/)
  2. Personalizer (single LLM call: ranks + writes relevance notes)
  3. Markdown renderer (pure-function assembly)
"""

import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.agents.cheatsheet.context_parser import parse_code_context
from src.agents.cheatsheet.library_detector import detect_libraries, LIBRARY_SIGNATURES
from src.agents.cheatsheet.complexity_scorer import calculate_complexity
from src.agents.cheatsheet.language_detector import detect_language
from src.agents.cheatsheet.pack_loader import (
    PackLoader, SUPPORTED_LANGUAGES, PackNotFoundError,
)
from src.agents.cheatsheet.personalizer import Personalizer
from src.agents.cheatsheet.markdown_renderer import render_markdown
from src.agents.cheatsheet.request_model import CheatsheetRequest

logger = logging.getLogger(__name__)

_PACK_ROOT = Path(__file__).resolve().parents[3] / "data" / "cheatsheet_packs"
_loader = PackLoader(root=_PACK_ROOT)
_personalizer = Personalizer()


def _failure(message: str) -> dict:
    return {"success": False, "data": {"message": message}, "format": "markdown"}


async def generate_cheatsheet_invoke(
    args: dict,
    tenant_id: str = "unknown",
    integration_name: str = "unknown",
    user_id: Optional[str] = None,
) -> dict:
    """MCP gateway entry point."""
    # 1. Validate request
    try:
        req = CheatsheetRequest(**args)
    except ValidationError as e:
        first = e.errors()[0]
        return _failure(first.get("msg", "Invalid request."))

    # 2. Parse code context + run deterministic analysis
    parsed = parse_code_context(req.code_context or "")
    blocks = parsed.get("blocks", [])
    detected_libraries = detect_libraries(blocks) if blocks else []
    complexity = calculate_complexity(blocks) if blocks else {
        "score": 0, "suggested_level": "beginner", "features": {}
    }

    # 3. Resolve language (explicit wins, else auto-detect from code)
    language = req.language
    if not language and blocks:
        language = detect_language(blocks[0])
    if not language:
        return _failure(
            "Could not detect language from code_context. "
            "Pass an explicit 'language' or 'intent'."
        )
    if language not in SUPPORTED_LANGUAGES:
        return _failure(
            f"Language {language!r} is not supported. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES)}."
        )

    # 4. Load packs
    try:
        lang_pack = _loader.load_language_pack(language, req.skill_level)
    except PackNotFoundError as e:
        logger.error(f"Pack data missing: {e}")
        return _failure(f"Internal: pack data missing for {language}/{req.skill_level}.")

    packs = [lang_pack]
    packs_used = [{
        "kind": "language",
        "id": f"{language}/{req.skill_level}",
        "version": lang_pack.pack.version,
        "last_reviewed": lang_pack.pack.last_reviewed.isoformat(),
    }]
    for lib in detected_libraries:
        lib_pack = _loader.load_library_pack(lib, req.skill_level)
        if lib_pack is not None:
            packs.append(lib_pack)
            packs_used.append({
                "kind": "library",
                "id": f"{lib}/{req.skill_level}",
                "version": lib_pack.pack.version,
                "last_reviewed": lib_pack.pack.last_reviewed.isoformat(),
            })

    # 5. Personalize (single LLM call)
    personalization = await _personalizer.personalize(
        packs=packs,
        code_context_blocks=blocks,
        detected_libraries=detected_libraries,
        complexity_score=complexity["score"],
        complexity_suggested_level=complexity["suggested_level"],
        requested_language=language,
        requested_skill=req.skill_level,
        intent=req.intent or "",
        tenant_id=tenant_id,
        integration_name=integration_name,
        user_id=user_id,
    )

    # 6. Render
    markdown = render_markdown(language, req.skill_level, packs, personalization)

    # 7. Build response (additive new fields, keeps legacy keys)
    ranked_entries = []
    for ranked in personalization.ranked:
        entry = None
        source_pack = None
        for pack in packs:
            for e in pack.entries:
                if e.id == ranked.id:
                    entry = e
                    source_pack = (
                        f"libraries/{pack.pack.library}/{pack.pack.skill_level}"
                        if pack.pack.library
                        else f"languages/{pack.pack.language}/{pack.pack.skill_level}"
                    )
                    break
            if entry:
                break
        if entry is None:
            continue
        ranked_entries.append({
            "id": ranked.id,
            "title": entry.title,
            "relevance_note": ranked.relevance_note,
            "source_pack": source_pack,
        })

    # 8. Fire dashboard analytics (best-effort, do not fail request)
    try:
        from src.workers.tasks.usage_tasks import log_request_call
        log_request_call.delay(
            user_id=user_id,
            tenant_id=tenant_id,
            integration_name=integration_name,
            tool_name="generate_cheatsheet",
            success=True,
            duration_ms=0,
        )
    except Exception as e:
        logger.debug(f"Analytics log skipped: {e}")

    return {
        "success": True,
        "data": {
            "language": language,
            "skill_level": req.skill_level,
            "complexity_score": complexity["score"],
            "complexity_suggested_level": complexity["suggested_level"],
            "detected_libraries": detected_libraries,
            "packs_used": packs_used,
            "ranked_entries": ranked_entries,
            "intro": personalization.intro,
            "quality": personalization.quality,
            "markdown": markdown,
        },
        "format": "markdown",
    }
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_cheatsheet.py -v -k "unsupported or no_inputs"`
Expected: PASS for these — they don't need LLM.

(End-to-end tests that hit LLM may or may not pass depending on Ollama availability. That's expected; they're nightly-only conceptually.)

---

## Task 11: Delete legacy files

- [ ] **Step 1: Delete dead modules**

Run:
```bash
rm /Users/siddesh.kale/Documents/DevForge/DevForge_Backend/src/agents/cheatsheet/enhanced_templates.py
rm /Users/siddesh.kale/Documents/DevForge/DevForge_Backend/src/agents/cheatsheet/section_selector.py
rm /Users/siddesh.kale/Documents/DevForge/DevForge_Backend/src/agents/cheatsheet/quick_reference.py
rm /Users/siddesh.kale/Documents/DevForge/DevForge_Backend/src/tools/cheatsheet/tools.py
rmdir /Users/siddesh.kale/Documents/DevForge/DevForge_Backend/src/tools/cheatsheet 2>/dev/null || true
```

- [ ] **Step 2: Verify nothing imports the deleted modules**

Run:
```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
grep -rn "from src.agents.cheatsheet.enhanced_templates\|from src.agents.cheatsheet.section_selector\|from src.agents.cheatsheet.quick_reference\|from src.tools.cheatsheet" src/ tests/ 2>&1
```
Expected: no output (no remaining imports)

---

## Task 12: Update MCP tool description + JSON-schema + manifest

**Files:**
- Modify: `src/api/routers/__init__.py`
- Modify: `manifests/devforge.json`

- [ ] **Step 1: Update `TOOL_DESCRIPTIONS["generate_cheatsheet"]`**

In `src/api/routers/__init__.py` around line 135, replace with:

```python
    "generate_cheatsheet": (
        "Generates an activity-aware programming cheat sheet from curated, "
        "human-reviewed knowledge packs (one LLM call for personalization). "

        "SUPPORTED LANGUAGES: python, javascript, typescript, go, rust, java, "
        "ruby, php, csharp. Unsupported languages return success:false with a "
        "clear message - DO NOT retry with a different value, ask the user. "

        "INPUTS you should provide: "
        "  - language (one of the above, or omit to auto-detect from code_context) "
        "  - skill_level (beginner|intermediate|expert; default beginner) "
        "  - code_context (paste the user's actual code if available - enables "
        "    library detection and activity-aware ranking) "
        "  - intent (1-line description of what the user is trying to do, e.g. "
        "    'debugging async deadlock' - strongly improves relevance when code "
        "    is unavailable or short). "

        "OUTPUTS: data.markdown (rendered sheet), data.ranked_entries (structured), "
        "data.packs_used (provenance for citing), data.quality ('curated' = LLM-"
        "personalized; 'curated_unpersonalized' = deterministic fallback fired "
        "because LLM returned bad JSON - content is still trustworthy but not "
        "tailored). "

        "LATENCY: 5-15s warm-cache, 20-30s cold-cache. Suggest a loading indicator."
    ),
```

- [ ] **Step 2: Update `_get_tool_schema["generate_cheatsheet"]` to add `intent`**

In the same file around line 1553, in the `generate_cheatsheet` schema block, add the `intent` property:

```python
        "generate_cheatsheet": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": [
                        "python", "javascript", "typescript", "go", "rust",
                        "java", "ruby", "php", "csharp",
                    ],
                    "description": (
                        "Programming language. One of the supported 9 ecosystems. "
                        "Omit to auto-detect from code_context."
                    ),
                },
                "skill_level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "expert"],
                    "description": "User skill level (default: beginner)",
                },
                "code_context": {
                    "type": "string",
                    "description": (
                        "Code snippet for context-aware cheatsheet generation. "
                        "Enables library detection and activity-driven ranking."
                    ),
                },
                "intent": {
                    "type": "string",
                    "description": (
                        "Short description of what the user is trying to do "
                        "(e.g., 'debugging async deadlock', 'refactoring to typed "
                        "dataclasses'). Strongly improves relevance, especially "
                        "when code_context is short or unavailable."
                    ),
                },
            },
            "required": [],
        },
```

- [ ] **Step 3: Bump version in manifests/devforge.json**

Change `"version": "0.10.0"` to `"version": "0.11.0"` (top-level manifest version).

For the cheatsheet tool block in manifest, update the `description` to the same agent-instructive string above (first ~3 sentences fit; full prose is in `TOOL_DESCRIPTIONS`).

- [ ] **Step 4: Verify routers module imports cleanly**

Run: `cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend && python -c "from src.api.routers import router; print('OK')"`
Expected: `OK`

---

## Task 13: Update docs

**Files:**
- Modify: `DevForge_Backend/docs/tools/generate_cheatsheet.md` (rewrite)
- Modify: `DevForge_Backend/CLAUDE.md` ("Current tool versions" table)

- [ ] **Step 1: Rewrite generate_cheatsheet.md**

Rewrite the doc to match v0.11. Keep the existing structure (Overview, Features, Folder Structure, Parameters, Pipeline, Code Location, Testing, Performance, Changelog) but reflect:

- v0.11.0 status
- 9 supported languages (not 1)
- 14 libraries
- New `intent` parameter
- Three-layer architecture
- Pack-based ground truth
- New response fields: `complexity_suggested_level`, `packs_used`, `ranked_entries`, `intro`, `quality`
- Latency: 5-15s warm / 20-30s cold (not <500ms)
- Test count: ~30 deterministic + 2 LLM-gated
- Folder Structure includes `data/cheatsheet_packs/`
- Changelog entry v0.11.0
- Last Updated: 2026-05-15

The Write call replaces the entire file. Reference [spec section](../../../docs/superpowers/specs/2026-05-15-generate-cheatsheet-production-grade-design.md) for canonical content.

- [ ] **Step 2: Update CLAUDE.md "Current tool versions" table**

In `DevForge_Backend/CLAUDE.md`, change the `generate_cheatsheet` row:

```markdown
| `generate_cheatsheet` | 0.11.0 | 0.11.0 | Curated packs + LLM personalization (9 langs) |
```

Also bump the `Manifest version` for `generate_data` to 0.11.0 if/when the top-level manifest version is shared (the manifest is one number for the whole MCP server).

---

## Self-review (executed during plan writing)

- **Spec coverage:** Three-layer architecture (Tasks 3, 8, 9), pack schema (Task 1), bootstrap (Task 5), CI gate (Task 4), language detector (Task 6), request model (Task 7), agent rewrite (Task 10), deletion (Task 11), MCP description (Task 12), docs (Task 13). All spec sections covered.
- **Placeholder scan:** No TBDs, no "add appropriate handling" — code shown in every step. Bootstrap actual content ships through Task 2 (seed pack) + user-run script (Task 5).
- **Type consistency:** `PersonalizationOutput.ranked: list[RankedEntry]` consistent across Tasks 8, 9, 10. `Pack`/`Entry`/`Example` consistent across Tasks 1, 3, 8, 9, 10. `SUPPORTED_LANGUAGES` tuple used identically in Tasks 3, 5, 6, 10, 12.

---

## Execution handoff

Plan complete. Two execution options:

1. **Subagent-driven (recommended for plan size)** — dispatch fresh subagent per task, review between tasks.
2. **Inline execution** — execute tasks in this session with batched checkpoints.

User has already directed: "**dont commit anything** — after all changes are made — i will manually review and commit". Both modes honor that; no `git commit` step appears in any task.
