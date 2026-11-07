from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow
from app.services.builder import BuilderService


def test_bulk_edit_is_visible_in_single(tmp_path, synthetic_registry, instance, inventory):
    application = QApplication.instance() or QApplication([])
    service = BuilderService(synthetic_registry)
    service.project.instances = [instance]
    service.inventory = inventory
    window = MainWindow(service, QSettings(str(tmp_path / "sync.ini"), QSettings.IniFormat))
    column = window.table_model.columns.index("local_interface")
    window.table_model.setData(window.table_model.index(0, column), "test-updated", Qt.EditRole)
    assert window.form.widgets["local_interface"].text() == "test-updated"
    assert "test-updated" in window.instances.item(0).text()
    window.dirty = False
    window.close()
