from pathlib import Path
import json
import pytest
from PySide6.QtCore import QSettings, QTimer, QThreadPool, QElapsedTimer
from PySide6.QtWidgets import QApplication, QDialog
from app.api_config import ApiSettings
from app.inventory.api_repository import ApiError, API_INVENTORY_SOURCE
from app.services.builder import BuilderService
from app.persistence.project import load_project
from app.gui.main_window import MainWindow
from app.gui.api_dialog import ApiInventoryDialog


def test_failed_fetch_preserves_everything(monkeypatch, instance, inventory):
    service = BuilderService()
    service.inventory = inventory
    service.project.instances = [instance]
    service.project.inventory_source = "original.csv"
    service.result = object()
    before = service.result
    def fail(*_):
        raise ApiError("API failure")
    monkeypatch.setattr(service, "fetch_api_inventory", fail)
    with pytest.raises(ApiError):
        service.load_api_inventory(ApiSettings("http://localhost"))
    assert service.inventory is inventory and service.result is before
    assert service.project.instances == [instance]
    assert service.project.inventory_source == "original.csv"


def test_api_project_roundtrip_without_network_or_secrets(tmp_path, monkeypatch, inventory, instance):
    service = BuilderService()
    service.project.instances = [instance]
    service.apply_api_inventory(inventory)
    path = tmp_path / "api.nobproj"
    service.save_project(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["inventory_source"] == API_INVENTORY_SOURCE
    assert not any(key in path.read_text(encoding="utf-8") for key in ["password", "access_token", "refresh_token", "API_BASE_URL"])
    assert load_project(path).inventory_source == API_INVENTORY_SOURCE
    monkeypatch.setattr(service, "fetch_api_inventory", lambda *_: pytest.fail("Project open must not connect automatically"))
    warning = service.open_project(path)
    assert "API" in warning and service.project.instances == [instance]
    assert service.inventory == {}


def test_gui_api_load_updates_same_router_selector(tmp_path, monkeypatch, inventory):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=QSettings(str(tmp_path / "api.ini"), QSettings.IniFormat))
    window.add_instance()
    monkeypatch.setattr(ApiSettings, "load", lambda: ApiSettings("http://localhost:8000"))
    monkeypatch.setattr(ApiInventoryDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(window.service, "fetch_api_inventory", lambda *_: inventory)
    window.load_api_inventory()
    timer = QElapsedTimer()
    timer.start()
    while window.workers and timer.elapsed() < 3000:
        app.processEvents()
    app.processEvents()
    assert window.service.project.inventory_source == API_INVENTORY_SOURCE
    assert window.router.findData("10.0.0.1") > 0
    assert "api:/router/" in window.info.text()
    window.dirty = False
    window.close()


def test_legacy_csv_project_preserves_tasks_but_never_reads_inventory(tmp_path, instance):
    service = BuilderService()
    service.project.instances = [instance]
    service.project.common_overrides = {"mtu": 4484}
    path = tmp_path / "legacy.nobproj"
    service.save_project(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["inventory_source"] = "old-router-inventory.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    warning = service.open_project(path)
    assert "CSV" in warning and "API" in warning
    assert service.project.instances == [instance]
    assert service.project.common_overrides == {"mtu": 4484}
    assert service.project.inventory_source == API_INVENTORY_SOURCE
    assert not service.inventory
    service.save_project(path)
    assert "old-router-inventory.csv" not in path.read_text(encoding="utf-8")


def test_csv_inventory_entry_points_removed(tmp_path):
    from PySide6.QtGui import QAction
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=QSettings(str(tmp_path / "api-only.ini"), QSettings.IniFormat))
    labels = [a.text() for a in window.findChildren(QAction)]
    assert "Inventory CSV" not in labels
    assert "API Inventory 불러오기" in labels
    assert not hasattr(window, "load_inventory")
    assert not hasattr(window.service, "load_inventory")
    # CSV remains available for Bulk task parameters.
    assert hasattr(window.service.bulk, "load")
    assert window.service.project.inventory_source == API_INVENTORY_SOURCE
    window.close()
