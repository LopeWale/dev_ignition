import sys
from pathlib import Path

import pytest
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from compose_generator import (  # noqa: E402
    build_config,
    render_automation_gateway_config,
    render_compose,
)
from errors import ConfigBuildError  # noqa: E402
from models import AutomationGatewayConfig  # noqa: E402


def _volume_by_target(compose_data, target: str):
    volumes = compose_data["services"]["ignition-dev"]["volumes"]
    for volume in volumes:
        if volume["target"] == target:
            return volume
    raise AssertionError(f"Missing volume mount for target {target}")


def test_render_compose_uses_project_parent(tmp_path):
    project_root = tmp_path / "custom_projects"
    project_dir = project_root / "DemoProject"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    raw = {
        "mode": "clean",
        "project_name": "DemoProject",
        "projects_dir": str(project_root),
        "admin_user": "admin",
        "admin_pass": "secure-pass-123",
        "gateway_name": "demo-gateway",
        "data_mount_type": "volume",
    }

    cfg = build_config(raw)
    output_dir = tmp_path / "artifacts"
    compose_path = render_compose(cfg, output_dir=output_dir)

    compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    projects_volume = _volume_by_target(
        compose_data, "/usr/local/bin/ignition/data/projects"
    )

    assert Path(projects_volume["source"]) == project_root.resolve()


def test_render_compose_defaults_to_repository_projects(tmp_path):
    raw = {
        "mode": "clean",
        "admin_user": "admin",
        "admin_pass": "secure-pass-123",
        "gateway_name": "demo-gateway",
        "data_mount_type": "volume",
    }

    cfg = build_config(raw)
    compose_path = render_compose(cfg, output_dir=tmp_path)
    compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    projects_volume = _volume_by_target(
        compose_data, "/usr/local/bin/ignition/data/projects"
    )

    from paths import PROJECTS_DIR  # Imported lazily to avoid circular import during tests

    assert Path(projects_volume["source"]) == PROJECTS_DIR.resolve()


def test_render_compose_with_automation_gateway(tmp_path):
    raw = {
        "mode": "clean",
        "admin_user": "admin",
        "admin_pass": "secure-pass-123",
        "gateway_name": "demo-gateway",
        "data_mount_type": "volume",
        "automation_gateway_enabled": True,
    }

    cfg = build_config(raw)
    compose_path = render_compose(cfg, output_dir=tmp_path)
    render_automation_gateway_config(cfg, output_dir=tmp_path)

    compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert "automation-gateway" in compose_data["services"]
    ag_service = compose_data["services"]["automation-gateway"]

    assert ag_service["image"] == "rocworks/automation-gateway:latest"
    assert ag_service["environment"]["GATEWAY_CONFIG"] == "/app/config.yaml"

    volume = ag_service["volumes"][0]
    assert volume["target"] == "/app/config.yaml"
    assert Path(volume["source"]).exists()

    config_path = tmp_path / "automation-gateway" / "config.yaml"
    assert config_path.exists()
    contents = config_path.read_text(encoding="utf-8")
    assert "GraphQL" in contents


def test_render_automation_gateway_with_custom_template(tmp_path):
    raw = {
        "mode": "clean",
        "admin_user": "admin",
        "admin_pass": "secure-pass-123",
        "gateway_name": "demo-gateway",
        "data_mount_type": "volume",
        "automation_gateway_enabled": True,
        "automation_gateway_config_template": "telemetry",
    }

    cfg = build_config(raw)
    compose_path = render_compose(cfg, output_dir=tmp_path)
    render_automation_gateway_config(cfg, output_dir=tmp_path)

    assert cfg.automation_gateway is not None
    assert cfg.automation_gateway.config_template == "telemetry"
    assert cfg.automation_gateway.template_filename() == "telemetry.yaml.j2"

    config_path = tmp_path / "automation-gateway" / "config.yaml"
    contents = config_path.read_text(encoding="utf-8")
    assert "MqttTelemetry" in contents
    assert "GraphQL" not in contents

    compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    ag_service = compose_data["services"]["automation-gateway"]
    assert ag_service["environment"]["GATEWAY_CONFIG"] == "/app/config.yaml"


def test_available_automation_gateway_templates():
    templates = AutomationGatewayConfig.available_templates()
    assert {"default", "telemetry"}.issubset(templates)


def test_build_config_rejects_unknown_gateway_template():
    raw = {
        "mode": "clean",
        "admin_user": "admin",
        "admin_pass": "secure-pass-123",
        "gateway_name": "demo-gateway",
        "data_mount_type": "volume",
        "automation_gateway_enabled": True,
        "automation_gateway_config_template": "nonexistent",
    }

    with pytest.raises(ConfigBuildError) as exc:
        build_config(raw)

    assert "Unsupported Automation Gateway config template" in str(exc.value)
