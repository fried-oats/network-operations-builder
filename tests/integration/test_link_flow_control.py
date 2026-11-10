import csv
import json
from pathlib import Path
import pytest
from app.domain import InventoryRecord, TaskInstance
from app.services.builder import BuilderService

CASE = Path(__file__).parents[1] / "golden/ptx10008_backbone/input.json"


def make_service(mode, isis_mode):
    data = json.loads(CASE.read_text(encoding="utf-8"))
    instance = TaskInstance(**data["instances"][0])
    instance.overrides.update(local_interface="et-3/0/32", link_mode=mode,
        isis_enabled=isis_mode != "off", isis_passive=isis_mode == "passive", cos_enabled=False)
    service = BuilderService()
    service.project.instances = [instance]
    service.apply_api_inventory({r["management_ip"]: InventoryRecord(**r) for r in data["inventory"]})
    return service


@pytest.mark.parametrize("mode", ["backbone", "external"])
@pytest.mark.parametrize("isis_mode", ["p2p", "passive", "off"])
def test_link_mode_alone_controls_flow_control(mode, isis_mode):
    service = make_service(mode, isis_mode)
    result = service.generate()
    assert not result.diagnostics
    lines = result.outputs["task.clean"].splitlines()
    physical = [line for line in lines if line.startswith("set interfaces et-3/0/32 ether-options ")]
    expected = (["set interfaces et-3/0/32 ether-options no-flow-control"] if mode == "external" else [])
    expected.append("set interfaces et-3/0/32 ether-options fec none")
    assert physical == expected
    assert not any("class-of-service" in line for line in lines)
    changes = [c for c in result.changes if c.property == "no-flow-control"]
    assert len(changes) == (1 if mode == "external" else 0)
    if changes:
        assert changes[0].target == "interfaces et-3/0/32 ether-options"


@pytest.mark.parametrize("mode", ["backbone", "external"])
@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_flow_control_single_bulk_match(tmp_path, mode, suffix):
    service = make_service(mode, "p2p")
    expected = service.generate().outputs["task.clean"]
    instance = service.project.instances[0]
    path = tmp_path / f"flow.{suffix}"
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
        wb["Parameters"].append([row.get(key) for key in service.bulk.columns])
        wb.save(path)
        wb.close()
    service.import_bulk(path)
    actual = service.generate()
    assert not actual.diagnostics
    assert actual.outputs["task.clean"] == expected
