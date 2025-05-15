from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal, Tuple

@dataclass
class Backup:
    name: str
    path: Path

    def validate(self) -> None:
        """
        Ensure the backup file exists and has a recognized .gwbk extension.
        """
        if not self.path.is_file():
            raise FileNotFoundError(f"Backup file not found: {self.path}")
        if self.path.suffix.lower() != '.gwbk':
            raise ValueError(f"Invalid backup extension: {self.path.suffix}. Expected .gwbk")

@dataclass
class Project:
    name: str
    path: Path

    def validate(self) -> None:
        """
        Ensure the project folder contains an Ignition 8.1 project manifest (project.json).
        Supports both direct export or a nested folder structure.
        """
        # Check for top-level project.json
        manifest = self.path / 'project.json'
        if manifest.is_file():
            return
        # Check for a single nested folder containing project.json
        subdirs = [d for d in self.path.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            nested_manifest = subdirs[0] / 'project.json'
            if nested_manifest.is_file():
                # Flatten path to nested folder
                self.path = subdirs[0]
                return
        raise ValueError(f"Project '{self.name}' missing project.json manifest in {self.path}")

@dataclass
class TagFile:
    name: str
    path: Path
    format: Literal['json', 'xml'] = field(init=False)

    def __post_init__(self):
        suffix = self.path.suffix.lower()
        if suffix == '.json':
            self.format = 'json'
        elif suffix == '.xml':
            self.format = 'xml'
        else:
            raise ValueError(f"Unsupported tag file format: {suffix}")

    def validate(self) -> None:
        """
        Ensure the tag file exists and matches its declared format.
        """
        if not self.path.is_file():
            raise FileNotFoundError(f"Tag file not found: {self.path}")

@dataclass
class ComposeConfig:
    mode: Literal['clean', 'backup']
    backup: Optional[Backup]
    project: Optional[Project]
    tag_file: Optional[TagFile]
    http_port: int
    https_port: int
    admin_user: str
    admin_password: str
    gateway_name: str
    edition: str = 'standard'
    timezone: str = 'America/Chicago'

    def validate(self) -> None:
        """
        Validate the overall config:
        - Mode-specific requirements
        - Port bounds
        - Credentials non-empty
        """
        if self.mode not in ('clean', 'backup'):
            raise ValueError(f"Invalid mode: {self.mode}. Expected 'clean' or 'backup'.")
        if self.mode == 'backup':
            if not self.backup:
                raise ValueError("Backup mode requires a Backup object.")
            self.backup.validate()
        # Project is optional in both modes, but if set validate it
        if self.project:
            self.project.validate()
        # Tag file is optional
        if self.tag_file:
            self.tag_file.validate()
        # Validate ports
        for port, name in [(self.http_port, 'HTTP'), (self.https_port, 'HTTPS')]:
            if not (1 <= port <= 65535):
                raise ValueError(f"{name} port {port} is out of valid range (1-65535)")
        # Validate credentials
        if not self.admin_user:
            raise ValueError("Admin username cannot be empty.")
        if not self.admin_password:
            raise ValueError("Admin password cannot be empty.")
        if not self.gateway_name:
            raise ValueError("Gateway name cannot be empty.")

    def to_dict(self) -> dict:
        """
        Serialize config for templating.
        """
        return {
            'mode': self.mode,
            'backup_file': self.backup.name if self.backup else None,
            'project_name': self.project.name if self.project else None,
            'tag_file': self.tag_file.name if self.tag_file else None,
            'http_port': self.http_port,
            'https_port': self.https_port,
            'admin_user': self.admin_user,
            'admin_pass': self.admin_password,
            'gateway_name': self.gateway_name,
            'edition': self.edition,
            'timezone': self.timezone,
        }