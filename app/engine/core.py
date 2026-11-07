"""Pure Python engine: no Qt imports or device/network operations."""
from collections import defaultdict
from ipaddress import ip_interface
import re
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from app.domain import ConfigChange, Diagnostic, GeneratedSection, GenerationResult, ResolvedParameters
from .registry import Registry
from . import junos


def unspecified(value):
    return value is None or isinstance(value, str) and not value.strip()


def parse(value, spec):
    kind = spec["type"]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"enable", "disable", "true", "false", "on", "off"}:
            return value.strip().lower() in {"enable", "true", "on"}
        raise ValueError("enable/disable 또는 true/false가 필요합니다")
    if kind == "integer":
        if isinstance(value, bool) or not re.fullmatch(r"[+-]?\d+", str(value).strip()):
            raise ValueError("정수가 필요합니다")
        return int(value)
    if not isinstance(value, str):
        raise ValueError("문자열이 필요합니다")
    value = value.strip()
    if any(ord(c) < 32 for c in value) or any(c in value for c in '\";{}\\'):
        raise ValueError("CLI 제어 문자/개행/인용 문자는 허용되지 않습니다")
    if kind == "ip_interface":
        if "/" not in value:
            raise ValueError("주소/프리픽스가 필요합니다")
        address = ip_interface(value)
        if address.version != spec["family"]:
            raise ValueError("IP 주소 패밀리가 다릅니다")
        # Preserve validated IPv6 spelling supplied in a Golden/input; collision checks canonicalize separately.
        return value if address.version == 6 else str(address)
    return value


