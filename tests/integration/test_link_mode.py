import json
from pathlib import Path
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from app.domain import TaskInstance, InventoryRecord
from app.gui.main_window import MainWindow
from app.services.builder import BuilderService

CASE = Path(__file__).parents[1] / "golden/ptx10008_backbone/input.json"


def service_for_golden():
    data = json.loads(CASE.read_text(encoding="utf-8"))
    service = BuilderService()
    service.project.instances = [TaskInstance(**data["instances"][0])]
    service.apply_api_inventory({r["management_ip"]: InventoryRecord(**r) for r in data["inventory"]})
    return service


def test_link_mode_in_link_group_even_without_cos(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = service_for_golden()
    service.project.instances[0].overrides["cos_enabled"] = False
    window = MainWindow(service, QSettings(str(tmp_path / "link.ini"), QSettings.IniFormat))
    assert "cos_mode" not in window.form.widgets
    assert window.form.schema.fields["link_mode"]["group"] == "Link"
    assert not window.form.widgets["link_mode"].isHidden()
    assert "link_mode" in window.table_model.columns
    assert "cos_mode" not in window.table_model.columns
    mode = window.form.widgets["link_mode"]
    mode.setCurrentIndex(mode.findData("external"))
    result = service.generate()
    assert not result.diagnostics
    assert result.resolved["IF-001"].values["link_mode"] == "external"
    assert "class-of-service" not in result.outputs["task.clean"]
    window.dirty = False
    window.close()


@pytest.mark.parametrize("mode,expected,absent", [
    ("backbone", "rewrite-rules", "classifiers"),
    ("external", "classifiers", "rewrite-rules"),
])
def test_link_mode_preserves_cli_and_does_not_change_isis(mode, expected, absent):
    service = service_for_golden()
    service.project.instances[0].overrides["link_mode"] = mode
    result = service.generate()
    assert not result.diagnostics
    text = result.outputs["task.clean"]
    assert expected in text and absent not in text
    assert "point-to-point" in text and "level 2 passive" not in text


def test_defaults_common_override_and_old_field_rejection():
    service = service_for_golden()
    instance = service.project.instances[0]
    instance.overrides.pop("link_mode")
    assert service.generate().resolved[instance.instance_id].values["link_mode"] == "backbone"
    service.project.common_overrides["link_mode"] = "external"
    assert service.generate().resolved[instance.instance_id].sources["link_mode"] == "common"
    instance.overrides["link_mode"] = "backbone"
    assert service.generate().resolved[instance.instance_id].values["link_mode"] == "backbone"
    instance.overrides["cos_mode"] = "external"
    assert any(d.field == "cos_mode" and d.code == "unknown_field" for d in service.generate().diagnostics)
