import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from compose_generator import build_config, render_compose  # noqa: E402


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
