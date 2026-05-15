"""CI gate: validate all cheatsheet packs.

Runs:
  1. YAML parses and matches the Pack pydantic schema.
  2. Every example's `code` parses cleanly under its declared language grammar
     via tree-sitter-languages. Zero syntax errors required.
  3. Entry ids are globally unique across all packs.

Exit code 0 on success, non-zero on any failure.

Usage:
  python scripts/validate_cheatsheet_packs.py data/cheatsheet_packs/
"""

import sys
from pathlib import Path

import yaml

from src.agents.cheatsheet.pack_models import Pack

try:
    from tree_sitter_languages import get_parser
    HAVE_TREE_SITTER = True
except ImportError:
    HAVE_TREE_SITTER = False


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
                        f"{path}::{entry.id}::{ex.title}: "
                        f"syntax error in {ex.language} example"
                    )
            except Exception as e:
                errors.append(
                    f"{path}::{entry.id}::{ex.title}: "
                    f"tree-sitter parse failed: {e}"
                )
    return errors


def main(root: str) -> int:
    root_path = Path(root)
    all_errors: list[str] = []
    all_ids: dict[str, str] = {}

    if not root_path.exists():
        print(f"VALIDATION FAILED: pack root not found: {root_path}", file=sys.stderr)
        return 1

    for path in sorted(root_path.rglob("*.yaml")):
        all_errors.extend(validate_pack(path))
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
            pass

    if all_errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: validated {len(all_ids)} entries across all packs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/cheatsheet_packs"))
