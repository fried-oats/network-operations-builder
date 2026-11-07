import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from dataclasses import replace
import shutil
import pytest
from app.domain import Capability, InventoryRecord, TaskInstance
from app.engine.registry import Registry


@pytest.fixture
def registry():
    return Registry()


@pytest.fixture
def inventory():
    record = InventoryRecord("10.0.0.1", "Router-A", "Core", "G", "Seoul", "NOC", "Juniper", "PTX10008")
    return {record.management_ip: record}


@pytest.fixture
def instance():
    return TaskInstance("IF-001", target_management_ip="10.0.0.1", overrides={
        "os_family": "Junos", "os_version": "TEST-ONLY", "interface_type": "TEST-ONLY",
        "local_interface": "test-0", "peer_name": "Router-B", "peer_interface": "test-1",
        "ipv4_address": "192.0.2.1/30",
    })


@pytest.fixture
def synthetic_registry(tmp_path, registry):
    """Infrastructure test double. NOT an approved Junos syntax/capability fixture."""
    root = tmp_path / "definitions"
    shutil.copytree(registry.root, root)
    result = Registry(root)
    template = result.templates["junos.interface.create"]
    result.templates[template.template_id] = replace(template, approved=True)
    (root / "templates" / template.filename).write_text(
        "set TEST_ONLY {{ parameters.local_interface }} mtu {{ parameters.mtu }}\n", encoding="utf-8")
    features = {spec["capability"]: "supported" for spec in result.schemas["interface.create"].fields.values() if "capability" in spec}
    result.capability = Capability(({"match": {"manufacturer": "Juniper", "model": "PTX10008", "os_family": "Junos", "os_version": "TEST-ONLY", "interface_type": "TEST-ONLY"}, "features": features},))
    return result
