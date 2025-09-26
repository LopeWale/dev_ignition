import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from errors import ConfigBuildError
from models import AutomationGatewayConfig, Backup, ComposeConfig, Project, TagFile
from paths import (
    AUTOMATION_GATEWAY_CONFIGS_DIR,
    AUTOMATION_GATEWAY_TEMPLATES_DIR,
    BACKUPS_DIR,
    GENERATED_DIR,
    JDBC_DIR,
    LOGS_DIR,
    MODULES_DIR,
    PROJECTS_DIR,
    SECRETS_DIR,
    TAGS_DIR,
    TEMPLATES_DIR,
    ensure_runtime_directories,
)

# Setup logger
logger = logging.getLogger(__name__)

ensure_runtime_directories()

ACTIVATION_TOKEN_CONTAINER_PATH = '/run/secrets/ignition/activation-token'
LICENSE_KEY_CONTAINER_PATH = '/run/secrets/ignition/license-key'

def _compose_host_path(path: Path) -> str:
    """Convert a host path into a Docker Compose friendly POSIX string."""

    resolved = path.expanduser().resolve(strict=False)
    return resolved.as_posix()

def _parse_bool(value: Optional[str]) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_optional_int(value: Optional[str], label: str) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ConfigBuildError(f"{label} must be an integer: {exc}") from exc


def _normalise_data_mount(
    source: str, requested_type: Optional[str]
) -> Tuple[str, str, Optional[Path]]:
    cleaned_source = (source or '').strip()
    mount_type = (requested_type or '').strip().lower()
    if not cleaned_source:
        cleaned_source = 'ignition-data'
    if mount_type not in {'volume', 'bind'}:
        candidate = Path(cleaned_source).expanduser()
        if (
            candidate.is_absolute()
            or cleaned_source.startswith('.')
            or '/' in cleaned_source
            or '\\' in cleaned_source
        ):
            mount_type = 'bind'
        else:
            mount_type = 'volume'
    if mount_type == 'bind':
        local_path = Path(cleaned_source).expanduser()
        local_path.mkdir(parents=True, exist_ok=True)
        resolved = local_path.resolve()
        return _compose_host_path(resolved), 'bind', resolved
    return cleaned_source, 'volume', None

def _resolve_optional_path(path_value: Optional[str]) -> Optional[Path]:
    if not path_value:
        return None
    return Path(path_value).expanduser().resolve()


def _resolve_gateway_config_source(path_value: Optional[str]) -> Optional[Path]:
    if not path_value:
        return None
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = AUTOMATION_GATEWAY_CONFIGS_DIR / candidate
    return candidate.resolve()


def _detect_default_secret(relative_name: str) -> Optional[Path]:
    base = SECRETS_DIR / relative_name
    candidates = [base]
    for suffix in ('.txt', '.key', '.lic', '.json'):
        candidates.append(base.with_suffix(suffix))
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    return None


def _has_payload(directory: Path) -> bool:
    for entry in directory.iterdir():
        if entry.name == '.gitkeep':
            continue
        return True
    return False

def _prepare_mount_dir(
    preferred: Optional[Path],
    fallback: Path,
    *,
    force_mount: bool = False,
) -> Optional[Path]:
    if preferred:
        path = preferred.expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    if force_mount or _has_payload(fallback):
        return fallback.resolve()
    return None


