"""Only user-approved production fixtures belong here; infrastructure doubles live elsewhere."""
from pathlib import Path
import json
import pytest
import yaml
from app.domain import InventoryRecord, TaskInstance
from app.engine.core import ConfigEngine
from app.engine.registry import Registry

cases = sorted(p.parent for p in Path(__file__).parent.glob("*/input.json"))


@pytest.mark.parametrize("case", cases or [None], ids=[p.name for p in cases] or ["awaiting-user-golden"])
def test_approved_junos_golden(case):
    if case is None:
        pytest.skip("사용자 승인 Junos Golden Config 입력/기대 결과 대기")
    metadata = yaml.safe_load((case / "metadata.yaml").read_text(encoding="utf-8"))
    assert metadata["approved_by"] and metadata["os_version"] and metadata["interface_type"]
    data = json.loads((case / "input.json").read_text(encoding="utf-8"))
    inventory = {record["management_ip"]: InventoryRecord(**record) for record in data["inventory"]}
    instances = [TaskInstance(**row) for row in data["instances"]]
    definitions = case / metadata["definitions_root"] if metadata.get("definitions_root") else None
    result = ConfigEngine(Registry(definitions)).generate(instances, inventory, data.get("common_overrides", {}))
    assert not result.diagnostics
    assert result.outputs["task.clean"] == (case / "expected.set").read_text(encoding="utf-8")
