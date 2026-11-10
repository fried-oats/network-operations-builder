import copy
import csv
import json
from dataclasses import replace
from pathlib import Path
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QComboBox
from app.domain import InventoryRecord, TaskInstance
from app.engine.core import ConfigEngine
from app.inventory.normalization import inventory_record
from app.services.builder import BuilderService
from app.gui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1] / "golden/ptx10008_backbone"


@pytest.fixture
def inputs():
    data = json.loads((ROOT / "input.json").read_text(encoding="utf-8"))
    return TaskInstance(**data["instances"][0]), {row["management_ip"]: InventoryRecord(**row) for row in data["inventory"]}


def test_os_metadata_normalization():
    def record_for(vendor, version):
        return inventory_record("192.0.2.1", "R1", "", "", "", "", vendor, "PTX10008", version)
    record = record_for("Juniper Networks", " 23.4R2-S1.6-EVO ")
    assert (record.os_family, record.os_version) == ("Junos", "23.4R2-S1.6-EVO")
    assert record_for("Juniper", "").os_version == ""
    assert record_for("Unknown Vendor", "23.4R2-S1.6-EVO").os_family == ""


@pytest.mark.parametrize("circuit", ["00000000-0000", "0000-0000-0000", "Direct", ""])
def test_description_contract_and_default_metric(inputs, circuit):
    instance, inventory = inputs
    instance.overrides.update(circuit_id=circuit, etc="Test circuit")
    instance.overrides.pop("isis_metric")
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    p = result.resolved[instance.instance_id]
    assert p.values["isis_metric"] == 1000
    expected = f"## GL-PO239(et-1/0/0)-DO-GW203(et-0/0/1)`100g`{circuit or 'Direct'}`Test circuit`##"
    assert p.values["description"] == expected
    assert p.sources["description"] == "rule:link_description"
    assert p.sources["os_version"] == "inventory"
    assert 'description "' + expected + '"' in result.outputs["task.clean"]
    assert "level 2 metric 1000" in result.outputs["task.clean"]
    assert "level 2 ipv6-unicast-metric 1000" in result.outputs["task.clean"]


@pytest.mark.parametrize("circuit", ["123-456", "1234567-1234", "0000-0000-000X", "direct"])
def test_bad_circuit_ids_are_blocked(inputs, circuit):
    instance, inventory = inputs
    instance.overrides["circuit_id"] = circuit
    result = ConfigEngine().generate([instance], inventory)
    assert any(d.field == "circuit_id" and d.code == "format" for d in result.diagnostics)
    assert not result.outputs["task.clean"]


@pytest.mark.parametrize("field,value", [("description", "override"), ("crc_alarm_id", 123), ("qdrop_alarm_id", 123), ("platform", "PTX10008")])
def test_removed_inputs_cannot_bypass_engine(inputs, field, value):
    instance, inventory = inputs
    instance.overrides[field] = value
    result = ConfigEngine().generate([instance], inventory)
    assert any(d.field == field for d in result.diagnostics)
    assert not result.valid_instance_ids


def test_unsafe_inventory_name_blocked(inputs):
    instance, inventory = inputs
    key = instance.target_management_ip
    inventory[key] = replace(inventory[key], name='bad"\nset evil')
    result = ConfigEngine().generate([instance], inventory)
    assert any(d.code == "inventory_name" for d in result.diagnostics)
    assert not result.valid_instance_ids


def test_router_selection_updates_os_and_removes_obsolete_fields(tmp_path, inputs):
    app = QApplication.instance() or QApplication([])
    instance, inventory = inputs
    key = instance.target_management_ip
    inventory["192.0.2.240"] = replace(inventory[key], management_ip="192.0.2.240", name="Router-2", os_version="OTHER-OS")
    inventory["192.0.2.241"] = replace(inventory[key], management_ip="192.0.2.241", name="Legacy", os_version="")
    service = BuilderService()
    service.inventory = inventory
    service.project.instances = [instance]
    window = MainWindow(service, QSettings(str(tmp_path / "revisions.ini"), QSettings.IniFormat))
    assert not {"platform", "description", "crc_alarm_id", "qdrop_alarm_id"} & window.form.widgets.keys()
    assert not {"platform", "description", "crc_alarm_id", "qdrop_alarm_id"} & set(window.table_model.columns)
    assert {"circuit_id", "etc"} <= window.form.widgets.keys()
    assert window.form.widgets["isis_metric"].placeholderText() == "default: 1000"
    assert not window.form.widgets["os_version"].isEnabled()
    window.router.setCurrentIndex(window.router.findData("192.0.2.240"))
    assert window.form.widgets["os_version"].text() == "OTHER-OS"
    assert not {"os_family", "os_version"} & instance.overrides.keys()
    assert window.form.widgets["os_family"].currentData() == "Junos"
    window.router.setCurrentIndex(window.router.findData("192.0.2.241"))
    assert window.form.widgets["os_version"].isEnabled()
    assert window.form.widgets["os_version"].text() == ""
    for widget in window.form.widgets.values():
        if isinstance(widget, QComboBox):
            assert "상속" not in widget.itemText(0)
        else:
            assert "상속" not in widget.placeholderText()
    window.dirty = False
    window.close()
