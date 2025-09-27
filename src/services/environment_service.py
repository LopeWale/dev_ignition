"""Service responsible for provisioning and tracking Ignition environments."""

from __future__ import annotations

import json
import logging
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
from uuid import uuid4

from compose_generator import (
    build_config,
    render_automation_gateway_config,
    render_compose,
    render_env,
)
from docker_manager import DockerManager, DockerManagerError
from paths import BACKUPS_DIR, BASE_DIR, GENERATED_DIR, PROJECTS_DIR, TAGS_DIR

from models import ComposeConfig

if TYPE_CHECKING:  # pragma: no cover - typing only
    from api.schemas import EnvironmentCreate

logger = logging.getLogger(__name__)


class EnvironmentNotFoundError(Exception):
    """Raised when an environment identifier cannot be resolved."""


@dataclass
class EnvironmentRecord:
    """Internal representation of a provisioned environment."""

    id: str
    display_name: str
    gateway_name: str
    mode: str
    created_at: datetime
    compose_file: Path
    env_file: Path
    http_port: int
    https_port: int
    image_repo: str
    image_tag: str
    data_mount_type: str
    data_mount_source: str
    config: Dict[str, Any]
    status: str = "created"
    last_started_at: Optional[datetime] = None
    last_stopped_at: Optional[datetime] = None
    last_error: Optional[str] = None


    def to_dict(self, base_dir: Path) -> Dict[str, Any]:
        """Serialise to a JSON friendly structure."""

        return {
            "id": self.id,
            "display_name": self.display_name,
            "gateway_name": self.gateway_name,
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "compose_file": _relativise(self.compose_file, base_dir),
            "env_file": _relativise(self.env_file, base_dir),
            "http_port": self.http_port,
            "https_port": self.https_port,
            "image_repo": self.image_repo,
            "image_tag": self.image_tag,
            "data_mount_type": self.data_mount_type,
            "data_mount_source": self.data_mount_source,
            "config": self.config,
            "status": self.status,
            "last_started_at": self.last_started_at.isoformat()
            if self.last_started_at
            else None,
            "last_stopped_at": self.last_stopped_at.isoformat()
            if self.last_stopped_at
            else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Path) -> "EnvironmentRecord":
        """Rehydrate a record from persisted JSON."""

        compose_file = Path(data["compose_file"])
        if not compose_file.is_absolute():
            compose_file = base_dir / compose_file

        env_file = Path(data["env_file"])
        if not env_file.is_absolute():
            env_file = base_dir / env_file

        created_at = datetime.fromisoformat(data["created_at"])

        return cls(
            id=data["id"],
            display_name=data["display_name"],
            gateway_name=data["gateway_name"],
            mode=data["mode"],
            created_at=created_at,
            compose_file=compose_file,
            env_file=env_file,
            http_port=int(data["http_port"]),
            https_port=int(data["https_port"]),
            image_repo=data["image_repo"],
            image_tag=data["image_tag"],
            data_mount_type=data["data_mount_type"],
            data_mount_source=data["data_mount_source"],
            config=data.get("config", {}),
            status=data.get("status", "created"),
            last_started_at=datetime.fromisoformat(data["last_started_at"])
            if data.get("last_started_at")
            else None,
            last_stopped_at=datetime.fromisoformat(data["last_stopped_at"])
            if data.get("last_stopped_at")
            else None,
            last_error=data.get("last_error"),
        )


def _relativise(path: Path, base_dir: Path) -> str:
    """Return a POSIX-style path relative to the base directory when possible."""

    try:
        relative = path.resolve().relative_to(base_dir.resolve())
        return relative.as_posix()
    except ValueError:
        return path.as_posix()


def _stringify_optional_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    return _relativise(path, BASE_DIR)


