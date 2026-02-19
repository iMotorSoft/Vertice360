from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_ENV_PATTERN = re.compile(r"os\.getenv\(|os\.environ\.get\(|os\.environ\[")
EXCLUDED_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_FILES = {"globalVar.py", "tests/test_no_direct_env_reads.py"}


def _should_skip(rel_path: str) -> bool:
    parts = rel_path.split("/")
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    return rel_path in EXCLUDED_FILES


def test_no_direct_env_reads_outside_globalvar() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if _should_skip(rel):
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_ENV_PATTERN.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, "Direct env reads found outside globalVar.py:\n" + "\n".join(offenders)
