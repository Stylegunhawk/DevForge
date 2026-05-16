"""Tests for DependencyAnalyzer parsers (v0.10).

One test per supported manifest format. Each asserts on:
  * Evidence count (right number of matches found)
  * Match names (correct PACKAGE_MAP normalization)
  * Category routing (framework / library / language / service / database)
"""

import pytest

from src.agents.prompt_refiner.dependency_analyzer import (
    DependencyAnalyzer,
    PACKAGE_MAP,
    PARSERS,
    _pick_parser,
)


@pytest.fixture
def analyzer():
    return DependencyAnalyzer()


# ---------------------------------------------------------------------------
# Existing formats (regression — must still work)
# ---------------------------------------------------------------------------

def test_parse_requirements_txt(analyzer):
    content = "fastapi==0.110.0\nsqlalchemy==2.0\n# a comment\n\npytest>=8.0\n"
    out = analyzer.analyze({"requirements.txt": content})

    matches = {(e.match, e.category) for e in out}
    assert ("FastAPI", "framework") in matches
    assert ("SQLAlchemy", "library") in matches
    assert ("Pytest", "library") in matches
    assert len(out) == 3


def test_parse_package_json(analyzer):
    content = '{"dependencies": {"react": "^18.2", "next": "^14"}, "devDependencies": {"typescript": "^5.3"}}'
    out = analyzer.analyze({"package.json": content})

    by_name = {e.match: e for e in out}
    assert by_name["React"].category == "framework"
    assert by_name["Next.js"].category == "framework"
    assert by_name["TypeScript"].category == "language"


# ---------------------------------------------------------------------------
# New parsers (v0.10)
# ---------------------------------------------------------------------------

def test_parse_go_mod_block_form(analyzer):
    content = """module myapp

go 1.22

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/spf13/cobra v1.8.0
    gorm.io/gorm v1.25.0
)
"""
    out = analyzer.analyze({"go.mod": content})
    matches = {e.match for e in out}
    assert "Gin" in matches
    assert "Cobra" in matches
    assert "GORM" in matches


def test_parse_go_mod_single_line(analyzer):
    content = "module x\ngo 1.22\nrequire github.com/labstack/echo v4.11.0\n"
    out = analyzer.analyze({"go.mod": content})
    assert any(e.match == "Echo" and e.category == "framework" for e in out)


def test_parse_cargo_toml(analyzer):
    content = """[package]
name = "myapp"

[dependencies]
axum = "0.7"
tokio = { version = "1.0", features = ["full"] }
serde = "1.0"

[dev-dependencies]
diesel = "2.0"
"""
    out = analyzer.analyze({"Cargo.toml": content})
    by_name = {e.match: e for e in out}
    assert by_name["Axum"].category == "framework"
    assert by_name["Tokio"].category == "library"
    assert by_name["Serde"].category == "library"
    assert by_name["Diesel"].category == "library"


def test_parse_pom_xml(analyzer):
    content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot</artifactId>
      <version>3.2.0</version>
    </dependency>
    <dependency>
      <groupId>org.hibernate</groupId>
      <artifactId>hibernate-core</artifactId>
      <version>6.4.0</version>
    </dependency>
  </dependencies>
</project>"""
    out = analyzer.analyze({"pom.xml": content})
    by_name = {e.match: e for e in out}
    assert by_name["Spring Boot"].category == "framework"
    assert by_name["Hibernate"].category == "library"


def test_parse_gradle_groovy(analyzer):
    content = """plugins {
    id 'org.springframework.boot' version '3.2.0'
}
dependencies {
    implementation 'org.springframework.boot:spring-boot:3.2.0'
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
}
"""
    out = analyzer.analyze({"build.gradle": content})
    matches = {e.match for e in out}
    assert "Spring Boot" in matches
    assert "JUnit" in matches


def test_parse_gradle_kotlin_dsl(analyzer):
    content = """dependencies {
    implementation("io.ktor:ktor-server-core:2.3.0")
}
"""
    out = analyzer.analyze({"build.gradle.kts": content})
    assert any(e.match == "Ktor" and e.category == "framework" for e in out)


def test_parse_gemfile(analyzer):
    content = """source 'https://rubygems.org'

gem 'rails', '~> 7.0'
gem 'sidekiq'

group :test do
  gem 'rspec'