class EnvironmentService:
    """Coordinates Compose generation and persistence of environment metadata."""

    def __init__(
        self,
        *,
        docker_manager_factory: Optional[
            Callable[[Path, Optional[Path]], DockerManager]
        ] = None,
    ) -> None:

        self._lock = threading.Lock()
        self._root = GENERATED_DIR / "environments"
        self._registry_path = self._root / "registry.json"
        self._root.mkdir(parents=True, exist_ok=True)
        self._docker_manager_factory = (
            docker_manager_factory or self._default_docker_manager_factory
        )

        logger.debug("EnvironmentService initialised with root %s", self._root)

    # Public API -----------------------------------------------------------------
    def list_environments(self) -> List[EnvironmentRecord]:
        """Return all known environments."""

        with self._lock:
            return list(self._load_records())

    def get_environment(self, env_id: str) -> EnvironmentRecord:
        """Fetch a single environment by identifier."""

        with self._lock:
            for record in self._load_records():
                if record.id == env_id:
                    return record
        raise EnvironmentNotFoundError(env_id)

    def create_environment(self, payload: "EnvironmentCreate") -> EnvironmentRecord:
        """Render Compose artifacts for the provided request and persist metadata."""

        raw_config = payload.to_raw_config(
            backups_dir=str(BACKUPS_DIR),
            projects_dir=str(PROJECTS_DIR),
            tags_dir=str(TAGS_DIR),
        )
        cfg = build_config(raw_config)

        display_name = payload.display_name or cfg.gateway_name
        env_id = uuid4().hex
        env_dir = self._root / env_id

        with self._lock:
            env_dir.mkdir(parents=True, exist_ok=True)
            compose_path = render_compose(cfg, output_dir=env_dir)
            env_path = render_env(cfg, output_dir=env_dir)
            render_automation_gateway_config(cfg, output_dir=env_dir)

            record = EnvironmentRecord(
                id=env_id,
                display_name=display_name,
                gateway_name=cfg.gateway_name,
                mode=cfg.mode,
                created_at=datetime.now(timezone.utc),
                compose_file=compose_path,
                env_file=env_path,
                http_port=cfg.http_port,
                https_port=cfg.https_port,
                image_repo=cfg.image_repo,
                image_tag=cfg.image_tag,
                data_mount_type=cfg.data_mount_type,
                data_mount_source=cfg.data_mount_source,
                config=self._sanitise_config(cfg),
                status="created",
            )

            records = self._load_records()
            records.append(record)
            self._save_records(records)

        logger.info("Provisioned environment %s -> %s", env_id, compose_path)
        return record

    def delete_environment(self, env_id: str) -> None:
        """Remove an environment and its generated artifacts."""

        with self._lock:
            records = self._load_records()
            remaining: List[EnvironmentRecord] = []
            target: Optional[EnvironmentRecord] = None
            for record in records:
                if record.id == env_id:
                    target = record
                else:
                    remaining.append(record)

            if target is None:
                raise EnvironmentNotFoundError(env_id)

            self._save_records(remaining)

        env_dir = target.compose_file.parent
        try:
            env_dir.relative_to(self._root)
        except ValueError:
            logger.warning(
                "Refusing to delete environment directory outside the root: %s",
                env_dir,
            )
            return

        shutil.rmtree(env_dir, ignore_errors=True)
        logger.info("Deleted environment %s and cleaned up %s", env_id, env_dir)

    def start_environment(
        self,
        env_id: str,
        *,
        wait_for_gateway: bool = False,
        wait_timeout: int = 60,
    ) -> EnvironmentRecord:
        """Start an environment using docker compose and update its status."""

        record = self._transition(env_id, status="starting", clear_error=True)

        manager = self._docker_manager_factory(record.compose_file, record.env_file)
        logger.info("Starting environment %s", env_id)
        try:
            manager.up_detached()
            if wait_for_gateway and not manager.wait_for_gateway(
                record.http_port, timeout=wait_timeout
            ):
                raise DockerManagerError(
                    "Gateway did not become healthy within the allotted timeout."
                )
        except DockerManagerError as exc:
            logger.exception("Failed to start environment %s", env_id)
            self._transition(env_id, status="error", last_error=str(exc))
            raise
        except Exception as exc:
            logger.exception("Unexpected failure starting environment %s", env_id)
            self._transition(env_id, status="error", last_error=str(exc))
            raise DockerManagerError(
                "Unexpected error while starting docker compose stack.",
                underlying=exc,
            ) from exc

        now = datetime.now(timezone.utc)
        return self._transition(
            env_id,
            status="running",
            last_started_at=now,
            last_error=None,
        )

    def stop_environment(self, env_id: str) -> EnvironmentRecord:
        """Stop a running environment via docker compose and update its status."""

        record = self._transition(env_id, status="stopping")

        manager = self._docker_manager_factory(record.compose_file, record.env_file)
        logger.info("Stopping environment %s", env_id)
        try:
            manager.down()
        except DockerManagerError as exc:
            logger.exception("Failed to stop environment %s", env_id)
            self._transition(env_id, status="error", last_error=str(exc))
            raise
        except Exception as exc:
            logger.exception("Unexpected failure stopping environment %s", env_id)
            self._transition(env_id, status="error", last_error=str(exc))
            raise DockerManagerError(
                "Unexpected error while stopping docker compose stack.",
                underlying=exc,
            ) from exc

        now = datetime.now(timezone.utc)
        return self._transition(
            env_id,
            status="stopped",
            last_stopped_at=now,
            last_error=None,
        )

    # Serialisation helpers -------------------------------------------------------
    def to_summary_payload(self, record: EnvironmentRecord) -> Dict[str, Any]:
        """Convert a record into a serialisable structure for the API layer."""

        base = record.to_dict(BASE_DIR)
        return {
            "id": base["id"],
            "display_name": base["display_name"],
            "gateway_name": base["gateway_name"],
            "mode": base["mode"],
            "created_at": record.created_at,
            "http_port": record.http_port,
            "https_port": record.https_port,
            "image_repo": record.image_repo,
            "image_tag": record.image_tag,
            "data_mount_type": record.data_mount_type,
            "data_mount_source": record.data_mount_source,
            "compose_file": base["compose_file"],
            "env_file": base["env_file"],
            "status": record.status,
            "last_started_at": record.last_started_at,
            "last_stopped_at": record.last_stopped_at,
            "last_error": record.last_error,

        }

    def to_detail_payload(self, record: EnvironmentRecord) -> Dict[str, Any]:
        """Expand a record with its sanitised configuration."""

        payload = self.to_summary_payload(record)
        payload["config"] = record.config
        return payload

    # Internal helpers -----------------------------------------------------------
    def _load_records(self) -> List[EnvironmentRecord]:
        if not self._registry_path.exists():
            return []

        try:
            raw = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.exception("Failed to decode environment registry %s", self._registry_path)
            return []

        entries: List[Dict[str, Any]]
        if isinstance(raw, dict) and "environments" in raw:
            entries = raw.get("environments", [])
        elif isinstance(raw, list):
            entries = raw
        else:
            logger.warning("Unexpected registry payload: %s", type(raw))
            return []

        records: List[EnvironmentRecord] = []
        for entry in entries:
            try:
                records.append(EnvironmentRecord.from_dict(entry, BASE_DIR))
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Skipping malformed registry entry: %s", entry)
        return records

    def _save_records(self, records: List[EnvironmentRecord]) -> None:
        data = [record.to_dict(BASE_DIR) for record in records]
        payload = {"environments": data}
        tmp_path = self._registry_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(self._registry_path)

    def _sanitise_config(self, cfg: ComposeConfig) -> Dict[str, Any]:
        return {
            "mode": cfg.mode,
            "http_port": cfg.http_port,
            "https_port": cfg.https_port,
            "admin_user": cfg.admin_user,
            "gateway_name": cfg.gateway_name,
            "edition": cfg.edition,
            "timezone": cfg.timezone,
            "conn_type": cfg.conn_type,
            "device_ip": cfg.device_ip,
            "device_port": cfg.device_port,
            "com_port": cfg.com_port,
            "baud_rate": cfg.baud_rate,
            "image_repo": cfg.image_repo,
            "image_tag": cfg.image_tag,
            "data_mount_type": cfg.data_mount_type,
            "data_mount_source": cfg.data_mount_source,
            "data_mount_target": cfg.data_mount_target,
            "data_mount_local": _stringify_optional_path(cfg.data_mount_local),
            "modules_dir": _stringify_optional_path(cfg.modules_dir),
            "jdbc_dir": _stringify_optional_path(cfg.jdbc_dir),
            "gateway_modules_enabled": cfg.gateway_modules_enabled,
            "gateway_module_relink": cfg.gateway_module_relink,
            "gateway_jdbc_relink": cfg.gateway_jdbc_relink,
            "ignition_uid": cfg.ignition_uid,
            "ignition_gid": cfg.ignition_gid,
            "activation_token_file": _stringify_optional_path(cfg.activation_token_file),
            "license_key_file": _stringify_optional_path(cfg.license_key_file),
            "project_name": cfg.project.name if cfg.project else None,
            "tag_name": cfg.tag_file.name if cfg.tag_file else None,
            "backup_name": cfg.backup.name if cfg.backup else None,
            "automation_gateway": self._automation_gateway_snapshot(cfg),
        }

    def _automation_gateway_snapshot(
        self, cfg: ComposeConfig
    ) -> Optional[Dict[str, Any]]:
        if not cfg.automation_gateway:
            return None

        ag = cfg.automation_gateway
        return {
            "enabled": ag.enabled,
            "image_repo": ag.image_repo,
            "image_tag": ag.image_tag,
            "graphql_port": ag.graphql_port,
            "mqtt_port": ag.mqtt_port,
            "mqtt_ws_port": ag.mqtt_ws_port,
            "opcua_port": ag.opcua_port,
            "log_level": ag.log_level,
            "ignition_endpoint": ag.ignition_endpoint,
            "config_template": ag.config_template,
            "config_source": _stringify_optional_path(ag.config_source),
            "config_file": _stringify_optional_path(ag.config_host_path),
            "config_container_path": ag.config_container_path,
        }

    def _default_docker_manager_factory(
        self, compose_path: Path, env_path: Optional[Path]
    ) -> DockerManager:
        return DockerManager(compose_file=compose_path, env_file=env_path)

    _UNSET = object()

    def _transition(
        self,
        env_id: str,
        *,
        status: Optional[str] = None,
        last_started_at: Optional[datetime] = None,
        last_stopped_at: Optional[datetime] = None,
        last_error: object = _UNSET,
        clear_error: bool = False,
    ) -> EnvironmentRecord:
        """Update a record with the provided fields and persist the registry."""

        with self._lock:
            records = self._load_records()
            target: Optional[EnvironmentRecord] = None
            for record in records:
                if record.id == env_id:
                    target = record
                    break

            if target is None:
                raise EnvironmentNotFoundError(env_id)

            if status is not None:
                target.status = status
            if last_started_at is not None:
                target.last_started_at = last_started_at
            if last_stopped_at is not None:
                target.last_stopped_at = last_stopped_at
            if clear_error:
                target.last_error = None
            elif last_error is not self._UNSET:
                target.last_error = last_error

            self._save_records(records)

            return target
