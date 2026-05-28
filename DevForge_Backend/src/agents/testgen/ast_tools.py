"""Tree-sitter helpers for generate_tests.

Two jobs:
  1. parse_ok        — does generated test source parse with no ERROR nodes?
  2. symbol guard    — which names does the test import from the module under
                       test, and which symbols does the source actually define?

Uses the same `tree_sitter_languages.get_parser` wrapper as
src/agents/rag/chunking/code_chunker.py. Supports python, javascript, typescript.
All functions are defensive: a parser failure degrades to a safe empty/False
result rather than raising into the request path.
"""

from __future__ import annotations

import logging
import re
from typing import Iterator

logger = logging.getLogger(__name__)

_PARSERS: dict = {}
_INVISIBLE = ("​", "‌", "‍")
_JS_LANGS = ("javascript", "typescript")


def _get_parser(language: str):
    if language not in _PARSERS:
        from tree_sitter_languages import get_parser

        _PARSERS[language] = get_parser(language)
    return _PARSERS[language]


def _normalize(code: str) -> str:
    code = code.lstrip("﻿")
    for ch in _INVISIBLE:
        code = code.replace(ch, "")
    return code


def _parse(code: str, language: str):
    parser = _get_parser(language)
    return parser.parse(bytes(_normalize(code), "utf8"))


def _node_text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf8", errors="replace")


