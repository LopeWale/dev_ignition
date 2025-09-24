"""Central definitions for repository paths used across the application."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
GENERATED_DIR = BASE_DIR / "generated"
PROJECTS_DIR = BASE_DIR / "projects"
TAGS_DIR = BASE_DIR / "tags"
BACKUPS_DIR = BASE_DIR / "backups"
LOGS_DIR = BASE_DIR / "logs"
MODULES_DIR = BASE_DIR / "modules"
JDBC_DIR = BASE_DIR / "jdbc"
SECRETS_DIR = BASE_DIR / "secrets"

_RUNTIME_DIRECTORIES = (
    PROJECTS_DIR,
    TAGS_DIR,
    BACKUPS_DIR,
    LOGS_DIR,
    GENERATED_DIR,
    MODULES_DIR,
    JDBC_DIR,
    SECRETS_DIR,
)


def ensure_runtime_directories(additional: Optional[Iterable[Path]] = None) -> None:
    """Ensure that all runtime directories exist on disk."""

    for directory in _RUNTIME_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)

    if additional is None:
        return

    for path in additional:
        Path(path).mkdir(parents=True, exist_ok=True)


__all__ = [
    "BASE_DIR",
    "TEMPLATES_DIR",
    "GENERATED_DIR",
    "PROJECTS_DIR",
    "TAGS_DIR",
    "BACKUPS_DIR",
    "LOGS_DIR",
    "MODULES_DIR",
    "JDBC_DIR",
    "SECRETS_DIR",
    "ensure_runtime_directories",
]
