"""Load + cache cheatsheet knowledge packs from disk (v0.11)."""

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

    L2 cache: maps (file_path, mtime_ns) → parsed Pack. Reload on file
    modification without process restart.
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
