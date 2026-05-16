"""Dependency analyzer for identifying project tech stack.

Parses manifest files across 8 ecosystems to detect frameworks, libraries,
languages, services, and databases. Each match is emitted as an Evidence
item carrying its category, so downstream consumers can route into typed
lists on ChosenStack.

Supported manifests:
    Python:     requirements.txt
    JS / Node:  package.json
    Go:         go.mod
    Rust:       Cargo.toml
    Java:       pom.xml, build.gradle, build.gradle.kts
    Kotlin:     build.gradle, build.gradle.kts (shared with Java)
    Ruby:       Gemfile
    PHP:        composer.json
    C# / .NET:  *.csproj
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover — project pins 3.12
    tomllib = None  # type: ignore

from src.agents.prompt_refiner.context_types import Evidence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Package map: package-id (lowercase) -> normalized record.
# Each record carries name (display), category, language, weight.
# Categories: language | framework | library | service | database
# ---------------------------------------------------------------------------
PACKAGE_MAP: Dict[str, Dict[str, object]] = {
    # ----- Python -----
    "fastapi":    {"name": "FastAPI",    "category": "framework", "language": "python", "weight": 0.9},
    "flask":      {"name": "Flask",      "category": "framework", "language": "python", "weight": 0.9},
    "django":     {"name": "Django",     "category": "framework", "language": "python", "weight": 0.9},
    "sqlalchemy": {"name": "SQLAlchemy", "category": "library",   "language": "python", "weight": 0.7},
    "pandas":     {"name": "Pandas",     "category": "library",   "language": "python", "weight": 0.6},
    "pytest":     {"name": "Pytest",     "category": "library",   "language": "python", "weight": 0.5},

    # ----- JavaScript / Node -----
    "react":      {"name": "React",      "category": "framework", "language": "javascript", "weight": 0.9},
    "vue":        {"name": "Vue.js",     "category": "framework", "language": "javascript", "weight": 0.9},
    "next":       {"name": "Next.js",    "category": "framework", "language": "javascript", "weight": 0.9},
    "express":    {"name": "Express.js", "category": "framework", "language": "javascript", "weight": 0.9},
    "typescript": {"name": "TypeScript", "category": "language",  "language": "typescript", "weight": 0.8},

    # ----- Go -----
    # Go modules are namespaced (e.g. github.com/gin-gonic/gin). We index by
    # both the full module path and the conventional short name; the parser
    # does the short-name lookup.
    "gin":        {"name": "Gin",        "category": "framework", "language": "go", "weight": 0.9},
    "echo":       {"name": "Echo",       "category": "framework", "language": "go", "weight": 0.9},
    "fiber":      {"name": "Fiber",      "category": "framework", "language": "go", "weight": 0.9},
    "cobra":      {"name": "Cobra",      "category": "framework", "language": "go", "weight": 0.8},
    "gorm":       {"name": "GORM",       "category": "library",   "language": "go", "weight": 0.7},

    # ----- Rust -----
    "actix-web":  {"name": "Actix Web",  "category": "framework", "language": "rust", "weight": 0.9},
    "axum":       {"name": "Axum",       "category": "framework", "language": "rust", "weight": 0.9},
    "rocket":     {"name": "Rocket",     "category": "framework", "language": "rust", "weight": 0.9},
    "tokio":      {"name": "Tokio",      "category": "library",   "language": "rust", "weight": 0.8},
    "clap":       {"name": "Clap",       "category": "framework", "language": "rust", "weight": 0.7},
    "serde":      {"name": "Serde",      "category": "library",   "language": "rust", "weight": 0.6},
    "diesel":     {"name": "Diesel",     "category": "library",   "language": "rust", "weight": 0.7},

    # ----- Java / Kotlin -----
    "spring-boot":      {"name": "Spring Boot",      "category": "framework", "language": "java",   "weight": 0.9},
    "spring-core":      {"name": "Spring Framework", "category": "framework", "language": "java",   "weight": 0.8},
    "spring-web":       {"name": "Spring Web",       "category": "framework", "language": "java",   "weight": 0.8},
    "hibernate-core":   {"name": "Hibernate",        "category": "library",   "language": "java",   "weight": 0.7},
    "junit-jupiter":    {"name": "JUnit",            "category": "library",   "language": "java",   "weight": 0.5},
    "junit":            {"name": "JUnit",            "category": "library",   "language": "java",   "weight": 0.5},
    "ktor":             {"name": "Ktor",             "category": "framework", "language": "kotlin", "weight": 0.9},
    "ktor-server-core": {"name": "Ktor",             "category": "framework", "language": "kotlin", "weight": 0.9},

    # ----- Ruby -----
    "rails":      {"name": "Rails",      "category": "framework", "language": "ruby", "weight": 0.9},
    "sinatra":    {"name": "Sinatra",    "category": "framework", "language": "ruby", "weight": 0.9},
    "rspec":      {"name": "RSpec",      "category": "library",   "language": "ruby", "weight": 0.5},
    "sidekiq":    {"name": "Sidekiq",    "category": "library",   "language": "ruby", "weight": 0.6},

    # ----- PHP -----
    "laravel/framework": {"name": "Laravel",  "category": "framework", "language": "php", "weight": 0.9},
    "symfony/symfony":   {"name": "Symfony",  "category": "framework", "language": "php", "weight": 0.9},
    "phpunit/phpunit":   {"name": "PHPUnit",  "category": "library",   "language": "php", "weight": 0.5},

    # ----- C# / .NET -----
    "microsoft.aspnetcore.app":        {"name": "ASP.NET Core",       "category": "framework", "language": "csharp", "weight": 0.9},
    "microsoft.aspnetcore.mvc":        {"name": "ASP.NET Core MVC",   "category": "framework", "language": "csharp", "weight": 0.9},
    "microsoft.entityframeworkcore":   {"name": "Entity Framework",   "category": "library",   "language": "csharp", "weight": 0.7},
    "xunit":                            {"name": "xUnit",              "category": "library",   "language": "csharp", "weight": 0.5},
    "nunit":                            {"name": "NUnit",              "category": "library",   "language": "csharp", "weight": 0.5},
}


def _lookup_package(key: str) -> Optional[Dict[str, object]]:
    """Case-insensitive lookup into PACKAGE_MAP."""
    return PACKAGE_MAP.get(key.lower())


def _evidence_from_info(
    info: Dict[str, object],
    *,
    source: str = "dependency_analysis",
    file: Optional[str] = None,
    line: Optional[int] = None,
    excerpt: Optional[str] = None,
) -> Evidence:
    """Construct an Evidence object from a PACKAGE_MAP record."""
    return Evidence(
        source=source,
        file=file,
        line=line,
        excerpt=(excerpt[:50] if excerpt else None),
        match=str(info["name"]),
        weight=float(info["weight"]),
        confidence_hint="strong",
        category=str(info["category"]),
    )


# ---------------------------------------------------------------------------
# Individual parsers.
# Each takes (content, filename) -> List[Evidence]. Parsers are defensive:
# malformed input yields an empty list with a logged warning, never an
# unhandled exception.
# ---------------------------------------------------------------------------

def _parse_requirements(content: str, filename: str) -> List[Evidence]:
    """Parse Python requirements.txt."""
    out: List[Evidence] = []
    for line_num, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z0-9_\-\.]+)", line)
        if not m:
            continue
        info = _lookup_package(m.group(1))
        if info:
            out.append(_evidence_from_info(info, file=filename, line=line_num, excerpt=line))
    return out


def _parse_package_json(content: str, filename: str) -> List[Evidence]:
    """Parse Node.js package.json (dependencies + devDependencies)."""
    out: List[Evidence] = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse {filename}")
        return out
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section) or {}
        if not isinstance(deps, dict):
            continue
        for pkg_name, version in deps.items():
            info = _lookup_package(pkg_name)
            if info:
                out.append(_evidence_from_info(
                    info,
                    file=filename,
                    line=None,
                    excerpt=f'"{pkg_name}": "{version}"',
                ))
    return out


def _parse_go_mod(content: str, filename: str) -> List[Evidence]:
    """Parse Go go.mod files.

    Recognizes both single-line requires and `require ( ... )` blocks.
    Extracts the trailing path segment (e.g. ``gin`` from ``github.com/gin-gonic/gin``)
    and looks it up in PACKAGE_MAP.
    """
    out: List[Evidence] = []
    in_block = False
    for line_num, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue

        # Forms:
        #   require github.com/gin-gonic/gin v1.9.0
        #   github.com/gin-gonic/gin v1.9.0   (inside a block)
        m = re.match(r"^(?:require\s+)?(\S+)\s+v[\d\w\.\-+]+", line)
        if not m:
            continue
        module_path = m.group(1)
        # Pick the last path segment as the conventional short name.
        short = module_path.rsplit("/", 1)[-1]
        info = _lookup_package(short)
        if info:
            out.append(_evidence_from_info(info, file=filename, line=line_num, excerpt=line))
    return out


def _parse_cargo_toml(content: str, filename: str) -> List[Evidence]:
    """Parse Rust Cargo.toml ([dependencies] + [dev-dependencies])."""
    out: List[Evidence] = []
    if tomllib is None:  # pragma: no cover
        logger.warning("tomllib not available; skipping Cargo.toml parsing")
        return out
    try:
        data = tomllib.loads(content)
    except Exception as e:  # tomllib.TOMLDecodeError on 3.11+
        logger.warning(f"Failed to parse {filename}: {e}")
        return out
    for section in ("dependencies", "dev-dependencies"):
        deps = data.get(section) or {}
        if not isinstance(deps, dict):
            continue
        for pkg_name, spec in deps.items():
            info = _lookup_package(pkg_name)
            if info:
                out.append(_evidence_from_info(
                    info,
                    file=filename,
                    line=None,
                    excerpt=f'{pkg_name} = {spec!r}',
                ))
    return out


def _strip_namespace(tag: str) -> str:
    """Strip XML namespace from a tag (``{ns}name`` -> ``name``)."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_pom_xml(content: str, filename: str) -> List[Evidence]:
    """Parse Maven pom.xml.

    Looks for <dependency><artifactId>X</artifactId></dependency> entries.
    Namespace-agnostic.
    """
    out: List[Evidence] = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        logger.warning(f"Failed to parse {filename}: {e}")
        return out

    # iter() is namespace-sensitive; walk and match by stripped tag instead.
    for elem in root.iter():
        if _strip_namespace(elem.tag) != "dependency":
            continue
        artifact_id = None
        group_id = None
        for child in elem:
            tag = _strip_namespace(child.tag)
            if tag == "artifactId":
                artifact_id = (child.text or "").strip()
            elif tag == "groupId":
                group_id = (child.text or "").strip()
        if not artifact_id:
            continue
        info = _lookup_package(artifact_id)
        if info:
            excerpt = f"{group_id}:{artifact_id}" if group_id else artifact_id
            out.append(_evidence_from_info(info, file=filename, line=None, excerpt=excerpt))
    return out


