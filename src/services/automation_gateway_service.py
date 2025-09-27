"""Automation Gateway specific service helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from models import AutomationGatewayConfig
from paths import AUTOMATION_GATEWAY_TEMPLATES_DIR, BASE_DIR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateMetadata:
    """Describes Automation Gateway templates discovered on disk."""

    name: str
    filename: str
    exists: bool
    relative_path: Optional[str]
    description: Optional[str]
    is_default: bool


@dataclass(frozen=True)
class TemplateDetail(TemplateMetadata):
    """Extends :class:`TemplateMetadata` with the template contents."""

    content: str


class AutomationGatewayService:
    """Surface Automation Gateway metadata for the API layer."""

    def __init__(self, templates_dir: Path = AUTOMATION_GATEWAY_TEMPLATES_DIR) -> None:
        self._templates_dir = Path(templates_dir)

    def list_templates(self) -> List[TemplateMetadata]:
        """Return metadata for known Automation Gateway templates."""

        names = sorted(AutomationGatewayConfig.available_templates(self._templates_dir))
        return [self._build_metadata(name) for name in names]

    def get_template_detail(self, template_name: str) -> TemplateDetail:
        """Return full template metadata and contents for ``template_name``."""

        name = self._normalise_template_name(template_name)
        available = AutomationGatewayConfig.available_templates(self._templates_dir)
        if name not in available:
            choices = ", ".join(sorted(available)) or "none"
            raise ValueError(
                "Unknown Automation Gateway template "
                f"'{name}'. Available templates: {choices}."
            )

        metadata = self._build_metadata(name)
        if not metadata.exists:
            raise FileNotFoundError(
                f"Automation Gateway template not found on disk: {metadata.filename}"
            )

        path = self._template_path(name)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Unable to read template %s: %s", path, exc)
            raise

        return TemplateDetail(
            name=metadata.name,
            filename=metadata.filename,
            exists=metadata.exists,
            relative_path=metadata.relative_path,
            description=metadata.description,
            is_default=metadata.is_default,
            content=content,
        )

    def _extract_description(self, path: Path) -> Optional[str]:
        """Parse leading comments from a template file to form a description."""

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:  # pragma: no cover - file access failure is logged and ignored
            logger.warning("Unable to read template %s: %s", path, exc)
            return None

        description_lines: List[str] = []
        seen_content = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if description_lines:
                    break
                continue
            if not stripped.startswith("#"):
                seen_content = True
                break

            content = stripped.lstrip("#").strip()
            if not content:
                continue
            if "automation_gateway/templates/" in content:
                continue
            description_lines.append(content)

        if not description_lines and not seen_content:
            # File contains only comments; join them all.
            description_lines = [
                stripped.lstrip("#").strip()
                for stripped in (line.strip() for line in lines if line.strip().startswith("#"))
                if stripped
            ]

        if not description_lines:
            return None

        return " ".join(description_lines)

    def _build_metadata(self, name: str) -> TemplateMetadata:
        filename = f"{name}{AutomationGatewayConfig.TEMPLATE_SUFFIX}"
        path = self._template_path(name)
        exists = path.is_file()
        relative_path = None
        description = None

        if exists:
            try:
                relative_path = path.resolve().relative_to(BASE_DIR).as_posix()
            except ValueError:  # pragma: no cover - defensive guard for unexpected layout
                relative_path = path.resolve().as_posix()
            description = self._extract_description(path)
        else:
            logger.debug(
                "Automation Gateway template '%s' does not exist at %s", name, path
            )

        return TemplateMetadata(
            name=name,
            filename=filename,
            exists=exists,
            relative_path=relative_path,
            description=description,
            is_default=name == "default",
        )

    def _template_path(self, name: str) -> Path:
        return self._templates_dir / f"{name}{AutomationGatewayConfig.TEMPLATE_SUFFIX}"

    def _normalise_template_name(self, template_name: str) -> str:
        name = (template_name or "").strip()
        if not name:
            raise ValueError("Template name cannot be blank.")
        if any(sep in name for sep in ("/", "\\")) or ".." in name:
            raise ValueError("Template name cannot contain path separators or traversal sequences.")
        return name


__all__ = [
    "AutomationGatewayService",
    "TemplateDetail",
    "TemplateMetadata",
]
