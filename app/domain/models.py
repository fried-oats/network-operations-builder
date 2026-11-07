from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    version: str
    name: str
    schema_id: str
    template_id: str


@dataclass
class TaskInstance:
    instance_id: str
    task_id: str = "interface.create"
    task_version: str = "1.3.0"
    target_management_ip: str = ""
    profile_id: str = "hub-gate"
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Profile:
    profile_id: str
    version: str
    defaults: dict[str, Any]
    locked: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    rules: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Schema:
    schema_id: str
    version: str
    fields: dict[str, dict[str, Any]]
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Capability:
    rules: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Template:
    template_id: str
    version: str
    approved: bool
    filename: str


@dataclass(frozen=True)
class InventoryRecord:
    management_ip: str
    name: str
    hierarchy: str
    group: str
    location: str
    operation_team: str
    manufacturer: str
    model: str
    os_family: str = ""
    os_version: str = ""


@dataclass
class ResolvedParameters:
    values: dict[str, Any]
    sources: dict[str, str]


@dataclass(frozen=True)
class Diagnostic:
    instance_id: str
    field: str
    code: str
    message: str
    value: Any = None
    row: int | None = None
    remedy: str = "입력값과 정책/지원 자료를 확인하세요."


@dataclass(frozen=True)
class ConfigChange:
    management_ip: str
    target: str
    property: str
    value: Any
    owner_instance_id: str
    operation: str = "set"
    group: str = ""
    quoted: bool = False


@dataclass(frozen=True)
class GeneratedSection:
    instance_id: str
    management_ip: str
    output_kind: str
    start_line: int
    end_line: int
    commands: tuple[str, ...]


@dataclass
class GenerationResult:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    resolved: dict[str, ResolvedParameters] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    sections: list[GeneratedSection] = field(default_factory=list)
    changes: list[ConfigChange] = field(default_factory=list)
    valid_instance_ids: list[str] = field(default_factory=list)


@dataclass
class Project:
    project_format_version: str = "1.0"
    name: str = "새 프로젝트"
    inventory_source: str = ""
    common_overrides: dict[str, Any] = field(default_factory=dict)
    instances: list[TaskInstance] = field(default_factory=list)
    tool_versions: dict[str, str] = field(default_factory=lambda: {
        "task": "1.3.0", "schema": "1.3.0", "profile": "1.3.0", "template": "1.3.0"})