# Match Gradle dependency declarations:
#   implementation 'org.springframework.boot:spring-boot-starter-web:3.2.0'
#   testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
#   api group: 'org.foo', name: 'bar', version: '1.0'   (Groovy map syntax — best-effort)
_GRADLE_COORD_RE = re.compile(
    r"""
    \b(implementation|api|testImplementation|compileOnly|runtimeOnly|kapt)
    \s*[\(\s]?
    ['"]([^:'"]+):([^:'"]+):([^'"]+)['"]
    """,
    re.VERBOSE,
)


def _parse_gradle(content: str, filename: str) -> List[Evidence]:
    """Parse Gradle build.gradle / build.gradle.kts.

    Extracts ``group:artifact:version`` coordinates. Looks up by artifactId.
    """
    out: List[Evidence] = []
    for line_num, raw in enumerate(content.splitlines(), start=1):
        for m in _GRADLE_COORD_RE.finditer(raw):
            _, group_id, artifact_id, _ = m.groups()
            info = _lookup_package(artifact_id)
            if info:
                out.append(_evidence_from_info(
                    info,
                    file=filename,
                    line=line_num,
                    excerpt=f"{group_id}:{artifact_id}",
                ))
    return out


_GEMFILE_RE = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"]""")


def _parse_gemfile(content: str, filename: str) -> List[Evidence]:
    """Parse Ruby Gemfile (``gem 'name'`` declarations)."""
    out: List[Evidence] = []
    for line_num, raw in enumerate(content.splitlines(), start=1):
        m = _GEMFILE_RE.match(raw)
        if not m:
            continue
        info = _lookup_package(m.group(1))
        if info:
            out.append(_evidence_from_info(
                info, file=filename, line=line_num, excerpt=raw.strip(),
            ))
    return out


