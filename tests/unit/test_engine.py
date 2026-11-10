from dataclasses import replace
import copy
import pytest
from app.domain import Capability, TaskInstance
from app.engine.core import ConfigEngine


def codes(result):
    return {d.code for d in result.diagnostics}


def test_no_production_cli_without_golden(registry, instance, inventory):
    result = ConfigEngine(registry).generate([instance], inventory)
    assert not result.valid_instance_ids
    assert not any(result.outputs.values())
    assert "capability_unknown" in codes(result)


def test_template_gate_independent_of_capability(synthetic_registry, instance, inventory):
    registry = synthetic_registry
    key = "junos.interface.create"
    registry.templates[key] = replace(registry.templates[key], approved=False)
    result = ConfigEngine(registry).generate([instance], inventory)
    assert "needs_golden_config" in codes(result)
    assert not any(result.outputs.values())


def test_resolution_precedence_and_false(synthetic_registry, instance, inventory):
    instance.overrides.update(mtu="", isis_enabled="disable")
    result = ConfigEngine(synthetic_registry).generate([instance], inventory, {"mtu": "9000", "isis_enabled": "enable"})
    resolved = result.resolved[instance.instance_id]
    assert resolved.values["mtu"] == 9000
    assert resolved.sources["mtu"] == "common"
    assert resolved.values["isis_enabled"] is False
    assert resolved.sources["isis_enabled"] == "override"
    assert not result.diagnostics


def test_profile_lock_and_constraints(synthetic_registry, instance, inventory):
    registry = synthetic_registry
    profile = registry.profiles["hub-gate"]
    registry.profiles["hub-gate"] = replace(profile, locked={"mtu": 4484}, constraints={"isis_metric": {"max": 50}})
    instance.overrides["mtu"] = 9000
    result = ConfigEngine(registry).generate([instance], inventory)
    assert {"parse", "profile_constraint"} <= codes(result)
    assert result.resolved[instance.instance_id].values["mtu"] == 4484
    assert not result.valid_instance_ids


@pytest.mark.parametrize("key,value,code", [
    ("mtu", "1.2", "parse"), ("mtu", True, "parse"), ("mtu", "0", "range"),
    ("ipv4_address", "bad", "parse"), ("ipv6_address", "192.0.2.1/30", "parse"),
    ("ipv4_address", "192.0.2.1", "parse"), ("peer_name", "a\nset bad", "parse"),
    ("isis_enabled", "maybe", "parse"), ("isis_level", 3, "choice"),
    ("ldp_enabled", True, "dependency"), ("ipv6_filter_input", "filter", "dependency"),
    ("rmon_enabled", True, "required"), ("link_mode", "unknown-policy", "choice"),
    ("unexpected", "value", "unknown_field"),
])
def test_invalid_parameters(synthetic_registry, instance, inventory, key, value, code):
    instance.overrides[key] = value
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert code in codes(result)
    assert not result.valid_instance_ids


def test_t4000_fec_unsupported(registry, instance, inventory):
    record = inventory["10.0.0.1"]
    inventory[record.management_ip] = replace(record, model="T4000")
    result = ConfigEngine(registry).generate([instance], inventory)
    assert any(d.field == "fec" and d.code == "capability_unsupported" for d in result.diagnostics)


def test_model_only_support_is_unknown(synthetic_registry, instance, inventory):
    synthetic_registry.capability = Capability(({"match": {"model": "PTX10008"}, "features": {"fec": "supported"}},))
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert any(d.field == "fec" and d.code == "capability_unknown" for d in result.diagnostics)


@pytest.mark.parametrize("kind", ["interface", "address", "alarm", "id"])
def test_conflicts_block_every_owner(synthetic_registry, instance, inventory, kind):
    other = copy.deepcopy(instance)
    other.instance_id = "IF-002"
    if kind != "interface":
        other.overrides["local_interface"] = "test-2"
    if kind != "address":
        other.overrides["ipv4_address"] = "192.0.2.5/30"
    if kind == "alarm":
        instance.overrides.update(rmon_enabled=True, ifindex=1)
        other.overrides.update(rmon_enabled=True, ifindex=1)
    if kind == "id":
        other.instance_id = instance.instance_id
    result = ConfigEngine(synthetic_registry).generate([instance, other], inventory)
    assert f"duplicate_{kind}" in codes(result)
    assert not result.valid_instance_ids


def test_independent_valid_row_survives(synthetic_registry, instance, inventory):
    bad = copy.deepcopy(instance)
    bad.instance_id = "BAD"
    bad.overrides.update(local_interface="test-3", ipv4_address="bad")
    result = ConfigEngine(synthetic_registry).generate([instance, bad], inventory)
    assert result.valid_instance_ids == ["IF-001"]
    assert "BAD" not in result.outputs["task.annotated"]


def test_mapping_exact_lines(synthetic_registry, instance, inventory):
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert result.outputs["task.clean"] == "set TEST_ONLY test-0 mtu 4484\n"
    assert "//" not in result.outputs["task.clean"]
    for section in result.sections:
        lines = result.outputs[section.output_kind].splitlines()
        assert tuple(lines[section.start_line - 1:section.end_line]) == section.commands


def test_router_dedup_keeps_both_owners(instance):
    from app.domain import GenerationResult
    second = replace(instance, instance_id="IF-002")
    result = GenerationResult()
    commands = ("set TEST_ONLY shared value",)
    ConfigEngine.build_outputs([(instance, commands), (second, commands)], result)
    kind = "router:10.0.0.1.clean"
    assert result.outputs[kind] == commands[0] + "\n"
    sections = [s for s in result.sections if s.output_kind == kind]
    assert {s.instance_id for s in sections} == {"IF-001", "IF-002"}
    assert all(s.start_line == 1 for s in sections)


def test_inactive_feature_details_do_not_reach_renderer(synthetic_registry, instance, inventory):
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert "isis_metric" in result.resolved[instance.instance_id].values
    assert not any(change.property == "isis_metric" for change in result.changes)


def test_locked_feature_replaces_system_default(synthetic_registry, instance, inventory):
    profile = synthetic_registry.profiles["hub-gate"]
    synthetic_registry.profiles["hub-gate"] = replace(profile, locked={"mpls_enabled": True})
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert not result.diagnostics
    assert result.resolved[instance.instance_id].values["mpls_enabled"] is True
    assert result.resolved[instance.instance_id].sources["mpls_enabled"] == "profile.locked"
