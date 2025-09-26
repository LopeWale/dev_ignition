import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services import AutomationGatewayService


def test_list_templates_with_custom_directory(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    template_path = templates_dir / "custom.yaml.j2"
    template_path.write_text(
        """# automation_gateway/templates/custom.yaml.j2
#
# Custom template for testing
# Provides sample defaults
Servers: {}
""",
        encoding="utf-8",
    )

    service = AutomationGatewayService(templates_dir=templates_dir)
    templates = service.list_templates()

    by_name = {template.name: template for template in templates}

    assert "custom" in by_name
    custom = by_name["custom"]
    assert custom.exists is True
    assert custom.is_default is False
    assert "Custom template" in (custom.description or "")
    assert custom.relative_path == template_path.resolve().as_posix()

    default = by_name["default"]
    assert default.is_default is True
    assert default.exists is False
    assert default.relative_path is None
    assert default.description is None


def test_list_templates_with_missing_directory(tmp_path):
    service = AutomationGatewayService(templates_dir=tmp_path / "missing")
    templates = service.list_templates()
    names = {template.name for template in templates}
    assert names == {"default"}
    default = templates[0]
    assert default.exists is False