def _parse_composer_json(content: str, filename: str) -> List[Evidence]:
    """Parse PHP composer.json (require + require-dev)."""
    out: List[Evidence] = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse {filename}")
        return out
    for section in ("require", "require-dev"):
        deps = data.get(section) or {}
        if not isinstance(deps, dict):
            continue
        for pkg_name, version in deps.items():
            info = _lookup_package(pkg_name)
            if info:
                out.append(_evidence_from_info(
                    info,
                    file=filename,
                    line=None,
                    excerpt=f'"{pkg_name}": "{version}"',
                ))
    return out


def _parse_csproj(content: str, filename: str) -> List[Evidence]:
    """Parse C# .csproj (PackageReference Include="X")."""
    out: List[Evidence] = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        logger.warning(f"Failed to parse {filename}: {e}")
        return out
    for elem in root.iter():
        if _strip_namespace(elem.tag) != "PackageReference":
            continue
        pkg_name = elem.attrib.get("Include")
        if not pkg_name:
            continue
        info = _lookup_package(pkg_name)
        if info:
            version = elem.attrib.get("Version", "")
            excerpt = f'{pkg_name} {version}'.strip()
            out.append(_evidence_from_info(info, file=filename, line=None, excerpt=excerpt))
    return out


# Filename-suffix → parser dispatch table. Order matters only insofar as the
# longest specific match should be checked before the most generic, but the
# current set has no ambiguity since each filename is a unique exact match.
PARSERS: Dict[str, Callable[[str, str], List[Evidence]]] = {
    "requirements.txt": _parse_requirements,
    "package.json":     _parse_package_json,
    "go.mod":           _parse_go_mod,
    "Cargo.toml":       _parse_cargo_toml,
    "pom.xml":          _parse_pom_xml,
    "build.gradle":     _parse_gradle,
    "build.gradle.kts": _parse_gradle,
    "Gemfile":          _parse_gemfile,
    "composer.json":    _parse_composer_json,
}