class ConfigEngine:
    def __init__(self, registry=None):
        self.registry = registry or Registry()

    def generate(self, instances, inventory, common=None):
        result = GenerationResult()
        common = common or {}
        seen_ids = defaultdict(list)
        for index, instance in enumerate(instances):
            seen_ids[instance.instance_id].append(index)
        duplicate_ids = {key for key, indices in seen_ids.items() if len(indices) > 1}
        candidates = []
        for instance in instances:
            iid = instance.instance_id
            def error(field, code, message, value=None):
                result.diagnostics.append(Diagnostic(iid, field, code, message, value))
            if not iid or iid in duplicate_ids:
                error("instance_id", "duplicate_id" if iid else "required", "Instance ID가 비어 있거나 중복됩니다", iid)
            task = self.registry.tasks.get(instance.task_id)
            profile = self.registry.profiles.get(instance.profile_id)
            if not task or task.version != instance.task_version or not profile:
                error("task_id", "definition_version", "지원되지 않는 Task/Profile 또는 버전입니다")
                continue
            schema = self.registry.schemas[task.schema_id]
            values, sources = {}, {}
            # Parse each supplied layer; false is always explicit, never an empty value.
            for source, layer in (("system", schema.defaults), ("profile", profile.defaults), ("common", common), ("override", instance.overrides)):
                if not isinstance(layer, dict):
                    error("overrides", "type", "파라미터는 객체여야 합니다")
                    continue
                for key, value in layer.items():
                    if key not in schema.fields:
                        error(key, "unknown_field", "Schema에 없는 필드입니다", value)
                        continue
                    if schema.fields[key].get("derived"):
                        error(key, "derived_field", "자동 계산 필드는 직접 입력할 수 없습니다", value)
                        continue
                    if unspecified(value):
                        continue
                    try:
                        parsed = parse(value, schema.fields[key])
                        if source in {"common", "override"} and key in profile.locked and parsed != parse(profile.locked[key], schema.fields[key]):
                            raise ValueError("Profile 고정값을 변경할 수 없습니다")
                        values[key], sources[key] = parsed, source
                    except ValueError as exc:
                        error(key, "parse", str(exc), value)
            for key, value in profile.locked.items():
                values[key], sources[key] = parse(value, schema.fields[key]), "profile.locked"
            resolved = ResolvedParameters(values, sources)
            result.resolved[iid] = resolved
            record = inventory.get(instance.target_management_ip)
            if record:
                for key in ("os_family", "os_version"):
                    supplied = getattr(record, key, "")
                    if supplied:
                        try:
                            supplied = parse(supplied, schema.fields[key])
                            if key in values and sources[key] in {"common", "override"} and values[key] != supplied:
                                error(key, "inventory_mismatch", "선택 장비의 Inventory OS 정보와 다릅니다", values[key])
                            values[key], sources[key] = supplied, "inventory"
                        except ValueError as exc:
                            error(key, "inventory_os", str(exc), supplied)
                if schema.fields.get("description", {}).get("derived"):
                    try:
                        junos.resolve_description(values, sources, record)
                    except ValueError as exc:
                        error("description", "inventory_name", str(exc), record.name)
            golden_scope = junos.is_golden_scope(record, values)
            if golden_scope or schema.fields.get("crc_alarm_id", {}).get("derived"):
                junos.resolve_rules(values, sources, profile)
                for key, locked in profile.locked.items():
                    if values.get(key) != parse(locked, schema.fields[key]):
                        error(key, "profile_rule_conflict", "자동 적용 규칙과 Profile 고정값이 충돌합니다", values.get(key))
            if golden_scope:
                if not re.fullmatch(r"et-\d+/\d+/\d+", values.get("local_interface", "")):
                    error("local_interface", "interface_format", "확인된 형식은 et-slot/pic/port, unit 0입니다")
                if values.get("isis_enabled"):
                    expected_values = (("isis_level", 2),) if junos.passive_active(values) and profile.rules.get("isis_passive_overrides") else (("isis_passive", False), ("isis_level", 2), ("isis_hello_interval", 10), ("isis_hold_time", 30))
                    for key, expected in expected_values:
                        if values.get(key) != expected:
                            error(key, "needs_golden_config", f"현재 Golden 범위: {key}={expected}")
            if not record:
                error("target_management_ip", "inventory", "Inventory에서 관리 IP를 선택하세요", instance.target_management_ip)
            for key, spec in schema.fields.items():
                value = values.get(key)
                active = not spec.get("visible_when") or bool(values.get(spec["visible_when"]))
                if spec.get("required") or spec.get("required_when") and values.get(spec["required_when"]):
                    if value is None:
                        error(key, "required", "필수값입니다")
                if value is None:
                    continue
                if "choices" in spec and value not in spec["choices"]:
                    error(key, "choice", "허용값이 아닙니다", value)
                if spec.get("pattern") and isinstance(value, str) and not re.fullmatch(spec["pattern"], value):
                    error(key, "format", "Schema에서 허용한 입력 형식이 아닙니다", value)
                if isinstance(value, int) and not isinstance(value, bool) and (value < spec.get("min", value) or value > spec.get("max", value)):
                    error(key, "range", "허용 범위를 벗어났습니다", value)
                if active and value and spec.get("requires") and not values.get(spec["requires"]):
                    error(key, "dependency", f"{spec['requires']} 값이 필요합니다", value)
                constraints = profile.constraints.get(key, {})
                if "choices" in constraints and value not in constraints["choices"] or isinstance(value, int) and (value < constraints.get("min", value) or value > constraints.get("max", value)):
                    error(key, "profile_constraint", "Profile 제한 위반입니다", value)
                if record and active and value is not False and "capability" in spec:
                    status = self.capability_status(record, values, spec["capability"], value)
                    if status != "supported":
                        error(key, f"capability_{status}", f"{record.model}/{values.get('os_version', '?')}: {key} {status}; Golden 지원 범위를 확인하세요", value)
            candidates.append((instance, values))
        self.cross_validate(candidates, result)
        # Never render any member of a conflicting group, including the first row.
        invalid = {d.instance_id for d in result.diagnostics}
        rendered = []
        for instance, values in candidates:
            if instance.instance_id in invalid:
                continue
            task = self.registry.tasks[instance.task_id]
            template = self.registry.templates[task.template_id]
            if not template.approved:
                result.diagnostics.append(Diagnostic(instance.instance_id, "template", "needs_golden_config", "TODO: needs golden config — 승인된 실제 CLI와 입력/지원 범위가 필요합니다"))
                continue
            schema = self.registry.schemas[task.schema_id]
            effective = {key: value for key, value in values.items()
                         if not schema.fields[key].get("visible_when") or values.get(schema.fields[key]["visible_when"])}
            record = inventory.get(instance.target_management_ip)
            changes = (junos.lower(instance, effective, self.registry.profiles[instance.profile_id])
                       if junos.is_golden_scope(record, effective) else self.semantic_changes(instance, effective))
            result.changes.extend(changes)
            env = Environment(loader=FileSystemLoader(self.registry.root / "templates"), undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
            try:
                text = env.get_template(template.filename).render(parameters=effective, instance=instance, changes=changes)
                commands = tuple(text.strip().splitlines())
                if not commands or any(line and (not line.startswith("set ") or "\r" in line) for line in commands):
                    raise ValueError("템플릿은 비어 있지 않은 검증된 set CLI만 출력해야 합니다")
            except Exception as exc:
                result.diagnostics.append(Diagnostic(instance.instance_id, "template", "render", str(exc)))
                continue
            rendered.append((instance, commands))
            result.valid_instance_ids.append(instance.instance_id)
        self.build_outputs(rendered, result)
        return result

    def capability_status(self, record, values, feature, value):
        context = {"manufacturer": record.manufacturer, "model": record.model, **values}
        matches = []
        for rule in self.registry.capability.rules:
            if all(context.get(k) == v for k, v in rule["match"].items()) and feature in rule["features"]:
                support = rule["features"][feature]
                if isinstance(support, dict):
                    allowed = support.get("values")
                    status = support["status"] if allowed is None or value in allowed else "unsupported"
                else:
                    status = support
                # Supported needs a verified OS/version/interface scope, never just a model.
                if status == "supported" and not {"manufacturer", "model", "os_family", "os_version", "interface_type"} <= rule["match"].keys():
                    status = "unknown"
                matches.append(status)
        return "unsupported" if "unsupported" in matches else "supported" if "supported" in matches else "unknown"

    @staticmethod
    def semantic_changes(instance, values):
        return [ConfigChange(instance.target_management_ip, values.get("local_interface", ""), key, value, instance.instance_id)
                for key, value in values.items() if key not in {"os_family", "os_version", "platform", "interface_type", "local_interface"}]

    @staticmethod
    def cross_validate(candidates, result):
        owners = defaultdict(list)
        for instance, values in candidates:
            ip = instance.target_management_ip
            if values.get("local_interface"):
                owners[(ip, "interface", values["local_interface"])].append((instance.instance_id, "local_interface"))
            for key in ("ipv4_address", "ipv6_address"):
                if values.get(key):
                    owners[(ip, "address", str(ip_interface(values[key]).ip))].append((instance.instance_id, key))
            if values.get("rmon_enabled"):
                for key in ("crc_alarm_id", "qdrop_alarm_id"):
                    if values.get(key) is not None:
                        owners[(ip, "alarm", values[key])].append((instance.instance_id, key))
        for (ip, kind, value), entries in owners.items():
            if len(entries) > 1:
                for iid, key in entries:
                    result.diagnostics.append(Diagnostic(iid, key, f"duplicate_{kind}", f"{ip}: {value} 충돌 ({', '.join(x[0] for x in entries)})", value))

    @staticmethod
    def build_outputs(rendered, result):
        for view in ("task", "router"):
            ordered = rendered if view == "task" else sorted(rendered, key=lambda item: item[0].target_management_ip)
            for mode in ("clean", "annotated"):
                kind = f"{view}.{mode}"
                lines = []
                seen = {}
                for instance, commands in ordered:
                    if mode == "annotated":
                        lines.append(f"// TASK {instance.instance_id} | {instance.task_id} | {instance.target_management_ip}")
                    for command in commands:
                        dedup_key = (instance.target_management_ip, command)
                        if command and view == "router" and dedup_key in seen:
                            start = seen[dedup_key]
                        else:
                            lines.append(command)
                            start = len(lines)
                            seen[dedup_key] = start
                        result.sections.append(GeneratedSection(instance.instance_id, instance.target_management_ip, kind, start, start, (command,)))
                result.outputs[kind] = "\n".join(lines) + ("\n" if lines else "")
        # Device exports each have their own line coordinate system.
        targets = sorted({instance.target_management_ip for instance, _ in rendered})
        if targets:
            for ip in targets:
                subset = [(instance, commands) for instance, commands in rendered if instance.target_management_ip == ip]
                # Reuse base mapping without recursion through this method.
                for mode in ("clean", "annotated"):
                    kind = f"router:{ip}.{mode}"
                    lines, seen = [], {}
                    for instance, commands in subset:
                        if mode == "annotated":
                            lines.append(f"// TASK {instance.instance_id} | {instance.task_id} | {ip}")
                        for command in commands:
                            if not command or command not in seen:
                                lines.append(command)
                                seen[command] = len(lines)
                            line = seen[command]
                            result.sections.append(GeneratedSection(instance.instance_id, ip, kind, line, line, (command,)))
                    result.outputs[kind] = "\n".join(lines) + ("\n" if lines else "")
