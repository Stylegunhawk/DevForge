"""Heuristic language detection for cheat-sheet code context.

Returns Optional[str] — None on failure (no silent python fallback).
Uses regex heuristics for speed. The pack validator uses tree-sitter
where false positives are unacceptable.
"""

import re
from typing import Optional

_SIGNATURES: list[tuple[str, list[str]]] = [
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
        r":\s*$",
    ]),
]


def detect_language(code: str) -> Optional[str]:
    """Return language name or None if not recognised."""
    if not code or not code.strip():
        return None
    scores: dict[str, int] = {}
    for lang, patterns in _SIGNATURES:
        n = sum(1 for p in patterns if re.search(p, code, flags=re.MULTILINE))
        if n:
            scores[lang] = n
    if not scores:
        return None
    best_lang: Optional[str] = None
    best_score = 0
    for lang, _ in _SIGNATURES:
        if scores.get(lang, 0) > best_score:
            best_score = scores[lang]
            best_lang = lang
    return best_lang
