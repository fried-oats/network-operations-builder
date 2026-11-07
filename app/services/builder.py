from dataclasses import replace
from pathlib import Path
from app.bulk.io import BulkIO
from app.domain import Project
from app.engine.core import ConfigEngine
from app.engine.registry import Registry
from app.inventory import CsvInventoryRepository
from app.persistence.project import load_project, save_project


class BuilderService:
    def __init__(self, registry=None):
        self.registry = registry or Registry()
        self.engine = ConfigEngine(self.registry)
        self.bulk = BulkIO(self.registry)
        self.project = Project()
        self.inventory = {}
        self.result = None

    def load_inventory(self, path):
        records = CsvInventoryRepository().load(path)
        self.inventory = records
        self.project.inventory_source = str(Path(path).resolve())
        self.result = None

    def generate(self):
        self.result = self.engine.generate(self.project.instances, self.inventory, self.project.common_overrides)
        rows = {id(instance): number for number, instance in enumerate(self.project.instances, 2)}
        by_iid = {i.instance_id: rows[id(i)] for i in self.project.instances}
        self.result.diagnostics = [replace(d, row=by_iid.get(d.instance_id)) for d in self.result.diagnostics]
        return self.result

    def import_bulk(self, path):
        instances, common = self.bulk.load(path)
        self.project.instances = instances
        if Path(path).suffix.lower() == ".xlsx":
            self.project.common_overrides = common
        self.result = None

    def open_project(self, path):
        project = load_project(path)
        records = {}
        warning = None
        if project.inventory_source:
            try:
                records = CsvInventoryRepository().load(project.inventory_source)
            except (OSError, ValueError) as exc:
                warning = f"Inventory를 다시 로드하세요: {exc}"
        self.project, self.inventory, self.result = project, records, None
        return warning

    def save_project(self, path):
        save_project(path, self.project)

    def export_config(self, path, kind, newline="LF"):
        # Always revalidate current inputs, including after a preview was generated.
        result = self.generate()
        text = result.outputs.get(kind, "")
        if not text:
            raise ValueError("검증을 통과한 Config가 없습니다")
        if newline not in {"LF", "CRLF"}:
            raise ValueError("LF/CRLF만 지원합니다")
        Path(path).write_bytes(text.replace("\n", "\r\n" if newline == "CRLF" else "\n").encode("utf-8"))