def _pick_parser(filename: str) -> Optional[Callable[[str, str], List[Evidence]]]:
    """Resolve a parser for a given filename (or path with trailing filename).

    Matches:
      - exact basename present in PARSERS
      - ``*.csproj`` suffix → _parse_csproj
    """
    # Normalize to basename for exact-match lookup.
    basename = filename.rsplit("/", 1)[-1]
    if basename in PARSERS:
        return PARSERS[basename]
    if basename.endswith(".csproj"):
        return _parse_csproj
    return None


class DependencyAnalyzer:
    """Analyzes project dependencies to detect tech stack.

    Public API is unchanged from v0.9: ``analyze(files)`` takes a
    ``{filename: content}`` dict and returns a list of Evidence. New in
    v0.10: Evidence items carry a ``category`` field.
    """

    def analyze(self, files: Dict[str, str]) -> List[Evidence]:
        """Run every applicable parser and concatenate their Evidence."""
        evidence: List[Evidence] = []
        for filename, content in files.items():
            parser = _pick_parser(filename)
            if parser is None:
                continue
            try:
                evidence.extend(parser(content, filename))
            except Exception as e:
                # Defense in depth: even if a parser raises, we degrade
                # gracefully rather than failing the entire refine call.
                logger.warning(
                    f"Parser for {filename} raised: {e}", exc_info=True,
                )
        return evidence

    # ----- Back-compat shims for v0.9 callers -----

    def _parse_requirements(self, content: str, filename: str) -> List[Evidence]:
        return _parse_requirements(content, filename)

    def _parse_package_json(self, content: str, filename: str) -> List[Evidence]:
        return _parse_package_json(content, filename)
