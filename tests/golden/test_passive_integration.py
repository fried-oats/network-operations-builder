from pathlib import Path
from dataclasses import replace
import copy
import csv
import json
import pytest
from app.domain import TaskInstance, InventoryRecord
from app.engine.core import ConfigEngine
from app.services.builder import BuilderService

CASE = Path(__file__).parent / "ptx10008_passive"


@pytest.fixture
def passive():
    data = json.loads((CASE / "input.json").read_text(encoding="utf-8"))
    return TaskInstance(**data["instances"][0]), {r["management_ip"]: InventoryRecord(**r) for r in data["inventory"]}


@pytest.mark.parametrize("peer", ["Netflix(AS2906)", "[Uplink]T-Mobile_Sprint(AS1239)", "Google(AS15169)"])
def test_carrier_names_preserved_in_description(passive, peer):
    instance, inventory = passive
    instance.overrides["peer_name"] = peer
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    expected = f"## LA-POP239(et-3/0/32)-{peer}(et-0/0/1)`100g`08882137-1239``##"
    assert result.resolved[instance.instance_id].values["description"] == expected
    assert result.outputs["task.clean"].splitlines()[0] == f'set interfaces et-3/0/32 description "{expected}"'
    assert result.outputs["task.clean"].splitlines()[1] == "set interfaces et-3/0/32 speed 100g"
    assert instance.overrides["peer_name"] == peer


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_passive_single_equals_bulk(tmp_path, passive, suffix):
    instance, inventory = passive
    service = BuilderService()
    service.inventory = inventory
    service.project.instances = [instance]
    single = service.generate()
    assert not single.diagnostics
    path = tmp_path / f"passive.{suffix}"
    service.bulk.export_template(path)
    row = {"instance_id": instance.instance_id, "target_management_ip": instance.target_management_ip, **instance.overrides}
    if suffix == "csv":
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[*service.bulk.contract, *service.bulk.columns])
            w.writeheader()
            w.writerow({**service.bulk.contract, **row})
    else:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        wb["Parameters"].append([row.get(key) for key in service.bulk.columns])
        wb.save(path)
        wb.close()
    service.import_bulk(path)
    bulk = service.generate()
    assert not bulk.diagnostics
    assert bulk.outputs["task.clean"] == single.outputs["task.clean"] == (CASE / "expected.set").read_text(encoding="utf-8")
    for section in bulk.sections:
        assert tuple(bulk.outputs[section.output_kind].splitlines()[section.start_line - 1:section.end_line]) == section.commands


def test_policy_prevents_forbidden_commands(passive):
    instance, inventory = passive
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    text = result.outputs["task.clean"]
    for command in ("family iso", "family mpls", "set protocols mpls", "set protocols ldp", "ldp-synchronization", "point-to-point", "hello-interval", "hold-time"):
        assert command not in text
    assert "level 2 metric 0\n" in text and "level 2 ipv6-unicast-metric 0\n" in text
    assert "ether-options no-flow-control\n" in text
    assert "2600:0001:0600:0010::000b/127" in text


@pytest.mark.parametrize("family", ["ipv4_address", "ipv6_address"])
def test_passive_optional_addresses(passive, family):
    instance, inventory = passive
    instance.overrides[family] = ""
    prefix = "ipv4_filter" if family == "ipv4_address" else "ipv6_filter"
    for key in list(instance.overrides):
        if key.startswith(prefix):
            instance.overrides[key] = ""
    result = ConfigEngine().generate([instance], inventory)
    assert not result.diagnostics
    assert "level 2 passive" in result.outputs["task.clean"]
    if family == "ipv6_address":
        assert "ipv6-unicast-metric" not in result.outputs["task.clean"]


def test_unverified_passive_model_blocked(passive):
    instance, inventory = passive
    ip = instance.target_management_ip
    inventory[ip] = replace(inventory[ip], model="UNKNOWN")
    result = ConfigEngine().generate([instance], inventory)
    assert any(d.field == "isis_passive" and d.code == "capability_unknown" for d in result.diagnostics)
    assert not result.valid_instance_ids


def test_switch_back_to_p2p_keeps_raw_inputs(passive):
    instance, inventory = passive
    before = copy.deepcopy(instance.overrides)
    engine = ConfigEngine()
    assert not engine.generate([instance], inventory).diagnostics
    assert instance.overrides == before
    instance.overrides["isis_passive"] = False
    result = engine.generate([instance], inventory)
    assert not result.diagnostics
    text = result.outputs["task.clean"]
    assert "level 2 metric 1000" in text
    assert "family iso" in text and "family mpls" in text
    assert "ldp-synchronization" in text and "point-to-point" in text
    # Link remains external when passive is disabled, so flow control policy remains unchanged.
    assert "ether-options no-flow-control" in text


def test_shipped_passive_project():
    service = BuilderService()
    assert "API" in service.open_project(CASE.parents[2] / "examples/ptx10008_passive.nobproj")
    data = json.loads((CASE / "input.json").read_text(encoding="utf-8"))
    service.apply_api_inventory({r["management_ip"]: InventoryRecord(**r) for r in data["inventory"]})
    result = service.generate()
    assert not result.diagnostics
    assert result.outputs["task.clean"] == (CASE / "expected.set").read_text(encoding="utf-8")
