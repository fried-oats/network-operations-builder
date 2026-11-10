import csv
import json
from dataclasses import asdict
from pathlib import Path
import pytest
from openpyxl import load_workbook
from app.bulk.io import BulkIO, export_report
from app.domain import Diagnostic, Project
from app.inventory.normalization import inventory_record
from app.inventory.api_repository import API_INVENTORY_SOURCE
from app.persistence.project import load_project, save_project


def test_inventory_canonical_normalization():
    record = inventory_record(" 2001:db8::1 ", "Router", "Core", "G", "Seoul", "NOC", "Juniper Networks", "ptx10008")
    assert record.manufacturer == "Juniper" and record.model == "PTX10008"
    assert record.management_ip == "2001:db8::1"


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_current_template_and_missing_version(tmp_path, registry, suffix):
    io = BulkIO(registry)
    path = tmp_path / f"bulk.{suffix}"
    io.export_template(path)
    assert io.load(path) == ([], {})
    if suffix == "csv":
        text = path.read_text(encoding="utf-8-sig")
        path.write_text(text.replace(io.contract["schema_version"], "0.0.1"), encoding="utf-8-sig")
    else:
        wb = load_workbook(path)
        wb["Metadata"]["B2"] = "0.0.1"
        wb.save(path)
        wb.close()
    with pytest.raises(ValueError, match="버전"):
        io.load(path)


def test_header_only_csv_rejected(tmp_path, registry):
    io = BulkIO(registry)
    path = tmp_path / "bulk.csv"
    io.export_template(path)
    path.write_text(path.read_text(encoding="utf-8-sig").splitlines()[0] + "\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="메타데이터"):
        io.load(path)


@pytest.mark.parametrize("sheet,cell", [("Parameters", "C2"), ("Common Defaults", "B2")])
def test_xlsx_formulas_rejected(tmp_path, registry, sheet, cell):
    path = tmp_path / "bulk.xlsx"
    io = BulkIO(registry)
    io.export_template(path)
    wb = load_workbook(path)
    wb[sheet][cell] = "=1+1"
    wb.save(path)
    wb.close()
    with pytest.raises(ValueError, match="수식"):
        io.load(path)


def test_project_roundtrip_and_strict_version(tmp_path, instance):
    path = tmp_path / "project.nobproj"
    project = Project(instances=[instance], common_overrides={"mtu": 9000})
    save_project(path, project)
    assert json.loads(path.read_text(encoding="utf-8"))["inventory_source"] == API_INVENTORY_SOURCE
    assert load_project(path) == project
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tool_versions"]["schema"] = "0"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="버전"):
        load_project(path)


def test_atomic_save_preserves_original_on_failure(tmp_path, instance):
    path = tmp_path / "project.nobproj"
    project = Project(instances=[instance])
    save_project(path, project)
    original = path.read_bytes()
    project.common_overrides["bad"] = object()
    with pytest.raises(TypeError):
        save_project(path, project)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_report_formula_escape(tmp_path):
    path = tmp_path / "errors.csv"
    export_report(path, [Diagnostic("=CMD()", "field", "bad", "message", "+unsafe")])
    text = path.read_text(encoding="utf-8-sig")
    assert "'=CMD()" in text and "'+unsafe" in text