def _iter(node) -> Iterator:
    """DFS over a node and all its named descendants (node yielded first)."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for i in range(n.named_child_count):
            stack.append(n.named_child(i))


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "'\"`" and s[-1] == s[0]:
        return s[1:-1]
    return s


def _short(s: str, limit: int = 100) -> str:
    return re.sub(r"\s+", " ", s).strip()[:limit]


def _first_match_line(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return _short(line)
    return ""


def _same_node(a, b) -> bool:
    return a.start_byte == b.start_byte and a.end_byte == b.end_byte


# --------------------------------------------------------------------------- #
# Parse check
# --------------------------------------------------------------------------- #


def parse_ok(code: str, language: str) -> bool:
    """True if the source parses with no ERROR / missing nodes."""
    try:
        root = _parse(code, language).root_node
    except Exception as e:  # parser unavailable or crashed
        logger.warning(f"parse_ok: parser raised for {language}: {e}")
        return False
    try:
        return not root.has_error
    except AttributeError:
        return not _scan_error(root)


def _scan_error(node) -> bool:
    if node.type == "ERROR" or getattr(node, "is_missing", False):
        return True
    for i in range(node.child_count):
        if _scan_error(node.child(i)):
            return True
    return False


# --------------------------------------------------------------------------- #
# Defined symbols (the importable public surface of the source under test)
# --------------------------------------------------------------------------- #


def extract_defined_symbols(code: str, language: str) -> set[str]:
    """Top-level names a test could import from this source.

    Intentionally over-collects (e.g. all top-level consts) — over-collecting
    is safe for the guard (fewer false hallucination flags); under-collecting
    would wrongly flag real symbols.
    """
    try:
        tree = _parse(code, language)
    except Exception as e:
        logger.warning(f"extract_defined_symbols: parse failed for {language}: {e}")
        return set()
    src = bytes(_normalize(code), "utf8")
    root = tree.root_node
    if language == "python":
        return _py_defined(root, src)
    if language in _JS_LANGS:
        return _js_defined(root, src)
    return set()


def _add_name(node, src: bytes, names: set[str]) -> None:
    nn = node.child_by_field_name("name")
    if nn is not None:
        names.add(_node_text(nn, src))


def _py_defined(root, src: bytes) -> set[str]:
    names: set[str] = set()
    for i in range(root.named_child_count):
        child = root.named_child(i)
        t = child.type
        if t in ("function_definition", "class_definition"):
            _add_name(child, src, names)
        elif t == "decorated_definition":
            for j in range(child.named_child_count):
                inner = child.named_child(j)
                if inner.type in ("function_definition", "class_definition"):
                    _add_name(inner, src, names)
    return names


_JS_DECL_TYPES = (
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "abstract_class_declaration",
    "interface_declaration",
    "enum_declaration",
    "type_alias_declaration",
)


def _js_defined(root, src: bytes) -> set[str]:
    names: set[str] = set()

    def handle(node) -> None:
        t = node.type
        if t in _JS_DECL_TYPES:
            _add_name(node, src, names)
        elif t in ("lexical_declaration", "variable_declaration"):
            for j in range(node.named_child_count):
                d = node.named_child(j)
                if d.type == "variable_declarator":
                    nn = d.child_by_field_name("name")
                    if nn is not None and nn.type == "identifier":
                        names.add(_node_text(nn, src))
        elif t == "export_statement":
            for j in range(node.named_child_count):
                handle(node.named_child(j))

    for i in range(root.named_child_count):
        handle(root.named_child(i))
    return names


# --------------------------------------------------------------------------- #
# Module imports (names the generated test pulls from the module under test)
# --------------------------------------------------------------------------- #


def extract_module_imports(test_code: str, language: str, module_name: str) -> set[str]:
    """Names imported from `module_name` in the generated test."""
    try:
        tree = _parse(test_code, language)
    except Exception as e:
        logger.warning(f"extract_module_imports: parse failed for {language}: {e}")
        return set()
    src = bytes(_normalize(test_code), "utf8")
    root = tree.root_node
    if language == "python":
        return _py_module_imports(root, src, module_name)
    if language in _JS_LANGS:
        return _js_module_imports(root, src, module_name)
    return set()


def _py_module_imports(root, src: bytes, module_name: str) -> set[str]:
    found: set[str] = set()
    for node in _iter(root):
        if node.type != "import_from_statement":
            continue
        mod_node = node.child_by_field_name("module_name")
        if mod_node is None or _node_text(mod_node, src) != module_name:
            continue
        for j in range(node.named_child_count):
            c = node.named_child(j)
            if _same_node(c, mod_node):
                continue
            if c.type == "dotted_name":
                found.add(_node_text(c, src))
            elif c.type == "aliased_import":
                orig = c.child_by_field_name("name")
                if orig is not None:
                    found.add(_node_text(orig, src))
            elif c.type == "identifier":
                found.add(_node_text(c, src))
    return found


def _js_module_imports(root, src: bytes, module_name: str) -> set[str]:
    found: set[str] = set()
    for node in _iter(root):
        if node.type != "import_statement":
            continue
        source_node = node.child_by_field_name("source")
        if source_node is None or _strip_quotes(_node_text(source_node, src)) != module_name:
            continue
        for c in _iter(node):
            if c.type == "import_specifier":
                nn = c.child_by_field_name("name")
                if nn is not None:
                    found.add(_node_text(nn, src))
            elif c.type == "identifier" and c.parent is not None and c.parent.type == "import_clause":
                found.add(_node_text(c, src))
    return found


# --------------------------------------------------------------------------- #
# Test-case extraction (for the response's cases[] report)
# --------------------------------------------------------------------------- #


def extract_test_cases(test_code: str, language: str) -> list[dict]:
    """List of {name, asserts} describing each test in the generated file."""
    try:
        tree = _parse(test_code, language)
    except Exception as e:
        logger.warning(f"extract_test_cases: parse failed for {language}: {e}")
        return []
    src = bytes(_normalize(test_code), "utf8")
    root = tree.root_node
    if language == "python":
        return _py_cases(root, src)
    if language in _JS_LANGS:
        return _js_cases(root, src)
    return []


def _py_cases(root, src: bytes) -> list[dict]:
    cases: list[dict] = []

    def collect(node) -> None:
        for i in range(node.named_child_count):
            child = node.named_child(i)
            t = child.type
            if t == "function_definition":
                nn = child.child_by_field_name("name")
                name = _node_text(nn, src) if nn is not None else ""
                if name.startswith("test"):
                    cases.append(
                        {"name": name, "asserts": _first_match_line(_node_text(child, src), "assert")}
                    )
            elif t == "class_definition":
                body = child.child_by_field_name("body")
                if body is not None:
                    collect(body)
            elif t == "decorated_definition":
                collect(child)

    collect(root)
    return cases


_JS_TEST_FNS = {"test", "it", "test.only", "it.only", "test.skip", "it.skip"}


def _js_cases(root, src: bytes) -> list[dict]:
    cases: list[dict] = []
    for node in _iter(root):
        if node.type != "call_expression":
            continue
        fn = node.child_by_field_name("function")
        if fn is None or _node_text(fn, src) not in _JS_TEST_FNS:
            continue
        args = node.child_by_field_name("arguments")
        name = ""
        if args is not None:
            for j in range(args.named_child_count):
                a = args.named_child(j)
                if a.type in ("string", "template_string"):
                    name = _strip_quotes(_node_text(a, src))
                    break
        if name:
            cases.append({"name": name, "asserts": _first_match_line(_node_text(node, src), "expect(")})
    return cases
