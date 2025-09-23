# src/utils.py

import shutil
import zipfile
import uuid
from pathlib import Path

# === Configure your repo root and subdirs here ===
BASE_DIR       = Path(__file__).resolve().parent.parent
BACKUPS_DIR    = BASE_DIR / 'backups'
PROJECTS_DIR   = BASE_DIR / 'projects'
TAGS_DIR       = BASE_DIR / 'tags'
GENERATED_DIR  = BASE_DIR / 'generated'
MODULES_DIR    = BASE_DIR / 'modules'
JDBC_DIR       = BASE_DIR / 'jdbc'
SECRETS_DIR    = BASE_DIR / 'secrets'

def ensure_directories():
    """
    Create the core directories if they don't exist.
    """
    for d in (BACKUPS_DIR, PROJECTS_DIR, TAGS_DIR, GENERATED_DIR, MODULES_DIR, JDBC_DIR, SECRETS_DIR):
        d.mkdir(parents=True, exist_ok=True)

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