def build_config(raw: Dict[str, str]) -> ComposeConfig:
    """Build and validate a ComposeConfig from raw GUI inputs."""

    try:
        logger.debug("Starting ComposeConfig build with raw inputs: %s", raw)

        # Mode
        mode = raw.get('mode', '').lower()
        if mode not in ('clean', 'backup'):
            raise ConfigBuildError(
                f"Invalid mode: '{mode}'. Must be 'clean' or 'backup'."
            )
        logger.info("Mode set to: %s", mode)

        # Backup
        backup: Optional[Backup] = None
        if mode == 'backup':
            backup_name = raw.get('backup_name')
            if not backup_name:
                raise ConfigBuildError(
                    "Mode 'backup' selected, but no backup file provided."
                )
            backup_path = Path(raw.get('backups_dir', 'backups')) / backup_name
            backup = Backup(name=backup_name, path=backup_path)
            backup.validate()
            logger.info("Loaded backup: %s", backup.path)

        # Project
        project: Optional[Project] = None
        project_name = raw.get('project_name')
        if project_name:
            project_path = Path(raw.get('projects_dir', 'projects')) / project_name
            project = Project(name=project_name, path=project_path)
            project.validate()
            logger.info("Loaded project: %s", project.path)

        # Tag File
        tag_file: Optional[TagFile] = None
        tag_name = raw.get('tag_name')
        if tag_name:
            tag_path = Path(raw.get('tags_dir', 'tags')) / tag_name
            tag_file = TagFile(name=tag_name, path=tag_path)
            tag_file.validate()
            logger.info("Loaded tag file: %s", tag_file.path)

        # Ports and other envs
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

        if not admin_user or not admin_pass:
            raise ConfigBuildError(
                "Admin username and password must be provided."
            )
        if not gateway_name:
            raise ConfigBuildError("Gateway name cannot be empty.")

        conn_type = raw.get('conn_type', 'ethernet').strip().lower()
        if conn_type not in {'ethernet', 'serial'}:
            raise ConfigBuildError(
                f"Invalid connection type '{conn_type}'."
            )
        device_ip = raw.get('device_ip', '').strip() or None
        device_port = raw.get('device_port', '').strip()
        if device_port:
            try:
                device_port_int = int(device_port)
            except ValueError as exc:
                raise ConfigBuildError(f"Invalid device port: {exc}") from exc
            device_port = str(device_port_int)
        else:
            device_port = None
        com_port = raw.get('com_port', '').strip() or None
        baud_rate = raw.get('baud_rate', '').strip()
        if baud_rate:
            try:
                baud_rate_int = int(baud_rate)
            except ValueError as exc:
                raise ConfigBuildError(f"Invalid baud rate: {exc}") from exc
            baud_rate = str(baud_rate_int)
        else:
            baud_rate = None

        image_repo = raw.get('image_repo', 'inductiveautomation/ignition').strip()
        if not image_repo:
            image_repo = 'inductiveautomation/ignition'
        image_tag = raw.get('image_tag', 'latest').strip()
        if not image_tag:
            image_tag = 'latest'

        data_mount_source, data_mount_type, data_mount_local = _normalise_data_mount(
            raw.get('data_mount_source', ''),
            raw.get('data_mount_type')
        )

        modules_dir = _resolve_optional_path(raw.get('modules_dir'))
        jdbc_dir = _resolve_optional_path(raw.get('jdbc_dir'))
        if modules_dir:
            modules_dir.mkdir(parents=True, exist_ok=True)
        if jdbc_dir:
            jdbc_dir.mkdir(parents=True, exist_ok=True)

        activation_token_file = (
            _resolve_optional_path(raw.get('activation_token_file'))
            or _detect_default_secret('activation-token')
        )
        license_key_file = (
            _resolve_optional_path(raw.get('license_key_file'))
            or _detect_default_secret('license-key')
        )

        automation_gateway: Optional[AutomationGatewayConfig] = None
        if _parse_bool(raw.get('automation_gateway_enabled')):
            ag_image_repo = (raw.get('automation_gateway_image_repo') or 'rocworks/automation-gateway').strip() or 'rocworks/automation-gateway'
            ag_image_tag = (raw.get('automation_gateway_image_tag') or 'latest').strip() or 'latest'

            graphql_port = _parse_optional_int(
                raw.get('automation_gateway_graphql_port'),
                'Automation Gateway GraphQL port',
            )
            mqtt_port = _parse_optional_int(
                raw.get('automation_gateway_mqtt_port'),
                'Automation Gateway MQTT port',
            )
            mqtt_ws_port = _parse_optional_int(
                raw.get('automation_gateway_mqtt_ws_port'),
                'Automation Gateway MQTT WebSocket port',
            )
            opcua_port = _parse_optional_int(
                raw.get('automation_gateway_opcua_port'),
                'Automation Gateway OPC UA port',
            )

            log_level = (raw.get('automation_gateway_log_level') or 'INFO').strip() or 'INFO'
            config_template = (raw.get('automation_gateway_config_template') or 'default').strip() or 'default'
            ignition_endpoint = (raw.get('automation_gateway_ignition_endpoint') or 'opc.tcp://ignition-dev:62541/discovery').strip()
            config_source = _resolve_gateway_config_source(
                raw.get('automation_gateway_config_source')
            )

            automation_gateway = AutomationGatewayConfig(
                enabled=True,
                image_repo=ag_image_repo,
                image_tag=ag_image_tag,
                graphql_port=graphql_port or 4001,
                mqtt_port=mqtt_port or 1883,
                mqtt_ws_port=mqtt_ws_port or 1884,
                opcua_port=opcua_port or 4841,
                log_level=log_level,
                config_template=config_template,
                ignition_endpoint=ignition_endpoint,
                config_source=config_source,
            )

            logger.info(
                "Automation Gateway enabled with image %s:%s",
                automation_gateway.image_repo,
                automation_gateway.image_tag,
            )

        gateway_modules_enabled = (
            raw.get('gateway_modules_enabled')
            or raw.get('modules_enabled')
        )
        if gateway_modules_enabled:
            gateway_modules_enabled = gateway_modules_enabled.strip() or None

        gateway_module_relink = _parse_bool(
            raw.get('gateway_module_relink') or raw.get('module_relink')
        )
        gateway_jdbc_relink = _parse_bool(
            raw.get('gateway_jdbc_relink') or raw.get('jdbc_relink')
        )

        ignition_uid = _parse_optional_int(raw.get('ignition_uid'), 'IGNITION_UID')
        ignition_gid = _parse_optional_int(raw.get('ignition_gid'), 'IGNITION_GID')

        # ComposeConfig object
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
            timezone=timezone,
            conn_type=conn_type,
            device_ip=device_ip,
            device_port=device_port,
            com_port=com_port,
            baud_rate=baud_rate,
            image_repo=image_repo,
            image_tag=image_tag,
            data_mount_source=data_mount_source,
            data_mount_type=data_mount_type,
            modules_dir=modules_dir,
            jdbc_dir=jdbc_dir,
            data_mount_local=data_mount_local,
            gateway_modules_enabled=gateway_modules_enabled,
            gateway_module_relink=gateway_module_relink,
            gateway_jdbc_relink=gateway_jdbc_relink,
            ignition_uid=ignition_uid,
            ignition_gid=ignition_gid,
            activation_token_file=activation_token_file,
            license_key_file=license_key_file,
            automation_gateway=automation_gateway,
        )
        cfg.validate()
        logger.info("Successfully built ComposeConfig: %s", cfg)
        return cfg

    except Exception as e:
        logger.exception("Failed to build ComposeConfig")
        if isinstance(e, ConfigBuildError):
            raise
        raise ConfigBuildError(str(e), underlying=e)


