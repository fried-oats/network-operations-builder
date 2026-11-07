from dataclasses import asdict
from pathlib import Path
import json
import os
import tempfile
from app.domain import Project, TaskInstance

MAX_FILE_BYTES = 20 * 1024 * 1024


def save_project(path, project):
    destination = Path(path)
    payload = asdict(project)
    if project.inventory_source:
        payload["inventory_source"] = os.path.relpath(Path(project.inventory_source).resolve(), destination.parent.resolve())
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_project(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("프로젝트 파일 크기 제한 초과")
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"중복 JSON 키: {key}")
            result[key] = value
        return result
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"잘못된 JSON 값: {x}")))
    expected = Project().tool_versions
    if not isinstance(data, dict) or data.get("project_format_version") != "1.0" or data.get("tool_versions") != expected:
        raise ValueError("지원되지 않는 프로젝트/정의 버전")
    if not isinstance(data.get("instances"), list) or len(data["instances"]) > 10000 or not isinstance(data.get("common_overrides"), dict):
        raise ValueError("잘못된 프로젝트 구조")
    for item in data["instances"]:
        if not isinstance(item, dict) or not isinstance(item.get("overrides"), dict):
            raise ValueError("잘못된 Instance 구조")
        if any(not isinstance(item.get(k), str) for k in ("instance_id", "task_id", "task_version", "target_management_ip", "profile_id")):
            raise ValueError("잘못된 Instance 필드 타입")
        if item["task_id"] != "interface.create" or item["task_version"] != expected["task"] or item["profile_id"] != "hub-gate":
            raise ValueError("지원되지 않는 Instance 정의")
    data["instances"] = [TaskInstance(**item) for item in data["instances"]]
    project = Project(**data)
    if not isinstance(project.name, str) or not isinstance(project.inventory_source, str):
        raise ValueError("잘못된 프로젝트 메타데이터")
    if project.inventory_source:
        project.inventory_source = str((path.parent / project.inventory_source).resolve())
    return project
