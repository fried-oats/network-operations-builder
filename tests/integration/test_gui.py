import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow
from app.services.builder import BuilderService


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_gui_form_table_and_mapping(qt_app, tmp_path, synthetic_registry, instance, inventory):
    service = BuilderService(synthetic_registry)
    service.project.instances = [instance]
    service.inventory = inventory
    settings = QSettings(str(tmp_path / "gui.ini"), QSettings.IniFormat)
    window = MainWindow(service, settings)
    assert window.splitter.count() == 3
    assert not window.splitter.childrenCollapsible()
    assert window.table_model.rowCount() == 1
    assert window.form.widgets["local_interface"].text() == "test-0"
    service.generate()
    window.show_preview()
    assert "TEST_ONLY" in window.preview.toPlainText()
    assert window.preview.extraSelections()
    index = window.table_model.index(0, window.table_model.columns.index("mtu"))
    window.table_model.setData(index, "9000", Qt.EditRole)
    assert service.result is None
    assert window.preview.toPlainText() == ""
    window.dirty = False
    window.close()
    assert settings.value("splitter")


def test_switch_preserves_single_edits(qt_app, tmp_path):
    window = MainWindow(settings=QSettings(str(tmp_path / "gui.ini"), QSettings.IniFormat))
    window.add_instance()
    widget = window.form.widgets["local_interface"]
    widget.setText("et-0/0/0")
    widget.textEdited.emit("et-0/0/0")
    window.add_instance()
    window.instances.setCurrentRow(0)
    assert widget.text() == "et-0/0/0"
    assert window.service.project.instances[0].overrides["local_interface"] == "et-0/0/0"
    window.dirty = False
    window.close()
