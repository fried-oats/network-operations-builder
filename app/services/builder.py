from dataclasses import replace
from pathlib import Path
from app.bulk.io import BulkIO
from app.domain import Project
from app.engine.core import ConfigEngine
from app.engine.registry import Registry
from app.inventory.api_repository import API_INVENTORY_SOURCE, fetch_api_inventory
from app.persistence.project import load_project, save_project


class BuilderService:
    def __init__(self, registry=None):
        self.registry = registry or Registry()
        self.engine = ConfigEngine(self.registry)
        self.bulk = BulkIO(self.registry)
        self.project = Project()
        self.inventory = {}
        self.result = None

    def generate(self):
        self.result = self.engine.generate(self.project.instances, self.inventory, self.project.common_overrides)
        rows = {id(instance): number for number, instance in enumerate(self.project.instances, 2)}
        by_iid = {i.instance_id: rows[id(i)] for i in self.project.instances}
        self.result.diagnostics = [replace(d, row=by_iid.get(d.instance_id)) for d in self.result.diagnostics]
        return self.result

    def fetch_api_inventory(self, settings, user_id="", password=""):
        return fetch_api_inventory(settings, user_id, password)

    def apply_api_inventory(self, records):
        self.inventory = records
        self.project.inventory_source = API_INVENTORY_SOURCE
        self.result = None

    def load_api_inventory(self, settings, user_id="", password=""):
        records = self.fetch_api_inventory(settings, user_id, password)
        self.apply_api_inventory(records)

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
        if project.inventory_source not in {"", API_INVENTORY_SOURCE}:
            warning = "기존 CSV Inventory 참조를 API로 전환했습니다. 파일 → API Inventory 불러오기로 라우터 목록을 불러오세요. Task/공통값은 유지했습니다."
        else:
            warning = "파일 → API Inventory 불러오기로 라우터 목록을 다시 불러오세요. Task/공통값은 유지했습니다."
        if not project.instances:
            warning = None
        project.inventory_source = API_INVENTORY_SOURCE
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
