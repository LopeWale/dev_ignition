import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api import create_app


def test_list_automation_gateway_templates():
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/automation-gateway/templates")
        assert response.status_code == 200, response.text
        payload = response.json()

    assert "items" in payload
    names = {item["name"] for item in payload["items"]}
    assert {"default", "telemetry"}.issubset(names)

    default = next(item for item in payload["items"] if item["name"] == "default")
    assert default["is_default"] is True
    assert default["exists"] is True
    assert default["filename"].endswith(".yaml.j2")
