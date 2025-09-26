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
    """Describes a rendered Automation Gateway template on disk."""

    name: str
    filename: str
    exists: bool
    relative_path: Optional[str]
    description: Optional[str]
    is_default: bool


class AutomationGatewayService:
    """Surface Automation Gateway metadata for the API layer."""

    def __init__(self, templates_dir: Path = AUTOMATION_GATEWAY_TEMPLATES_DIR) -> None:
        self._templates_dir = Path(templates_dir)

    def list_templates(self) -> List[TemplateMetadata]:
        """Return metadata for known Automation Gateway templates."""

        names = sorted(AutomationGatewayConfig.available_templates(self._templates_dir))
        metadata: List[TemplateMetadata] = []

        for name in names:
            filename = f"{name}{AutomationGatewayConfig.TEMPLATE_SUFFIX}"
            path = self._templates_dir / filename
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

            metadata.append(
                TemplateMetadata(
                    name=name,
                    filename=filename,
                    exists=exists,
                    relative_path=relative_path,
                    description=description,
                    is_default=name == "default",
                )
            )

        return metadata

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


__all__ = [
    "AutomationGatewayService",
    "TemplateMetadata",
]