def render_compose(cfg: ComposeConfig, *, output_dir: Optional[Path] = None) -> Path:
    """Render docker-compose.yml from template into the requested output directory."""

    try:
        target_dir = output_dir or GENERATED_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(['j2'])
        )
        template = env.get_template('docker-compose.yml.j2')

        context = cfg.to_dict()

        automation_gateway_ctx: Optional[Dict[str, object]] = None
        if cfg.automation_gateway and cfg.automation_gateway.enabled:
            ag_dir = target_dir / 'automation-gateway'
            ag_dir.mkdir(parents=True, exist_ok=True)

            config_host_path = ag_dir / cfg.automation_gateway.config_file_name
            cfg.automation_gateway.config_host_path = config_host_path

            automation_gateway_ctx = {
                'service_name': 'automation-gateway',
                'image_repo': cfg.automation_gateway.image_repo,
                'image_tag': cfg.automation_gateway.image_tag,
                'config_host_path': _compose_host_path(config_host_path),
                'config_container_path': cfg.automation_gateway.config_container_path,
                'graphql_port': cfg.automation_gateway.graphql_port,
                'mqtt_port': cfg.automation_gateway.mqtt_port,
                'mqtt_ws_port': cfg.automation_gateway.mqtt_ws_port,
                'opcua_port': cfg.automation_gateway.opcua_port,
                'log_level': cfg.automation_gateway.log_level,
            }

            if cfg.automation_gateway.config_source:
                automation_gateway_ctx['config_source'] = _compose_host_path(
                    cfg.automation_gateway.config_source
                )

        modules_mount = _prepare_mount_dir(
            cfg.modules_dir,
            MODULES_DIR,
            force_mount=bool(cfg.gateway_module_relink or cfg.gateway_modules_enabled),
        )
        jdbc_mount = _prepare_mount_dir(
            cfg.jdbc_dir,
            JDBC_DIR,
            force_mount=cfg.gateway_jdbc_relink,
        )

        volume_mounts: List[Dict[str, object]] = []
        declared_volumes: List[str] = []

        def add_volume(
            volume_type: str,
            source: str,
            target: str,
            *,
            read_only: bool = False,
        ) -> None:
            entry: Dict[str, object] = {
                'type': volume_type,
                'source': source,
                'target': target,
            }
            if read_only:
                entry['read_only'] = True
            volume_mounts.append(entry)

        def add_bind(path: Path, target: str, *, read_only: bool = False) -> None:
            add_volume('bind', _compose_host_path(path), target, read_only=read_only)

        if cfg.data_mount_type == 'volume':
            declared_volumes.append(cfg.data_mount_source)
            add_volume('volume', cfg.data_mount_source, cfg.data_mount_target)
        else:
            if not cfg.data_mount_local:
                raise ConfigBuildError(
                    'Missing bind-mount path for Ignition data directory.'
                )
            add_bind(cfg.data_mount_local, cfg.data_mount_target)

        logs_path = LOGS_DIR.resolve()
        logs_path.mkdir(parents=True, exist_ok=True)
        add_bind(logs_path, '/usr/local/bin/ignition/data/logs')

        if cfg.mode == 'backup' and cfg.backup:
            add_bind(cfg.backup.path.resolve(), '/restore.gwbk', read_only=True)
        else:
            projects_source = PROJECTS_DIR
            if cfg.project:
                projects_source = cfg.project.path.parent

            projects_source.mkdir(parents=True, exist_ok=True)
            add_bind(
                projects_source.resolve(),
                '/usr/local/bin/ignition/data/projects',
            )

        if cfg.tag_file:
            add_bind(cfg.tag_file.path, '/usr/local/bin/ignition/data/init-tags.json', read_only=True)

        if modules_mount:
            add_bind(modules_mount, '/modules')

        if jdbc_mount:
            add_bind(jdbc_mount, '/jdbc')

        if cfg.activation_token_file:
            add_bind(cfg.activation_token_file, ACTIVATION_TOKEN_CONTAINER_PATH, read_only=True)
        if cfg.license_key_file:
            add_bind(cfg.license_key_file, LICENSE_KEY_CONTAINER_PATH, read_only=True)

        context.update({
            'volume_mounts': volume_mounts,
            'declared_volumes': declared_volumes,
        })
        if automation_gateway_ctx:
            base_ag = context.get('automation_gateway', {}) or {}
            base_ag.update(automation_gateway_ctx)
            context['automation_gateway'] = base_ag
        if cfg.activation_token_file:
            context['activation_token_container_path'] = (
                ACTIVATION_TOKEN_CONTAINER_PATH
            )
        if cfg.license_key_file:
            context['license_key_container_path'] = (
                LICENSE_KEY_CONTAINER_PATH
            )

        content = template.render(**context)
        out_path = target_dir / 'docker-compose.yml'
        out_path.write_text(content, encoding='utf-8')
        logger.info("Rendered compose file to %s", out_path)
        return out_path

    except Exception as e:
        logger.exception("Failed to render docker-compose.yml")
        raise ConfigBuildError(
            f"Compose template rendering error: {e}", underlying=e
        )


