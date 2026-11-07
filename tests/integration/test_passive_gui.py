from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow
from app.services.builder import BuilderService


def test_passive_controls_and_backbone_values_restore(tmp_path, synthetic_registry, instance, inventory):
    app = QApplication.instance() or QApplication([])
    instance.overrides.update(isis_enabled=True, isis_passive=False, isis_metric=150, mpls_enabled=True, ldp_enabled=True)
    service = BuilderService(synthetic_registry)
    service.inventory = inventory
    service.project.instances = [instance]
    window = MainWindow(service, QSettings(str(tmp_path / "passive.ini"), QSettings.IniFormat))
    form = window.form
    passive = form.widgets["isis_passive"]
    passive.setCurrentIndex(passive.findData(True))
    assert form.widgets["isis_metric"].text() == "0"
    for key in ("isis_metric", "mpls_enabled", "ldp_enabled", "isis_hello_interval", "isis_hold_time"):
        assert not form.widgets[key].isEnabled()
    assert form.widgets["mpls_enabled"].currentData() is False
    assert form.widgets["ldp_enabled"].currentData() is False
    assert form.values()["isis_metric"] == "150"
    assert form.values()["mpls_enabled"] is True
    result = service.generate()
    assert not result.diagnostics
    assert result.resolved[instance.instance_id].values["isis_metric"] == 0
    # Saving/reloading the raw instance keeps the original values underneath the policy.
    form.load(instance.overrides)
    assert form.widgets["isis_metric"].text() == "0"
    passive.setCurrentIndex(passive.findData(False))
    assert form.widgets["isis_metric"].text() == "150"
    assert form.widgets["isis_metric"].isEnabled()
    assert form.widgets["mpls_enabled"].currentData() is True
    assert form.widgets["ldp_enabled"].currentData() is True
    assert not form.policy_raw
    window.dirty = False
    window.close()
