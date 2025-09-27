import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api import create_app
from services import AutomationGatewayService


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


def test_get_automation_gateway_template_detail():
    service = AutomationGatewayService()
    app = create_app(automation_gateway_service=service)

    with TestClient(app) as client:
        response = client.get("/api/automation-gateway/templates/default")
        assert response.status_code == 200, response.text
        payload = response.json()

    assert payload["name"] == "default"
    assert payload["exists"] is True
    assert "Servers" in payload["content"]


def test_get_automation_gateway_template_detail_unknown_name():
    service = AutomationGatewayService()
    app = create_app(automation_gateway_service=service)

    with TestClient(app) as client:
        response = client.get("/api/automation-gateway/templates/bad-template")

    assert response.status_code == 400
    assert "Unknown Automation Gateway template" in response.json()["detail"]


def test_get_automation_gateway_template_detail_missing_file(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    service = AutomationGatewayService(templates_dir=templates_dir)
    app = create_app(automation_gateway_service=service)

    with TestClient(app) as client:
        response = client.get("/api/automation-gateway/templates/default")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