def render_env(cfg: ComposeConfig, *, output_dir: Optional[Path] = None) -> Path:
    """Render .env file from template into the requested output directory."""

    try:
        target_dir = output_dir or GENERATED_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=False
        )
        template = env.get_template('.env.j2')

        context = cfg.to_dict()
        if cfg.activation_token_file:
            context['activation_token_file'] = ACTIVATION_TOKEN_CONTAINER_PATH
        if cfg.license_key_file:
            context['license_key_file'] = LICENSE_KEY_CONTAINER_PATH

        content = template.render(**context)
        out_path = target_dir / '.env'
        out_path.write_text(content, encoding='utf-8')
        logger.info("Rendered env file to %s", out_path)
        return out_path

    except Exception as e:
        logger.exception("Failed to render .env file")
        raise ConfigBuildError(
            f"Env template rendering error: {e}", underlying=e
        )


def render_automation_gateway_config(
    cfg: ComposeConfig, *, output_dir: Optional[Path] = None
) -> Optional[Path]:
    """Render or copy the Automation Gateway configuration file."""

    if not cfg.automation_gateway or not cfg.automation_gateway.enabled:
        return None

    try:
        target_dir = output_dir or GENERATED_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        config_path = cfg.automation_gateway.config_host_path
        if config_path is None:
            config_dir = target_dir / 'automation-gateway'
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / cfg.automation_gateway.config_file_name
            cfg.automation_gateway.config_host_path = config_path
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)

        if cfg.automation_gateway.config_source:
            shutil.copyfile(cfg.automation_gateway.config_source, config_path)
            logger.info(
                "Copied Automation Gateway config from %s to %s",
                cfg.automation_gateway.config_source,
                config_path,
            )
        else:
            env = Environment(
                loader=FileSystemLoader(str(AUTOMATION_GATEWAY_TEMPLATES_DIR)),
                autoescape=False,
            )
            template = env.get_template('config.yaml.j2')
            content = template.render(
                automation_gateway={
                    'graphql_port': cfg.automation_gateway.graphql_port,
                    'mqtt_port': cfg.automation_gateway.mqtt_port,
                    'mqtt_ws_port': cfg.automation_gateway.mqtt_ws_port,
                    'opcua_port': cfg.automation_gateway.opcua_port,
                    'log_level': cfg.automation_gateway.log_level,
                    'ignition_endpoint': cfg.automation_gateway.ignition_endpoint,
                },
                gateway_name=cfg.gateway_name,
            )
            config_path.write_text(content, encoding='utf-8')
            logger.info("Rendered Automation Gateway config to %s", config_path)

        return config_path

    except Exception as e:  # pragma: no cover - defensive logging
        logger.exception("Failed to render Automation Gateway configuration")
        raise ConfigBuildError(
            f"Automation Gateway config rendering error: {e}", underlying=e
        ) from e


def cleanup_generated_files() -> None:
    """Remove all files in the generated directory."""

    try:
        for file in GENERATED_DIR.iterdir():
            if file.is_file():
                file.unlink()
        logger.info("Cleaned up generated files in %s", GENERATED_DIR)
    except Exception as e:
        logger.exception("Failed to clean up generated files")
        raise ConfigBuildError(f"Cleanup error: {e}", underlying=e)
