from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor


class BulkTableModel(QAbstractTableModel):
    changed = Signal()

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.columns = service.bulk.columns
        self.errors = {}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.service.project.instances)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        instance = self.service.project.instances[index.row()]
        key = self.columns[index.column()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            value = getattr(instance, key) if index.column() < 2 else instance.overrides.get(key, "")
            return "enable" if value is True else "disable" if value is False else str(value) if value is not None else ""
        if role == Qt.BackgroundRole and (index.row(), key) in self.errors:
            return QColor("#ffe2de")
        if role == Qt.ToolTipRole:
            return "\n".join(self.errors.get((index.row(), key), []))

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False
        instance = self.service.project.instances[index.row()]
        key = self.columns[index.column()]
        if index.column() < 2:
            setattr(instance, key, str(value))
        else:
            instance.overrides[key] = value
        self.service.result = None
        self.dataChanged.emit(index, index)
        self.changed.emit()
        return True

    def flags(self, index):
        return super().flags(index) | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.columns[section] if orientation == Qt.Horizontal else str(section + 2)
        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            return str(self.service.bulk.fields.get(self.columns[section], {"required": True}))

    def refresh(self):
        self.beginResetModel()
        self.errors = {}
        self.endResetModel()

    def set_diagnostics(self, diagnostics):
        self.errors = {}
        for row, instance in enumerate(self.service.project.instances):
            for d in diagnostics:
                if d.instance_id == instance.instance_id:
                    self.errors.setdefault((row, d.field), []).append(f"{d.code}: {d.message}")
        if self.rowCount():
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
