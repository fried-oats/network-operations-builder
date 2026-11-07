from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QLineEdit, QLabel


class FieldWidgetFactory:
    @staticmethod
    def create(spec):
        if spec["type"] == "bool" or spec["type"] == "enum":
            widget = QComboBox()
            widget.addItem("default", "")
            choices = [("활성", True), ("비활성", False)] if spec["type"] == "bool" else [(str(v), v) for v in spec["choices"]]
            for label, value in choices:
                widget.addItem(label, value)
        else:
            # Raw text preserves invalid input for diagnostics; integers are parsed by engine.
            widget = QLineEdit()
        return widget


class SchemaForm(QWidget):
    changed = Signal()

    def __init__(self, schema, profile):
        super().__init__()
        self.schema, self.profile = schema, profile
        self.widgets, self.labels = {}, {}
        self.loading = False
        self.common = {}
        self.inventory_values = {}
        self.policy_raw = {}
        layout = QFormLayout(self)
        previous_group = None
        for key, spec in schema.fields.items():
            if spec.get("derived"):
                continue
            if spec.get("group") != previous_group:
                previous_group = spec.get("group")
                group = QLabel(previous_group)
                group.setStyleSheet("font-weight: bold; margin-top: 12px")
                layout.addRow(group)
            widget = FieldWidgetFactory.create(spec)
            label = QLabel(key + (" *" if spec.get("required") else ""))
            self.labels[key] = label
            self.widgets[key] = widget
            default = profile.locked.get(key, profile.defaults.get(key, schema.defaults.get(key)))
            hint = f"default: {default}" if default is not None else ""
            widget.setToolTip(hint)
            widget.setAccessibleName(key)
            if isinstance(widget, QLineEdit):
                widget.setPlaceholderText(hint)
                widget.textEdited.connect(self.on_change)
            else:
                widget.currentIndexChanged.connect(self.on_change)
            widget.setEnabled(key not in profile.locked)
            layout.addRow(label, widget)
        self.update_conditions()

    def on_change(self, *_):
        if not self.loading:
            self.update_conditions()
            self.changed.emit()

    def values(self):
        values = {key: widget.currentData() if isinstance(widget, QComboBox) else widget.text() for key, widget in self.widgets.items() if key not in self.inventory_values}
        values.update(self.policy_raw)
        return values

    def load(self, overrides, common=None, inventory=None):
        self.loading = True
        common = common or {}
        self.common = common
        self.policy_raw = {}
        self.inventory_values = {key: getattr(inventory, key, "") for key in ("os_family", "os_version") if getattr(inventory, key, "")}
        for key, widget in self.widgets.items():
            value = self.inventory_values.get(key, overrides.get(key, ""))
            inherited = common.get(key, self.profile.defaults.get(key, self.schema.defaults.get(key)))
            if isinstance(widget, QComboBox):
                widget.setItemText(0, f"default: {inherited}" if inherited is not None else "default")
                if isinstance(value, str) and self.schema.fields[key]["type"] == "bool":
                    value = {"enable": True, "disable": False, "true": True, "false": False}.get(value.lower(), value)
                index = widget.findData(value)
                if index < 0:
                    widget.addItem(f"잘못된 입력: {value}", value)
                    index = widget.count() - 1
                widget.setCurrentIndex(index)
            else:
                widget.setText("" if value is None else str(value))
                widget.setPlaceholderText(f"default: {inherited}" if inherited is not None else "")
                widget.setCursorPosition(0)
            widget.setEnabled(key not in self.inventory_values and key not in self.profile.locked)
            widget.setToolTip(f"Inventory: {value}" if key in self.inventory_values else f"default: {inherited}")
        self.loading = False
        self.update_conditions()

    def update_conditions(self):
        values = {**self.schema.defaults, **self.profile.defaults, **self.common}
        values.update(self.inventory_values)
        values.update({k: v for k, v in self.values().items() if v != "" and v is not None})
        for key, spec in self.schema.fields.items():
            if spec["type"] == "bool" and isinstance(values.get(key), str):
                values[key] = values[key].lower() in {"enable", "true", "on"}
        passive = values.get("isis_enabled") is True and values.get("isis_passive") is True
        policy = self.profile.rules.get("isis_passive_overrides", {}) if passive else {}
        previous_loading = self.loading
        self.loading = True
        if not policy and self.policy_raw:
            raw, self.policy_raw = self.policy_raw, {}
            for key, value in raw.items():
                self.set_display(key, value)
        for key, value in policy.items():
            if key not in self.policy_raw:
                widget = self.widgets[key]
                self.policy_raw[key] = widget.currentData() if isinstance(widget, QComboBox) else widget.text()
            self.set_display(key, value)
        self.loading = previous_loading
        values.update(policy)
        for key, spec in self.schema.fields.items():
            if key not in self.widgets:
                continue
            visible = not spec.get("visible_when") or bool(values.get(spec["visible_when"]))
            self.widgets[key].setVisible(visible)
            self.labels[key].setVisible(visible)
            self.widgets[key].setEnabled(key not in policy and key not in self.inventory_values
                and key not in self.profile.locked and not (passive and key in {"isis_hello_interval", "isis_hold_time"}))
            if key in policy:
                self.widgets[key].setToolTip(f"Passive 자동 적용: {policy[key]}")

    def set_display(self, key, value):
        widget = self.widgets[key]
        if isinstance(widget, QComboBox):
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        else:
            widget.setText("" if value is None else str(value))

    def show_resolved(self, resolved):
        for key, widget in self.widgets.items():
            value = resolved.values.get(key)
            source = resolved.sources.get(key, "미지정")
            widget.setToolTip(f"적용값: {value}; 출처: {source}")
            if isinstance(widget, QComboBox):
                widget.setItemText(0, f"default: {value}")
