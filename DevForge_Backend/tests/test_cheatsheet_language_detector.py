"""Tests for cheatsheet language detector (v0.11)."""

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
    code = (
        "package main\n"
        "import \"fmt\"\n"
        "func main() { fmt.Println(\"hi\") }\n"
    )
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
