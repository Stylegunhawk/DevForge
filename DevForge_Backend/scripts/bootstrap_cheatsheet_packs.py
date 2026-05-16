"""One-shot LLM bootstrap for cheatsheet packs (v0.11).

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
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

from src.agents.cheatsheet.library_detector import LIBRARY_SIGNATURES
from src.agents.cheatsheet.pack_loader import SUPPORTED_LANGUAGES
from src.agents.cheatsheet.pack_models import Pack
from src.core.model_router import model_router

logger = logging.getLogger(__name__)

PACK_ROOT = Path("data/cheatsheet_packs")
REPORT_PATH = Path("scripts/bootstrap_report.md")
SKILL_LEVELS = ("beginner", "intermediate", "expert")

SYSTEM_PROMPT = """You are a senior software engineer writing a cheat sheet pack.

Output STRICT YAML matching this schema:

pack:
  language: <lang>
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
            f"Generate a {skill}-level cheat sheet pack for the {target_name} "
            f"programming language. Use {target_name} for all examples. "
            f"Today's date is {date.today().isoformat()}."
        )
    return (
        f"Generate a {skill}-level cheat sheet pack for the {target_name} Python "
        f"library. All examples must use Python and import {target_name}. "
        f"Today's date is {date.today().isoformat()}."
    )


async def _bootstrap_one(
    target_kind: str, target_name: str, skill: str, overwrite: bool,
) -> tuple[Path, str]:
    sub = "languages" if target_kind == "language" else "libraries"
    path = PACK_ROOT / sub / target_name / f"{skill}.yaml"
    if path.exists() and not overwrite:
        return path, "skipped (exists)"

    path.parent.mkdir(parents=True, exist_ok=True)
    prompt = _user_prompt(target_kind, target_name, skill)

    model_name = model_router.select_model_by_task("routing")
    for attempt in range(1, 4):
        try:
            full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
            response = await model_router.invoke_with_usage(
                prompt=full_prompt,
                model_name=model_name,
                task_type="cheatsheet_bootstrap",
                tenant_id="bootstrap",
                integration_name="bootstrap_cli",
                user_id="bootstrap",
            )
            content = response.content if hasattr(response, "content") else str(response)
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith(("yaml\n", "yml\n")):
                    content = content.split("\n", 1)[1]
            raw = yaml.safe_load(content)
            pack = Pack(**raw)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(
                    pack.model_dump(mode="json"),
                    f, sort_keys=False, allow_unicode=True,
                )
            return path, f"ok (attempt {attempt})"
        except Exception as e:
            logger.warning(
                f"{target_kind}/{target_name}/{skill} attempt {attempt} failed: {e}"
            )
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
        skills = [args.skill] if args.skill else list(SKILL_LEVELS)
        for skill in skills:
            targets.append(("language", args.language, skill))
    elif args.library:
        skills = [args.skill] if args.skill else list(SKILL_LEVELS)
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
            line = (
                f"{i:3d}/{len(targets)} | {kind:8s} | {name:20s} | "
                f"{skill:12s} | {outcome}"
            )
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
