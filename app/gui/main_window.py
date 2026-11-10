import copy
import json
from pathlib import Path
from PySide6.QtCore import Qt, QSettings, QTimer, QRunnable, QThreadPool, QObject, Signal
from PySide6.QtGui import QAction, QFontDatabase, QTextCursor, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QListWidget, QLineEdit, QPushButton, QTabWidget,
    QComboBox, QLabel, QScrollArea, QPlainTextEdit, QTableView, QFileDialog,
    QMessageBox, QInputDialog, QTextEdit, QAbstractItemView,
)
from app.domain import Project, TaskInstance
from app.api_config import ApiSettings
from .api_dialog import ApiInventoryDialog
from app.services.builder import BuilderService
from app.bulk.io import export_report
from .fields import SchemaForm
from .models import BulkTableModel


class WorkerSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, service=None, settings=None):
        super().__init__()
        self.service = service or BuilderService()
        self.settings = settings or QSettings()
        self.path = None
        self.dirty = False
        self.selected = None
        self.loading = False
        self.revision = 0
        self.workers = set()
        self.setMinimumSize(1100, 700)
        self.resize(1500, 900)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.setCentralWidget(self.splitter)
        self.build_left()
        self.build_center()
        self.build_right()
        self.splitter.setSizes([330, 645, 525])
        self.build_menu()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.generate)
        if self.settings.value("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        if self.settings.value("splitter"):
            self.splitter.restoreState(self.settings.value("splitter"))
        self.refresh()

    def panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.splitter.addWidget(widget)
        return layout

    @staticmethod
    def button(layout, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def build_left(self):
        layout = self.panel()
        layout.addWidget(QLabel("Task Catalog"))
        catalog = QTreeWidget()
        catalog.setHeaderHidden(True)
        group = QTreeWidgetItem(catalog, ["Interface"])
        for task in self.service.registry.tasks.values():
            item = QTreeWidgetItem(group, [task.name])
            item.setData(0, Qt.UserRole, task.task_id)
        catalog.expandAll()
        catalog.setMaximumHeight(160)
        catalog.itemDoubleClicked.connect(lambda item, _: self.add_instance() if item.data(0, Qt.UserRole) else None)
        layout.addWidget(catalog)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Instance / 장비 / 인터페이스 검색")
        self.search.textChanged.connect(self.filter_instances)
        layout.addWidget(self.search)
        self.instances = QListWidget()
        self.instances.currentRowChanged.connect(self.select_instance)
        layout.addWidget(self.instances)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.button(actions, "추가", self.add_instance)
        self.button(actions, "복제", self.duplicate_instance)
        self.button(actions, "삭제", self.remove_instance)

    def build_center(self):
        layout = self.panel()
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        single = QWidget()
        sl = QVBoxLayout(single)
        self.router = QComboBox()
        self.router.setEditable(True)
        self.router.setInsertPolicy(QComboBox.NoInsert)
        self.router.completer().setFilterMode(Qt.MatchContains)
        self.router.currentIndexChanged.connect(self.edit_single)
        self.router.lineEdit().editingFinished.connect(self.edit_single)
        sl.addWidget(QLabel("Router · 이름 / management_ip"))
        sl.addWidget(self.router)
        self.router_info = QLabel()
        sl.addWidget(self.router_info)
        sl.addWidget(QLabel("Profile: hub-gate · 빈칸은 default 적용, Off는 비활성"))
        self.form = SchemaForm(self.service.registry.schemas["interface.create"], self.service.registry.profiles["hub-gate"])
        self.form.changed.connect(self.edit_single)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        sl.addWidget(scroll)
        self.button(sl, "검증 / 생성", self.generate)
        self.tabs.addTab(single, "Single Task")
        bulk = QWidget()
        bl = QVBoxLayout(bulk)
        bar = QHBoxLayout()
        bl.addLayout(bar)
        self.button(bar, "XLSX 양식", lambda: self.template("xlsx"))
        self.button(bar, "CSV 양식", lambda: self.template("csv"))
        self.button(bar, "가져오기", self.import_bulk)
        self.button(bl, "공통값 편집 (JSON)", self.edit_common)
        self.table_model = BulkTableModel(self.service)
        self.table_model.changed.connect(self.bulk_changed)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        bl.addWidget(self.table)
        self.button(bl, "전체 검증 / 정상 항목 생성", self.generate)
        self.tabs.addTab(bulk, "Bulk Task")

    def build_right(self):
        layout = self.panel()
        bar = QHBoxLayout()
        layout.addLayout(bar)
        self.view = QComboBox()
        self.view.addItems(["Task", "Router"])
        self.mode = QComboBox()
        self.mode.addItems(["Annotated", "Clean"])
        for combo in (self.view, self.mode):
            bar.addWidget(combo)
            combo.currentIndexChanged.connect(self.show_preview)
        self.output_router = QComboBox()
        self.output_router.setToolTip("장비별 출력 대상 management_ip")
        bar.addWidget(self.output_router)
        self.output_router.currentIndexChanged.connect(self.show_preview)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(self.preview, 3)
        search = QLineEdit()
        search.setPlaceholderText("Config 검색 · Enter")
        search.returnPressed.connect(lambda: self.preview.find(search.text()))
        layout.addWidget(search)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.copy_button = self.button(actions, "복사", self.copy_config)
        self.export_button = self.button(actions, "TXT 저장", self.export_config)
        self.errors = QListWidget()
        self.errors.itemClicked.connect(self.focus_diagnostic)
        layout.addWidget(self.errors, 1)

    def build_menu(self):
        toolbar = self.addToolBar("프로젝트")
        file_menu = self.menuBar().addMenu("파일")
        for label, shortcut, callback in (
            ("새 프로젝트", "Ctrl+N", self.new_project), ("열기", "Ctrl+O", self.open_project),
            ("프로젝트 이름 변경", "", self.rename_project),
            ("저장", "Ctrl+S", self.save_project), ("다른 이름으로 저장", "Ctrl+Shift+S", lambda: self.save_project(True)),
            ("API Inventory 불러오기", "", self.load_api_inventory),
            ("Config 내보내기", "", self.export_config),
            ("오류 보고서", "", self.export_errors),
        ):
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False, cb=callback: cb())
            file_menu.addAction(action)
            toolbar.addAction(action)
        self.recent_menu = file_menu.addMenu("최근 프로젝트")
        self.refresh_recent()
        view = self.menuBar().addMenu("보기")
        view.addAction("패널 너비 초기화", lambda: self.splitter.setSizes([330, 645, 525]))
        view.addAction("검증 패널", lambda: self.errors.setVisible(not self.errors.isVisible()))
        help_menu = self.menuBar().addMenu("도움말")
        help_menu.addAction("버전 / 검증 상태", lambda: QMessageBox.information(self, "MVP v0.1", "Task/Schema/Profile/Template: 1.4.1\nGolden: PTX10008 / 23.4R2-S1.6-EVO / et, unit 0\nLink mode: backbone/external (external: no-flow-control)\nIS-IS P2P/passive 지원\nae 전체 생성은 추가 Golden 필요\n장비 접속/실행 기능 없음"))

    def refresh_recent(self):
        self.recent_menu.clear()
        for path in self.settings.value("recent", [], type=list):
            self.recent_menu.addAction(path, lambda p=path: self.open_project(p))

    def touch(self):
        self.dirty = True
        self.revision += 1
        self.service.result = None
        self.preview.clear()
        self.copy_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.update_title()

    def update_title(self):
        self.setWindowTitle(f"{self.service.project.name}{' *' if self.dirty else ''} — Network Operations Builder")

    def update_project_info(self):
        self.info.setText(f"{self.service.project.name}\nInventory: {self.service.project.inventory_source or '미선택'}")

    def refresh(self, selected=None):
        self.loading = True
        self.instances.clear()
        for instance in self.service.project.instances:
            record = self.service.inventory.get(instance.target_management_ip)
            self.instances.addItem(f"{instance.instance_id} · {record.name if record else instance.target_management_ip} · {instance.overrides.get('local_interface', '')}")
        self.router.clear()
        self.router.addItem("장비 선택", "")
        for ip, record in self.service.inventory.items():
            self.router.addItem(f"{record.name} · {ip}", ip)
        self.table_model.refresh()
        self.output_router.blockSignals(True)
        self.output_router.clear()
        for ip in dict.fromkeys(i.target_management_ip for i in self.service.project.instances if i.target_management_ip):
            self.output_router.addItem(ip)
        self.output_router.blockSignals(False)
        self.selected = None
        self.loading = False
        self.instances.setCurrentRow(selected if selected is not None else (0 if self.instances.count() else -1))
        self.update_project_info()
        self.form.setEnabled(bool(self.service.project.instances))
        self.update_title()
        self.show_preview()
        self.filter_instances()

    def filter_instances(self):
        term = self.search.text().casefold()
        for index in range(self.instances.count()):
            item = self.instances.item(index)
            item.setHidden(term not in item.text().casefold())

    def update_instance_labels(self):
        for row, instance in enumerate(self.service.project.instances):
            record = self.service.inventory.get(instance.target_management_ip)
            self.instances.item(row).setText(f"{instance.instance_id} · {record.name if record else instance.target_management_ip} · {instance.overrides.get('local_interface', '')}")
        old_target = self.output_router.currentText()
        self.output_router.blockSignals(True)
        self.output_router.clear()
        self.output_router.addItems(list(dict.fromkeys(i.target_management_ip for i in self.service.project.instances if i.target_management_ip)))
        index = self.output_router.findText(old_target)
        if index >= 0:
            self.output_router.setCurrentIndex(index)
        self.output_router.blockSignals(False)
        self.filter_instances()

    def select_instance(self, row):
        if self.loading:
            return
        self.selected = row if row >= 0 else None
        if self.selected is None:
            return
        instance = self.service.project.instances[row]
        self.loading = True
        index = self.router.findData(instance.target_management_ip)
        self.router.setCurrentIndex(max(0, index))
        self.form.load(instance.overrides, self.service.project.common_overrides, self.service.inventory.get(instance.target_management_ip))
        self.loading = False
        self.update_router_info()
        self.navigate(instance.instance_id)

    def update_router_info(self):
        record = self.service.inventory.get(self.router.currentData())
        self.router_info.setText(f"{record.manufacturer} / {record.model} / {record.hierarchy}" if record else "Inventory에서 장비를 선택하세요")

    def edit_single(self, *_):
        if self.loading or self.selected is None:
            return
        instance = self.service.project.instances[self.selected]
        previous_target = instance.target_management_ip
        instance.overrides = self.form.values()
        # Editable combo text must match an actual inventory entry.
        instance.target_management_ip = self.router.currentData() or "" if self.router.currentText() == self.router.itemText(self.router.currentIndex()) else ""
        if previous_target != instance.target_management_ip:
            record = self.service.inventory.get(instance.target_management_ip)
            for key in ("os_family", "os_version"):
                if getattr(record, key, ""):
                    instance.overrides.pop(key, None)
            self.form.load(instance.overrides, self.service.project.common_overrides, record)
        self.touch()
        self.update_instance_labels()
        self.update_router_info()
        self.table_model.refresh()
        self.timer.start()

    def bulk_changed(self):
        self.touch()
        self.update_instance_labels()
        if self.selected is not None:
            self.select_instance(self.selected)
        self.timer.start()

    def next_id(self):
        existing = {i.instance_id for i in self.service.project.instances}
        number = 1
        while f"IF-{number:03}" in existing:
            number += 1
        return f"IF-{number:03}"

    def add_instance(self):
        self.service.project.instances.append(TaskInstance(self.next_id()))
        self.touch()
        self.refresh(len(self.service.project.instances) - 1)

    def duplicate_instance(self):
        if self.selected is None:
            return
        instance = copy.deepcopy(self.service.project.instances[self.selected])
        instance.instance_id = self.next_id()
        self.service.project.instances.append(instance)
        self.touch()
        self.refresh(len(self.service.project.instances) - 1)

    def remove_instance(self):
        if self.selected is not None and QMessageBox.question(self, "삭제", "선택한 Task를 삭제할까요?") == QMessageBox.Yes:
            del self.service.project.instances[self.selected]
            self.touch()
            self.refresh()

    def run_worker(self, function, done):
        worker = Worker(function)
        self.workers.add(worker)
        def finish(value):
            self.workers.discard(worker)
            done(value)
        def failed(message):
            self.workers.discard(worker)
            self.error(message)
        worker.signals.done.connect(finish)
        worker.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(worker)

    def generate(self):
        self.timer.stop()
        revision = self.revision
        instances = copy.deepcopy(self.service.project.instances)
        inventory = copy.deepcopy(self.service.inventory)
        common = copy.deepcopy(self.service.project.common_overrides)
        self.statusBar().showMessage("검증 중…")
        def done(result):
            if revision != self.revision:
                return
            self.service.result = result
            if self.selected is not None:
                iid = self.service.project.instances[self.selected].instance_id
                resolved = result.resolved.get(iid)
                if resolved:
                    self.form.show_resolved(resolved)
            self.table_model.set_diagnostics(result.diagnostics)
            self.errors.clear()
            for diagnostic in result.diagnostics:
                self.errors.addItem(f"{diagnostic.instance_id} · {diagnostic.field} · {diagnostic.code}: {diagnostic.message}")
            self.statusBar().showMessage(f"오류 {len(result.diagnostics)} · 생성 {len(result.valid_instance_ids)} / {len(instances)} · 로컬 Config 생성")
            self.show_preview()
        self.run_worker(lambda: self.service.engine.generate(instances, inventory, common), done)

    def kind(self):
        view = "task" if self.view.currentText() == "Task" else f"router:{self.output_router.currentText()}"
        return f"{view}.{self.mode.currentText().lower()}"

    def show_preview(self, *_):
        result = self.service.result
        text = result.outputs.get(self.kind(), "") if result else ""
        self.preview.setPlainText(text)
        self.copy_button.setEnabled(bool(text))
        self.export_button.setEnabled(bool(text))
        if self.selected is not None and self.selected < len(self.service.project.instances):
            self.navigate(self.service.project.instances[self.selected].instance_id)

    def navigate(self, iid):
        result = self.service.result
        if not result:
            return
        sections = [s for s in result.sections if s.instance_id == iid and s.output_kind == self.kind()]
        selections = []
        for section in sections:
            cursor = QTextCursor(self.preview.document().findBlockByNumber(section.start_line - 1))
            cursor.select(QTextCursor.LineUnderCursor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor("#fff0b0"))
            selections.append(selection)
        self.preview.setExtraSelections(selections)
        if sections:
            self.preview.setTextCursor(QTextCursor(self.preview.document().findBlockByNumber(sections[0].start_line - 1)))
            self.preview.centerCursor()

    def focus_diagnostic(self, item):
        result = self.service.result
        if not result:
            return
        diagnostic = result.diagnostics[self.errors.row(item)]
        for row, instance in enumerate(self.service.project.instances):
            if instance.instance_id == diagnostic.instance_id:
                self.instances.setCurrentRow(row)
                self.tabs.setCurrentIndex(0)
                widget = self.form.widgets.get(diagnostic.field)
                if widget:
                    widget.setFocus()
                break

    def choose(self, save, title, file_filter):
        callback = QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
        path, _ = callback(self, title, self.settings.value("last_path", ""), file_filter)
        if path:
            self.settings.setValue("last_path", str(Path(path).parent))
        return path

    def error(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "확인 필요", message)

    def load_api_inventory(self):
        try:
            settings = ApiSettings.load()
        except (OSError, ValueError) as exc:
            self.error(str(exc))
            return
        dialog = ApiInventoryDialog(settings, self)
        if dialog.exec() != ApiInventoryDialog.Accepted:
            dialog.deleteLater()
            return
        user_id, password = dialog.take_credentials()
        dialog.deleteLater()
        revision = self.revision
        self.statusBar().showMessage("API에서 라우터 정보를 불러오는 중…")
        def done(records):
            if revision != self.revision:
                self.error("조회하는 동안 프로젝트/입력이 변경되었습니다. API Inventory를 다시 불러오세요.")
                return
            self.service.apply_api_inventory(records)
            self.touch()
            self.refresh(self.selected)
            self.statusBar().showMessage(f"API Inventory: 라우터 {len(records)}개 로드 완료")
        self.run_worker(lambda: self.service.fetch_api_inventory(settings, user_id, password), done)

    def template(self, suffix):
        path = self.choose(True, "최신 Bulk 양식", f"{suffix.upper()} (*.{suffix})")
        if path:
            try:
                self.service.bulk.export_template(path)
            except (OSError, ValueError) as exc:
                self.error(str(exc))

    def import_bulk(self):
        path = self.choose(False, "Bulk 가져오기", "Bulk (*.xlsx *.csv)")
        if not path:
            return
        message = "현재 Task 목록을 교체할까요? XLSX는 공통값도 교체하며 CSV는 현재 공통값을 유지합니다."
        if self.service.project.instances and QMessageBox.question(self, "Bulk 가져오기", message) != QMessageBox.Yes:
            return
        revision = self.revision
        def done(value):
            if revision != self.revision:
                self.error("가져오는 동안 입력이 변경되었습니다. 다시 가져오세요.")
                return
            instances, common = value
            self.service.project.instances = instances
            if Path(path).suffix.lower() == ".xlsx":
                self.service.project.common_overrides = common
            self.touch()
            self.refresh()
            self.generate()
        self.run_worker(lambda: self.service.bulk.load(path), done)

    def edit_common(self):
        text, ok = QInputDialog.getMultiLineText(self, "공통값", "Schema 필드 → 값 (JSON)", json.dumps(self.service.project.common_overrides, ensure_ascii=False, indent=2))
        if ok:
            try:
                values = json.loads(text)
                if not isinstance(values, dict) or not set(values) <= set(self.service.bulk.fields):
                    raise ValueError("Schema 필드 객체가 필요합니다")
                self.service.project.common_overrides = values
                self.touch()
                self.refresh(self.selected)
                self.generate()
            except ValueError as exc:
                self.error(str(exc))

    def copy_config(self):
        if self.service.result:
            QApplication.clipboard().setText(self.service.result.outputs.get(self.kind(), ""))

    def export_config(self):
        path = self.choose(True, "정상 항목 Config 저장", "Text (*.txt)")
        if path:
            newline, ok = QInputDialog.getItem(self, "줄바꿈", "파일 줄바꿈", ["CRLF", "LF"], 0, False)
            if ok:
                try:
                    self.service.export_config(path, self.kind(), newline)
                except (OSError, ValueError) as exc:
                    self.error(str(exc))

    def export_errors(self):
        path = self.choose(True, "오류 보고서", "CSV (*.csv);;Excel (*.xlsx)")
        if path:
            try:
                result = self.service.generate()
                export_report(path, result.diagnostics)
            except (OSError, ValueError) as exc:
                self.error(str(exc))

    def confirm_dirty(self):
        if not self.dirty:
            return True
        choice = QMessageBox.question(self, "미저장 프로젝트", "변경사항을 저장할까요?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if choice == QMessageBox.Cancel:
            return False
        return self.save_project() if choice == QMessageBox.Save else True

    def new_project(self):
        name = self.ask_project_name("새 프로젝트", "새 프로젝트")
        if name is None or not self.confirm_dirty():
            return
        self.timer.stop()
        self.service.project, self.service.inventory, self.service.result = Project(name=name), {}, None
        self.path, self.dirty = None, True
        self.revision += 1
        self.errors.clear()
        self.refresh()

    def ask_project_name(self, title, initial):
        while True:
            name, accepted = QInputDialog.getText(self, title, "프로젝트 이름", text=initial)
            if not accepted:
                return None
            name = name.strip()
            if name:
                return name
            self.error("프로젝트 이름을 입력하세요.")
            initial = ""

    def rename_project(self):
        name = self.ask_project_name("프로젝트 이름 변경", self.service.project.name)
        if name is None or name == self.service.project.name:
            return
        self.service.project.name = name
        self.dirty = True
        self.update_title()
        self.update_project_info()

    def open_project(self, path=None):
        if not self.confirm_dirty():
            return
        path = path or self.choose(False, "프로젝트 열기", "NOB Project (*.nobproj)")
        if path:
            try:
                warning = self.service.open_project(path)
                self.path, self.dirty = path, False
                self.revision += 1
                self.refresh()
                self.remember(path)
                if warning:
                    self.error(warning)
            except (OSError, ValueError, TypeError) as exc:
                self.error(str(exc))

    def save_project(self, save_as=False):
        path = self.path if self.path and not save_as else self.choose(True, "프로젝트 저장", "NOB Project (*.nobproj)")
        if not path:
            return False
        try:
            self.service.save_project(path)
            self.path, self.dirty = path, False
            self.remember(path)
            self.update_title()
            return True
        except (OSError, ValueError) as exc:
            self.error(str(exc))
            return False

    def remember(self, path):
        recent = self.settings.value("recent", [], type=list)
        self.settings.setValue("recent", [path] + [p for p in recent if p != path][:9])
        self.refresh_recent()

    def closeEvent(self, event):
        if self.confirm_dirty():
            self.timer.stop()
            QThreadPool.globalInstance().waitForDone()
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("splitter", self.splitter.saveState())
            event.accept()
        else:
            event.ignore()
