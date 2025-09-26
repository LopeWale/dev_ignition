from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal, ClassVar

from paths import AUTOMATION_GATEWAY_TEMPLATES_DIR

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
class AutomationGatewayConfig:
    """Runtime settings for the Automation Gateway sidecar."""

    TEMPLATE_SUFFIX: ClassVar[str] = ".yaml.j2"

    enabled: bool = False
    image_repo: str = "rocworks/automation-gateway"
    image_tag: str = "latest"
    graphql_port: int = 4001
    mqtt_port: int = 1883
    mqtt_ws_port: int = 1884
    opcua_port: int = 4841
    log_level: str = "INFO"
    config_template: str = "default"
    ignition_endpoint: str = "opc.tcp://ignition-dev:62541/discovery"
    config_container_path: str = "/app/config.yaml"
    config_file_name: str = "config.yaml"
    config_source: Optional[Path] = None
    config_host_path: Optional[Path] = None

    def validate(self) -> None:
        if not self.enabled:
            return

        for port, label in (
            (self.graphql_port, "GraphQL"),
            (self.mqtt_port, "MQTT"),
            (self.mqtt_ws_port, "MQTT WebSocket"),
            (self.opcua_port, "OPC UA"),
        ):
            if not (1 <= port <= 65535):
                raise ValueError(
                    f"Automation Gateway {label} port {port} is out of range (1-65535)"
                )

        if not self.image_repo:
            raise ValueError("Automation Gateway image repository cannot be empty.")
        if not self.image_tag:
            raise ValueError("Automation Gateway image tag cannot be empty.")
        if not self.log_level:
            raise ValueError("Automation Gateway log level cannot be empty.")
        if not self.ignition_endpoint:
            raise ValueError("Automation Gateway Ignition endpoint cannot be empty.")

        template = (self.config_template or "").strip() or "default"
        if any(sep in template for sep in ("/", "\\")) or ".." in template:
            raise ValueError(
                "Automation Gateway config template must be a simple name without path separators."
            )

        self.config_template = template

        if self.config_source is None:
            available = self.available_templates()
            if template not in available:
                choices = ", ".join(sorted(available)) if available else "none"
                raise ValueError(
                    "Unsupported Automation Gateway config template "
                    f"'{self.config_template}'. Available templates: {choices}."
                )

            template_path = self.template_path()
            if not template_path.is_file():
                raise FileNotFoundError(
                    f"Automation Gateway template not found: {template_path}"
                )

        if self.config_source and not self.config_source.is_file():
            raise FileNotFoundError(
                f"Automation Gateway config source not found: {self.config_source}"
            )

    def to_template_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'image_repo': self.image_repo,
            'image_tag': self.image_tag,
            'graphql_port': self.graphql_port,
            'mqtt_port': self.mqtt_port,
            'mqtt_ws_port': self.mqtt_ws_port,
            'opcua_port': self.opcua_port,
            'log_level': self.log_level,
            'config_template': self.config_template,
            'ignition_endpoint': self.ignition_endpoint,
            'config_container_path': self.config_container_path,
            'config_file_name': self.config_file_name,
        }

    @classmethod
    def available_templates(cls) -> set[str]:
        templates: set[str] = set()
        if AUTOMATION_GATEWAY_TEMPLATES_DIR.exists():
            for path in AUTOMATION_GATEWAY_TEMPLATES_DIR.glob(f"*{cls.TEMPLATE_SUFFIX}"):
                name = cls._template_name_from_filename(path.name)
                if name:
                    templates.add(name)
        if "default" not in templates:
            templates.add("default")
        return templates

    @staticmethod
    def _template_name_from_filename(filename: str) -> Optional[str]:
        parts = filename.split('.')
        if len(parts) < 3:
            return None
        if parts[-2:] != ['yaml', 'j2']:
            return None
        return '.'.join(parts[:-2])

    def template_filename(self) -> str:
        return f"{self.config_template}{self.TEMPLATE_SUFFIX}"

    def template_path(self) -> Path:
        return AUTOMATION_GATEWAY_TEMPLATES_DIR / self.template_filename()

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
    conn_type: Literal['ethernet', 'serial'] = 'ethernet'
    device_ip: Optional[str] = None
    device_port: Optional[str] = None
    com_port: Optional[str] = None
    baud_rate: Optional[str] = None
    image_repo: str = 'inductiveautomation/ignition'
    image_tag: str = 'latest'
    data_mount_source: str = 'ignition-data'
    data_mount_type: Literal['volume', 'bind'] = 'volume'
    data_mount_target: str = '/data'
    data_mount_local: Optional[Path] = None
    modules_dir: Optional[Path] = None
    jdbc_dir: Optional[Path] = None
    gateway_modules_enabled: Optional[str] = None
    gateway_module_relink: bool = False
    gateway_jdbc_relink: bool = False
    ignition_uid: Optional[int] = None
    ignition_gid: Optional[int] = None
    activation_token_file: Optional[Path] = None
    license_key_file: Optional[Path] = None
    automation_gateway: Optional[AutomationGatewayConfig] = None

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
        if self.conn_type not in ('ethernet', 'serial'):
            raise ValueError(
                f"Invalid connection type '{self.conn_type}'."
            )
        if self.conn_type == 'ethernet':
            if self.device_ip and not self.device_port:
                raise ValueError("Device port must be provided when device IP is set.")
        if self.conn_type == 'serial' and not self.com_port:
            raise ValueError("Serial connections require a COM port to be specified.")
        if self.data_mount_type not in ('volume', 'bind'):
            raise ValueError(
                f"Invalid data_mount_type '{self.data_mount_type}'. Use 'volume' or 'bind'."
            )
        if self.data_mount_type == 'bind':
            if not self.data_mount_local:
                raise ValueError(
                    "Data mount local path must be provided when using a bind mount."
                )
            data_source_path = self.data_mount_local

            if not data_source_path.exists():
                raise FileNotFoundError(
                    f"Data mount source not found: {data_source_path}"
                )
            if not data_source_path.is_dir():
                raise ValueError(
                    f"Data mount source must be a directory: {data_source_path}"
                )
        for folder, label in (
            (self.modules_dir, 'Modules directory'),
            (self.jdbc_dir, 'JDBC directory'),
        ):
            if folder and not folder.exists():
                raise FileNotFoundError(f"{label} not found: {folder}")
        for file_path, label in (
            (self.activation_token_file, 'Activation token file'),
            (self.license_key_file, 'License key file'),
        ):
            if file_path and not file_path.is_file():
                raise FileNotFoundError(f"{label} not found: {file_path}")
        for value, label in (
            (self.ignition_uid, 'IGNITION_UID'),
            (self.ignition_gid, 'IGNITION_GID'),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} must be a positive integer.")

        if self.automation_gateway:
            self.automation_gateway.validate()

    def to_dict(self) -> dict:
        """
        Serialize config for templating.
        """
        data = {
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
            'conn_type': self.conn_type,
            'device_ip': self.device_ip,
            'device_port': self.device_port,
            'com_port': self.com_port,
            'baud_rate': self.baud_rate,
            'image_repo': self.image_repo,
            'image_tag': self.image_tag,
            'data_mount_source': self.data_mount_source,
            'data_mount_type': self.data_mount_type,
            'data_mount_target': self.data_mount_target,
            'gateway_modules_enabled': self.gateway_modules_enabled,
            'gateway_module_relink': self.gateway_module_relink,
            'gateway_jdbc_relink': self.gateway_jdbc_relink,
            'ignition_uid': self.ignition_uid,
            'ignition_gid': self.ignition_gid,
            'activation_token_file': str(self.activation_token_file) if self.activation_token_file else None,
            'license_key_file': str(self.license_key_file) if self.license_key_file else None,
        }
        if self.modules_dir:
            data['modules_dir'] = str(self.modules_dir)
        if self.jdbc_dir:
            data['jdbc_dir'] = str(self.jdbc_dir)
        if self.automation_gateway:
            data['automation_gateway'] = self.automation_gateway.to_template_dict()
        return data
