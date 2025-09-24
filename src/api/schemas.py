"""Pydantic schemas used by the public FastAPI surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    field_validator,
)


class EnvironmentCreate(BaseModel):
    """Request body for provisioning a new Ignition environment."""

    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(
        default=None,
        description="Human-friendly label for the environment.",
        max_length=100,
    )
    mode: Literal["clean", "backup"] = Field(
        default="clean",
        description="Provision either a clean gateway or restore from a backup.",
    )
    backup_name: Optional[str] = Field(
        default=None,
        description="File name of the `.gwbk` backup located in the backups directory.",
        max_length=255,
    )
    project_name: Optional[str] = Field(
        default=None,
        description="Project folder located under the projects directory.",
        max_length=255,
    )
    tag_name: Optional[str] = Field(
        default=None,
        description="Tag export file name located under the tags directory.",
        max_length=255,
    )
    http_port: int = Field(default=8088, ge=1, le=65535)
    https_port: int = Field(default=8043, ge=1, le=65535)
    admin_user: str = Field(
        description="Gateway admin username.",
        min_length=1,
        max_length=128,
    )
    admin_password: str = Field(
        description="Gateway admin password.",
        min_length=8,
        max_length=256,
    )
    gateway_name: str = Field(
        description="Gateway instance name registered with Ignition.",
        min_length=1,
        max_length=128,
    )
    edition: str = Field(default="standard", min_length=1, max_length=128)
    timezone: str = Field(default="America/Chicago", min_length=1, max_length=128)
    conn_type: Literal["ethernet", "serial"] = Field(default="ethernet")
    device_ip: Optional[IPvAnyAddress] = Field(default=None)
    device_port: Optional[int] = Field(default=None, gt=0, lt=65536)
    com_port: Optional[str] = Field(default=None, max_length=64)
    baud_rate: Optional[int] = Field(default=None, gt=0)
    image_repo: str = Field(default="inductiveautomation/ignition", min_length=1, max_length=255)
    image_tag: str = Field(default="latest", min_length=1, max_length=128)
    data_mount_source: Optional[str] = Field(default=None, max_length=500)
    data_mount_type: Literal["volume", "bind"] = Field(default="volume")
    data_mount_target: str = Field(default="/data", min_length=1, max_length=255)
    modules_dir: Optional[str] = Field(default=None, max_length=500)
    jdbc_dir: Optional[str] = Field(default=None, max_length=500)
    gateway_modules_enabled: Optional[str] = Field(default=None, max_length=500)
    gateway_module_relink: bool = Field(default=False)
    gateway_jdbc_relink: bool = Field(default=False)
    ignition_uid: Optional[int] = Field(default=None, ge=0)
    ignition_gid: Optional[int] = Field(default=None, ge=0)
    activation_token_file: Optional[str] = Field(default=None, max_length=500)
    license_key_file: Optional[str] = Field(default=None, max_length=500)

    @field_validator(
        "display_name",
        "backup_name",
        "project_name",
        "tag_name",
        "data_mount_source",
        "modules_dir",
        "jdbc_dir",
        "gateway_modules_enabled",
        "com_port",
        "activation_token_file",
        "license_key_file",
        mode="before",
    )
    @classmethod
    def _clean_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @field_validator(
        "admin_user",
        "gateway_name",
        "edition",
        "timezone",
        "image_repo",
        "image_tag",
        "data_mount_target",
        mode="before",
    )
    @classmethod
    def _clean_required(cls, value: str) -> str:
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("Value cannot be blank.")
            return trimmed
        return value

    @field_validator("admin_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Admin password cannot be blank.")
        return value

    @field_validator("device_port", "baud_rate")
    @classmethod
    def _validate_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("Value must be positive.")
        return value

    @field_validator("ignition_uid", "ignition_gid")
    @classmethod
    def _validate_non_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 0:
            raise ValueError("Value must be zero or positive.")
        return value

    @field_validator("http_port", "https_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("Port must be within the TCP range 1-65535.")
        return value

    @field_validator("data_mount_type")
    @classmethod
    def _validate_data_mount_type(cls, value: str) -> str:
        if value not in {"volume", "bind"}:
            raise ValueError("Data mount type must be either 'volume' or 'bind'.")
        return value

    @field_validator("data_mount_source")
    @classmethod
    def _ensure_data_source_when_bind(
        cls, value: Optional[str], values: Dict[str, Any]
    ) -> Optional[str]:
        mount_type = values.get("data_mount_type")
        if mount_type == "bind" and not value:
            raise ValueError("Bind mounts must provide a host path for data_mount_source.")
        return value

    @field_validator("backup_name")
    @classmethod
    def _ensure_backup_when_needed(
        cls, value: Optional[str], values: Dict[str, Any]
    ) -> Optional[str]:
        mode = values.get("mode", "clean")
        if mode == "backup" and not value:
            raise ValueError("backup_name is required when mode is 'backup'.")
        return value

    def to_raw_config(
        self,
        *,
        backups_dir: str,
        projects_dir: str,
        tags_dir: str,
    ) -> Dict[str, Any]:
        """Translate the request payload into the raw dictionary expected by build_config."""

        raw: Dict[str, Any] = {
            "mode": self.mode,
            "backup_name": self.backup_name,
            "project_name": self.project_name,
            "tag_name": self.tag_name,
            "http_port": self.http_port,
            "https_port": self.https_port,
            "admin_user": self.admin_user,
            "admin_pass": self.admin_password,
            "gateway_name": self.gateway_name,
            "edition": self.edition,
            "timezone": self.timezone,
            "conn_type": self.conn_type,
            "device_ip": str(self.device_ip) if self.device_ip else "",
            "device_port": str(self.device_port) if self.device_port else "",
            "com_port": self.com_port or "",
            "baud_rate": str(self.baud_rate) if self.baud_rate else "",
            "image_repo": self.image_repo,
            "image_tag": self.image_tag,
            "data_mount_source": self.data_mount_source or "",
            "data_mount_type": self.data_mount_type,
            "modules_dir": self.modules_dir,
            "jdbc_dir": self.jdbc_dir,
            "gateway_modules_enabled": self.gateway_modules_enabled,
            "gateway_module_relink": self.gateway_module_relink,
            "gateway_jdbc_relink": self.gateway_jdbc_relink,
            "ignition_uid": self.ignition_uid,
            "ignition_gid": self.ignition_gid,
            "activation_token_file": self.activation_token_file,
            "license_key_file": self.license_key_file,
            "backups_dir": backups_dir,
            "projects_dir": projects_dir,
            "tags_dir": tags_dir,
        }
        return raw


class EnvironmentConfigSnapshot(BaseModel):
    """Sanitised view of the Compose configuration without secrets."""

    mode: Literal["clean", "backup"]
    http_port: int
    https_port: int
    admin_user: str
    gateway_name: str
    edition: str
    timezone: str
    conn_type: Literal["ethernet", "serial"]
    device_ip: Optional[str]
    device_port: Optional[str]
    com_port: Optional[str]
    baud_rate: Optional[str]
    image_repo: str
    image_tag: str
    data_mount_type: Literal["volume", "bind"]
    data_mount_source: str
    data_mount_target: str
    data_mount_local: Optional[str]
    modules_dir: Optional[str]
    jdbc_dir: Optional[str]
    gateway_modules_enabled: Optional[str]
    gateway_module_relink: bool
    gateway_jdbc_relink: bool
    ignition_uid: Optional[int]
    ignition_gid: Optional[int]
    activation_token_file: Optional[str]
    license_key_file: Optional[str]
    project_name: Optional[str]
    tag_name: Optional[str]
    backup_name: Optional[str]


class EnvironmentSummary(BaseModel):
    """Lightweight representation used by list endpoints."""

    id: str
    display_name: str
    gateway_name: str
    mode: Literal["clean", "backup"]
    created_at: datetime
    http_port: int
    https_port: int
    image_repo: str
    image_tag: str
    data_mount_type: Literal["volume", "bind"]
    data_mount_source: str
    compose_file: str
    env_file: str


class EnvironmentDetail(EnvironmentSummary):
    """Full representation that includes the sanitised configuration."""

    config: EnvironmentConfigSnapshot


class EnvironmentList(BaseModel):
    """Wrapper used to document the collection payload."""

    items: List[EnvironmentSummary]


class ErrorMessage(BaseModel):
    """Consistent error envelope for API responses."""

    detail: str
