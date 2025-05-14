# src/compose_generator.py

import logging
from pathlib import Path
from typing import Dict, Optional

from models import Backup, Project, TagFile, ComposeConfig
from errors import ConfigBuildError
import logging

logger = logging.getLogger(__name__)

class ConfigBuildError(Exception):
    """Raised when building the ComposeConfig fails due to invalid inputs."""


def build_config(raw: Dict[str, str]) -> ComposeConfig:
    """
    Build and validate a ComposeConfig from raw GUI inputs.

    Expected keys in raw dict:
      - mode: 'clean' or 'backup'
      - backup_name: filename under backups/ (required if mode=='backup')
      - project_name: folder name under projects/ (optional)
      - tag_name: filename under tags/ (optional)
      - http_port, https_port: strings or ints
      - admin_user, admin_pass, gateway_name, edition, timezone
    """
    try:
        logger.debug("Starting ComposeConfig build with raw inputs: %s", raw)

        # Mode
        mode = raw.get('mode', '').lower()
        if mode not in ('clean', 'backup'):
            raise ConfigBuildError(f"Invalid mode: '{mode}'. Must be 'clean' or 'backup'.")
        logger.info("Mode set to: %s", mode)

        # Backup (if any)
        backup: Optional[Backup] = None
        if mode == 'backup':
            backup_name = raw.get('backup_name')
            if not backup_name:
                raise ConfigBuildError("Mode 'backup' selected, but no backup file provided.")
            backup_path = Path(raw.get('backups_dir', 'backups')) / backup_name
            backup = Backup(name=backup_name, path=backup_path)
            backup.validate()
            logger.info("Loaded backup: %s", backup.path)

        # Project (optional)
        project: Optional[Project] = None
        project_name = raw.get('project_name')
        if project_name:
            project_path = Path(raw.get('projects_dir', 'projects')) / project_name
            project = Project(name=project_name, path=project_path)
            project.validate()
            logger.info("Loaded project: %s", project.path)

        # TagFile (optional)
        tag_file: Optional[TagFile] = None
        tag_name = raw.get('tag_name')
        if tag_name:
            tag_path = Path(raw.get('tags_dir', 'tags')) / tag_name
            tag_file = TagFile(name=tag_name, path=tag_path)
            tag_file.validate()
            logger.info("Loaded tag file: %s", tag_file.path)

        # Ports & other envs
        try:
            http_port = int(raw.get('http_port', 8088))
            https_port = int(raw.get('https_port', 8043))
        except ValueError as ve:
            raise ConfigBuildError(f"Invalid port number: {ve}")
        admin_user = raw.get('admin_user', '').strip()
        admin_pass = raw.get('admin_pass', '').strip()
        gateway_name = raw.get('gateway_name', '').strip()
        edition = raw.get('edition', 'standard').strip()
        timezone = raw.get('timezone', 'America/Chicago').strip()

        # Validate required fields
        if not admin_user or not admin_pass:
            raise ConfigBuildError("Admin username and password must be provided.")
        if not gateway_name:
            raise ConfigBuildError("Gateway name must be provided.")

        # 6) Build the config object
        cfg = ComposeConfig(
            mode=mode,
            backup=backup,
            project=project,
            tag_file=tag_file,
            http_port=http_port,
            https_port=https_port,
            admin_user=admin_user,
            admin_password=admin_pass,
            gateway_name=gateway_name,
            edition=edition,
            timezone=timezone
        )

        # 7) Final validation
        cfg.validate()
        logger.info("Successfully built ComposeConfig: %s", cfg)

        return cfg

    except Exception as e:
        # Log the full stack and rethrow as ConfigBuildError if not already
        logger.exception("Failed to build ComposeConfig")
        if isinstance(e, ConfigBuildError):
            raise
        else:
            raise ConfigBuildError(str(e))
