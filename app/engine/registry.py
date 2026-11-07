from pathlib import Path
import sys
import yaml
from app.domain import Capability, Profile, Schema, TaskDefinition, Template


def definitions_path() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "definitions"


class Registry:
    def __init__(self, root: Path | None = None):
        self.root = root or definitions_path()
        self.tasks = {}
        self.profiles = {}
        self.schemas = {}
        self.templates = {}
        for folder, cls, key, destination in (
            ("tasks", TaskDefinition, "task_id", self.tasks),
            ("profiles", Profile, "profile_id", self.profiles),
            ("schemas", Schema, "schema_id", self.schemas),
            ("templates", Template, "template_id", self.templates),
        ):
            for path in sorted((self.root / folder).glob("*.yaml")):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if data[key] in destination:
                    raise ValueError(f"중복 정의: {data[key]}")
                destination[data[key]] = cls(**data)
        rules = []
        for path in sorted((self.root / "capabilities").glob("*.yaml")):
            rules.extend(yaml.safe_load(path.read_text(encoding="utf-8"))["rules"])
        self.capability = Capability(tuple(rules))

    def contract(self):
        task = self.tasks["interface.create"]
        profile = self.profiles["hub-gate"]
        return {"task_id": task.task_id, "schema_version": self.schemas[task.schema_id].version,
                "template_format_version": "1.0", "profile_id": profile.profile_id,
                "profile_version": profile.version}