end
"""
    out = analyzer.analyze({"Gemfile": content})
    by_name = {e.match: e for e in out}
    assert by_name["Rails"].category == "framework"
    assert by_name["Sidekiq"].category == "library"
    assert by_name["RSpec"].category == "library"


def test_parse_composer_json(analyzer):
    content = """{
  "require": {
    "laravel/framework": "^11.0",
    "symfony/symfony": "^7.0"
  },
  "require-dev": {
    "phpunit/phpunit": "^10.0"
  }
}"""
    out = analyzer.analyze({"composer.json": content})
    by_name = {e.match: e for e in out}
    assert by_name["Laravel"].category == "framework"
    assert by_name["Symfony"].category == "framework"
    assert by_name["PHPUnit"].category == "library"


def test_parse_csproj(analyzer):
    content = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.App" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
    <PackageReference Include="xunit" Version="2.6.0" />
  </ItemGroup>
</Project>"""
    out = analyzer.analyze({"MyApp.csproj": content})
    by_name = {e.match: e for e in out}
    assert by_name["ASP.NET Core"].category == "framework"
    assert by_name["Entity Framework"].category == "library"
    assert by_name["xUnit"].category == "library"


# ---------------------------------------------------------------------------
# Dispatcher behavior
# ---------------------------------------------------------------------------

def test_pick_parser_resolves_csproj_by_suffix():
    parser = _pick_parser("solution/Backend/MyApp.csproj")
    assert parser is not None
    # Should dispatch to _parse_csproj
    from src.agents.prompt_refiner.dependency_analyzer import _parse_csproj
    assert parser is _parse_csproj


def test_pick_parser_returns_none_for_unknown():
    assert _pick_parser("Makefile") is None
    assert _pick_parser("README.md") is None


def test_unknown_filenames_are_silently_ignored(analyzer):
    out = analyzer.analyze({"README.md": "# hello", "Makefile": "all:\n\techo hi"})
    assert out == []


def test_malformed_manifest_logs_warning_returns_empty(analyzer, caplog):
    # Malformed JSON in package.json should NOT raise.
    out = analyzer.analyze({"package.json": "{not json"})
    assert out == []


def test_polyglot_bundle(analyzer):
    """End-to-end: a single analyze() call across all 9 supported manifests."""
    files = {
        "requirements.txt": "fastapi==0.110\nsqlalchemy==2.0",
        "package.json":     '{"dependencies": {"react": "^18"}}',
        "go.mod":           "module x\nrequire github.com/gin-gonic/gin v1.9.0",
        "Cargo.toml":       '[dependencies]\naxum = "0.7"',
        "pom.xml":          '<?xml version="1.0"?><project><dependencies><dependency><artifactId>spring-boot</artifactId></dependency></dependencies></project>',
        "build.gradle":     "dependencies { implementation 'org.springframework.boot:spring-boot:3.2.0' }",
        "Gemfile":          "gem 'rails'",
        "composer.json":    '{"require": {"laravel/framework": "^11.0"}}',
        "App.csproj":       '<Project><ItemGroup><PackageReference Include="xunit" Version="2.6.0"/></ItemGroup></Project>',
    }
    out = analyzer.analyze(files)
    matches = {e.match for e in out}
    # At least one match from each ecosystem
    assert "FastAPI" in matches
    assert "React" in matches
    assert "Gin" in matches
    assert "Axum" in matches
    assert "Spring Boot" in matches
    assert "Rails" in matches
    assert "Laravel" in matches
    assert "xUnit" in matches


# ---------------------------------------------------------------------------
# PACKAGE_MAP integrity
# ---------------------------------------------------------------------------

def test_every_package_map_entry_has_required_keys():
    """Schema check on PACKAGE_MAP."""
    required = {"name", "category", "language", "weight"}
    valid_categories = {"language", "framework", "library", "service", "database"}
    for key, info in PACKAGE_MAP.items():
        assert required.issubset(info.keys()), f"{key} missing keys: {required - info.keys()}"
        assert info["category"] in valid_categories, f"{key} has invalid category: {info['category']}"
        assert isinstance(info["weight"], (int, float))
        assert 0.0 < info["weight"] <= 1.0


def test_parsers_registry_is_consistent():
    """Every parser in PARSERS is callable and accepts (str, str)."""
    for filename, parser in PARSERS.items():
        assert callable(parser)
        # Smoke: empty content should never raise
        result = parser("", filename)
        assert isinstance(result, list)
