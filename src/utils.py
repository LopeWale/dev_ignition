# src/utils.py

import shutil
import uuid
import zipfile
from pathlib import Path
from paths import (
    BACKUPS_DIR,
    GENERATED_DIR,
    JDBC_DIR,
    MODULES_DIR,
    PROJECTS_DIR,
    SECRETS_DIR,
    TAGS_DIR,
    ensure_runtime_directories,
)

from paths import (
    BACKUPS_DIR,
    GENERATED_DIR,
    JDBC_DIR,
    MODULES_DIR,
    PROJECTS_DIR,
    SECRETS_DIR,
    TAGS_DIR,
    ensure_runtime_directories,
)


def ensure_directories():
    """
    Create the core directories if they don't exist.
    """
    ensure_runtime_directories()


def save_backup(src_path: str) -> str:
    """
    Copy an uploaded gateway backup into backups/.
    Returns the filename under backups/.
    """
    ensure_directories()
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"Backup file not found: {src}")
    dest = BACKUPS_DIR / src.name
    # avoid overwriting by adding a UUID suffix if needed
    if dest.exists():
        dest = BACKUPS_DIR / f"{src.stem}_{uuid.uuid4().hex}{src.suffix}"
    shutil.copy(src, dest)
    return dest.name

def save_tag_file(src_path: str) -> str:
    """
    Copy an uploaded tag export (JSON or XML) into tags/.
    Returns the filename under tags/.
    """
    ensure_directories()
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"Tag file not found: {src}")
    dest = TAGS_DIR / src.name
    if dest.exists():
        dest = TAGS_DIR / f"{src.stem}_{uuid.uuid4().hex}{src.suffix}"
    shutil.copy(src, dest)
    return dest.name

def unzip_project(zip_path: str) -> str:
    """
    Unzip a project ZIP into projects/<ProjectName>/.
    If that folder exists, it is removed first.
    Returns the project name (zip filename stem).
    """
    ensure_directories()
    src = Path(zip_path)
    if not src.is_file():
        raise FileNotFoundError(f"Project ZIP not found: {src}")
    project_name = src.stem
    dest_dir = PROJECTS_DIR / project_name
    # clear any existing folder for a clean import
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    # extract all files
    with zipfile.ZipFile(src, 'r') as zf:
        zf.extractall(dest_dir)
    return project_name

def clear_generated():
    """
    Remove all files and subdirectories in generated/.
    """
    ensure_directories()
    for item in GENERATED_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
