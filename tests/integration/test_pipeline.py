import copy
import csv
from app.bulk.io import BulkIO
from app.engine.core import ConfigEngine
from app.services.builder import BuilderService


def test_single_equals_bulk_and_ten_rows(tmp_path, synthetic_registry, instance, inventory):
    io = BulkIO(synthetic_registry)
    path = tmp_path / "bulk.csv"
    single = ConfigEngine(synthetic_registry).generate([instance], inventory)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*io.contract, *io.columns])
        writer.writeheader()
        for n in range(10):
            writer.writerow({**io.contract, "instance_id": f"IF-{n:03}", "target_management_ip": instance.target_management_ip,
                             **instance.overrides, "local_interface": f"test-{n}", "ipv4_address": f"192.0.2.{n + 1}/32"})
    rows, common = io.load(path)
    bulk = ConfigEngine(synthetic_registry).generate(rows, inventory, common)
    assert not bulk.diagnostics
    assert len(bulk.valid_instance_ids) == 10
    assert len(bulk.outputs["router.clean"].splitlines()) == 10
    one = ConfigEngine(synthetic_registry).generate(rows[:1], inventory)
    assert single.outputs["task.clean"] == one.outputs["task.clean"]


def test_rejected_import_preserves_project(tmp_path, registry, instance):
    service = BuilderService(registry)
    service.project.instances = [instance]
    path = tmp_path / "bad.csv"
    path.write_text("instance_id\nBAD\n", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        service.import_bulk(path)
    assert service.project.instances == [instance]


def test_export_revalidates_and_line_endings(tmp_path, synthetic_registry, instance, inventory):
    service = BuilderService(synthetic_registry)
    service.inventory = inventory
    service.project.instances = [instance]
    path = tmp_path / "out.txt"
    service.export_config(path, "task.clean", "CRLF")
    assert path.read_bytes().endswith(b"\r\n")
    instance.overrides["mtu"] = "bad"
    import pytest
    with pytest.raises(ValueError):
        service.export_config(path, "task.clean")


def test_csv_import_preserves_gui_common_defaults(tmp_path, registry):
    service = BuilderService(registry)
    service.project.common_overrides = {"mtu": 9000}
    path = tmp_path / "bulk.csv"
    service.bulk.export_template(path)
    service.import_bulk(path)
    assert service.project.common_overrides == {"mtu": 9000}
