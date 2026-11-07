import copy
import csv
import json
from pathlib import Path
import pytest
from app.domain import InventoryRecord, TaskInstance
from app.engine.core import ConfigEngine
from app.engine.junos import lower_cos
from app.services.builder import BuilderService

ROOT = Path(__file__).parent


@pytest.fixture
def golden():
    data = json.loads((ROOT / "ptx10008_backbone/input.json").read_text(encoding="utf-8"))
    inventory = {row["management_ip"]: InventoryRecord(**row) for row in data["inventory"]}
    return TaskInstance(**data["instances"][0]), inventory


def test_golden_rules_and_provenance(golden):
    instance, inventory = golden
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    p = result.resolved[instance.instance_id]
    assert p.values["ldp_enabled"] is True
    assert p.sources["ldp_enabled"] == "rule:family_mpls"
    assert p.values["qdrop_alarm_id"] == 8657
    assert p.values["crc_alarm_id"] == 9657
    assert p.sources["qdrop_alarm_id"] == "rule:rmon_alarm_base"
    assert not p.values.get("ipv6_filter_output")
    text = result.outputs["task.clean"]
    assert "family inet6 filter output" not in text
    assert "speed 100g\n" in text
    assert "passive" not in text
    assert any(c.target == "interfaces et-1/0/0 ether-options" and c.property == "fec" for c in result.changes)
    for section in result.sections:
        lines = result.outputs[section.output_kind].splitlines()
        assert tuple(lines[section.start_line - 1:section.end_line]) == section.commands


@pytest.mark.parametrize("ifindex", [1, 525, 658, 1001])
def test_confirmed_rmon_formula(golden, ifindex):
    instance, inventory = golden
    instance.overrides["ifindex"] = ifindex
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    p = result.resolved[instance.instance_id]
    assert p.values["qdrop_alarm_id"] == 8000 + ifindex
    assert p.values["crc_alarm_id"] == 9000 + ifindex
    assert f"jnxCosQstatTotalDropPkts.{ifindex}.0" in result.outputs["task.clean"]
    assert f"ifJnxInFrameErrors.{ifindex}" in result.outputs["task.clean"]


@pytest.mark.parametrize("field,value", [
    ("os_version", "23.4R2-other"), ("interface_type", "ae"), ("fec", "rs"),
    ("speed", "400g"), ("mtu", 9000), ("isis_level", 1),
    ("isis_hello_interval", 5), ("circuit_id", "invalid"), ("description", "manual"),
    ("scheduler_map", "unverified"), ("local_interface", "et-1/0/0 disable"),
    ("ipv4_filter_input", "Filter invalid-token"),
])
def test_unverified_variants_blocked(golden, field, value):
    instance, inventory = golden
    instance.overrides[field] = value
    result = ConfigEngine().generate([instance], inventory)
    assert result.diagnostics
    assert not result.valid_instance_ids
    assert not result.outputs["task.clean"]


def test_explicit_ldp_disable_wins(golden):
    instance, inventory = golden
    instance.overrides["ldp_enabled"] = "disable"
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    text = result.outputs["task.clean"]
    assert "set protocols ldp" not in text and "ldp-synchronization" not in text
    assert "family mpls" in text


def test_derived_alarm_collision_blocks_all_owners(golden):
    instance, inventory = golden
    other = copy.deepcopy(instance)
    other.instance_id = "IF-002"
    other.overrides.update(local_interface="et-1/0/1", ipv4_address="112.174.87.50/30",
                           ipv6_address="2400::100:112:174:87:32/126", ifindex=1657)
    # QDrop 8000+1657 overlaps CRC 9000+657.
    result = ConfigEngine().generate([instance, other], inventory)
    assert {d.instance_id for d in result.diagnostics if d.code == "duplicate_alarm"} == {"IF-001", "IF-002"}
    assert not result.valid_instance_ids


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_actual_golden_single_equals_bulk(tmp_path, golden, suffix):
    instance, inventory = golden
    service = BuilderService()
    service.inventory = inventory
    service.project.instances = [instance]
    expected = service.generate().outputs["task.clean"]
    path = tmp_path / f"golden.{suffix}"
    service.bulk.export_template(path)
    row = {"instance_id": instance.instance_id, "target_management_ip": instance.target_management_ip, **instance.overrides}
    if suffix == "csv":
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[*service.bulk.contract, *service.bulk.columns])
            writer.writeheader()
            writer.writerow({**service.bulk.contract, **row})
    else:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        wb["Parameters"].append([row.get(k) for k in service.bulk.columns])
        wb.save(path)
        wb.close()
    service.import_bulk(path)
    actual = service.generate()
    assert not actual.diagnostics
    assert actual.outputs["task.clean"] == expected


def test_external_cos_fragment(registry):
    instance = TaskInstance("COS-REF", target_management_ip="192.0.2.239")
    p = {"local_interface": "ae0", "cos_mode": "external"}
    changes = lower_cos(instance, p, registry.profiles["hub-gate"])
    actual = "".join(f"{c.operation} {c.target} {c.property} {c.value}\n" for c in changes)
    assert actual == (ROOT / "cos_external/reference.set").read_text(encoding="utf-8")


def test_shipped_project_reproduces_golden():
    service = BuilderService()
    assert service.open_project(ROOT.parents[1] / "examples/ptx10008_golden.nobproj") is None
    result = service.generate()
    assert not result.diagnostics
    assert result.outputs["task.clean"] == (ROOT / "ptx10008_backbone/expected.set").read_text(encoding="utf-8")


def test_ten_actual_junos_bulk_rows(tmp_path, golden):
    instance, inventory = golden
    service = BuilderService()
    service.inventory = inventory
    path = tmp_path / "ten.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*service.bulk.contract, *service.bulk.columns])
        writer.writeheader()
        for n in range(10):
            overrides = {**instance.overrides, "local_interface": f"et-1/0/{n}", "ifindex": 657 + n,
                         "ipv4_address": f"192.0.2.{n + 1}/32", "ipv6_address": f"2001:db8::{n + 1}/128"}
            writer.writerow({**service.bulk.contract, "instance_id": f"IF-{n:03}",
                             "target_management_ip": instance.target_management_ip, **overrides})
    service.import_bulk(path)
    result = service.generate()
    assert not result.diagnostics
    assert len(result.valid_instance_ids) == 10
    assert len([c for c in result.changes if c.property == "syslog-subtag"]) == 20
    assert "set protocols ldp interface et-1/0/9.0" in result.outputs[f"router:{instance.target_management_ip}.clean"]
