"""Integration tests for the environment API."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api import create_app
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

        compose_path = _resolve_path(created["compose_file"])
        env_file = _resolve_path(created["env_file"])
        assert compose_path.exists()
        assert env_file.exists()

        list_response = client.get("/api/environments")
        assert list_response.status_code == 200
        listing = list_response.json()
        assert listing["items"][0]["id"] == env_id

        detail_response = client.get(f"/api/environments/{env_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["id"] == env_id
        assert detail["config"]["image_repo"] == "inductiveautomation/ignition"

        delete_response = client.delete(f"/api/environments/{env_id}")
        assert delete_response.status_code == 204

        missing = client.get(f"/api/environments/{env_id}")
        assert missing.status_code == 404

    assert not compose_path.exists()
    assert not env_file.exists()
