"""Integration tests for the environment API."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api import create_app
from services import EnvironmentService
from paths import GENERATED_DIR

pytestmark = pytest.mark.filterwarnings(
    "ignore:The 'app' shortcut is now deprecated:DeprecationWarning:httpx._client"
)


@pytest.fixture(autouse=True)
def clean_environment_registry():
    """Ensure the generated environments directory is reset between tests."""

    env_dir = GENERATED_DIR / "environments"
    if env_dir.exists():
        shutil.rmtree(env_dir)
    yield
    if env_dir.exists():
        shutil.rmtree(env_dir)


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        return Path.cwd() / path
    return path


def test_environment_lifecycle(tmp_path):
    app = create_app()

    payload = {
        "display_name": "QA Gateway",
        "mode": "clean",
        "admin_user": "admin",
        "admin_password": "StrongPass123!",
        "gateway_name": "qa-gateway",
        "http_port": 8090,
        "https_port": 8045,
        "edition": "standard",
        "timezone": "America/Chicago",
        "image_repo": "inductiveautomation/ignition",
        "image_tag": "8.1",
        "data_mount_type": "volume",
    }

    with TestClient(app) as client:
        response = client.post("/api/environments", json=payload)
        assert response.status_code == 201, response.text
        created = response.json()

        env_id = created["id"]
        assert created["display_name"] == "QA Gateway"
        assert created["config"]["gateway_name"] == "qa-gateway"
        assert created["config"]["admin_user"] == "admin"
        assert "admin_password" not in created["config"]
        assert created["status"] == "created"
        assert created["last_started_at"] is None
        assert created["config"]["automation_gateway"] is None


        compose_path = _resolve_path(created["compose_file"])
        env_file = _resolve_path(created["env_file"])
        assert compose_path.exists()
        assert env_file.exists()

        list_response = client.get("/api/environments")
        assert list_response.status_code == 200
        listing = list_response.json()
        assert listing["items"][0]["id"] == env_id
        assert listing["items"][0]["status"] == "created"


        detail_response = client.get(f"/api/environments/{env_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["id"] == env_id
        assert detail["config"]["image_repo"] == "inductiveautomation/ignition"
        assert detail["status"] == "created"
        assert detail["config"]["automation_gateway"] is None


        delete_response = client.delete(f"/api/environments/{env_id}")
        assert delete_response.status_code == 204

        missing = client.get(f"/api/environments/{env_id}")
        assert missing.status_code == 404

    assert not compose_path.exists()
    assert not env_file.exists()

def test_environment_start_stop(tmp_path):
    class DummyManager:
        def __init__(self, compose_file, env_file):
            self.compose_file = compose_file
            self.env_file = env_file
            self.up_calls = 0
            self.down_calls = 0
            self.wait_calls: list[tuple[int, int]] = []

        def up_detached(self) -> None:
            self.up_calls += 1

        def wait_for_gateway(self, port: int, timeout: int = 60) -> bool:
            self.wait_calls.append((port, timeout))
            return True

        def down(self) -> None:
            self.down_calls += 1

    managers: list[DummyManager] = []

    def factory(compose_file, env_file):
        manager = DummyManager(compose_file, env_file)
        managers.append(manager)
        return manager

    service = EnvironmentService(docker_manager_factory=factory)
    app = create_app(environment_service=service)

    payload = {
        "display_name": "QA Gateway",
        "mode": "clean",
        "admin_user": "admin",
        "admin_password": "StrongPass123!",
        "gateway_name": "qa-gateway",
        "http_port": 8090,
        "https_port": 8045,
        "edition": "standard",
        "timezone": "America/Chicago",
        "image_repo": "inductiveautomation/ignition",
        "image_tag": "8.1",
        "data_mount_type": "volume",
    }

    with TestClient(app) as client:
        create_response = client.post("/api/environments", json=payload)
        env_id = create_response.json()["id"]

        start_response = client.post(
            f"/api/environments/{env_id}/actions/start",
            params={"wait": True},
        )
        assert start_response.status_code == 200
        started = start_response.json()
        assert started["status"] == "running"
        assert started["last_started_at"] is not None

        assert len(managers) >= 1
        assert managers[0].up_calls == 1
        assert managers[0].wait_calls == [(8090, 60)]

        stop_response = client.post(f"/api/environments/{env_id}/actions/stop")
        assert stop_response.status_code == 200
        stopped = stop_response.json()
        assert stopped["status"] == "stopped"
        assert stopped["last_stopped_at"] is not None

        assert len(managers) >= 2
        assert managers[-1].down_calls == 1


def test_environment_with_automation_gateway(tmp_path):
    app = create_app()

    payload = {
        "display_name": "Gateway with Bridge",
        "mode": "clean",
        "admin_user": "admin",
        "admin_password": "StrongPass123!",
        "gateway_name": "ag-gateway",
        "http_port": 8090,
        "https_port": 8045,
        "edition": "standard",
        "timezone": "America/Chicago",
        "image_repo": "inductiveautomation/ignition",
        "image_tag": "8.1",
        "data_mount_type": "volume",
        "automation_gateway_enabled": True,
        "automation_gateway_graphql_port": 4010,
        "automation_gateway_mqtt_port": 18830,
        "automation_gateway_mqtt_ws_port": 18840,
        "automation_gateway_opcua_port": 4850,
    }

    with TestClient(app) as client:
        response = client.post("/api/environments", json=payload)
        assert response.status_code == 201, response.text
        created = response.json()

        ag_config = created["config"]["automation_gateway"]
        assert ag_config["enabled"] is True
        assert ag_config["graphql_port"] == 4010
        assert ag_config["config_file"] is not None
        assert ag_config["config_template"] == "default"

        compose_path = _resolve_path(created["compose_file"])
        compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        ag_service = compose_data["services"]["automation-gateway"]
        assert "automation-gateway" in compose_data["services"]
        assert "4010:4010" in ag_service["ports"]
        assert "18830:18830" in ag_service["ports"]

        config_path = _resolve_path(ag_config["config_file"])
        assert config_path.exists()
        assert "GraphQL" in config_path.read_text(encoding="utf-8")

