from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QInputDialog
import pytest
from app.gui.main_window import MainWindow
from app.persistence.project import load_project


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=QSettings(str(tmp_path / "name.ini"), QSettings.IniFormat))
    yield window
    window.dirty = False
    window.close()


def test_named_project_save_reload(window, monkeypatch, tmp_path):
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("  외부 연동 작업  ", True))
    window.new_project()
    assert window.service.project.name == "외부 연동 작업"
    assert window.dirty and window.path is None
    assert window.windowTitle().startswith("외부 연동 작업 *")
    assert window.info.text().startswith("외부 연동 작업\n")
    path = str(tmp_path / "named.nobproj")
    monkeypatch.setattr(window, "choose", lambda *a: path)
    assert window.save_project()
    assert not window.dirty
    assert load_project(path).name == "외부 연동 작업"
    window.open_project(path)
    assert window.service.project.name == "외부 연동 작업"


def test_cancel_or_blank_keeps_existing_project(window, monkeypatch):
    window.add_instance()
    original = window.service.project
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    monkeypatch.setattr(window, "confirm_dirty", lambda: pytest.fail("Name cancellation must not discard/save existing work"))
    window.new_project()
    assert window.service.project is original
    responses = iter([("   ", True), ("", False)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: next(responses))
    errors = []
    monkeypatch.setattr(window, "error", errors.append)
    window.rename_project()
    assert len(errors) == 1
    assert window.service.project is original and len(original.instances) == 1


def test_rename_preserves_inputs_preview_and_file(window, monkeypatch, tmp_path):
    window.add_instance()
    window.timer.stop()
    original = window.service.project.instances[0]
    result = object()
    window.service.result = result
    window.preview.setPlainText("existing preview")
    window.path = str(tmp_path / "existing.nobproj")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("변경된 프로젝트", True))
    window.rename_project()
    assert window.service.project.instances[0] is original
    assert window.service.result is result
    assert window.preview.toPlainText() == "existing preview"
    assert window.path.endswith("existing.nobproj") and window.dirty
    assert window.info.text().startswith("변경된 프로젝트\n")
