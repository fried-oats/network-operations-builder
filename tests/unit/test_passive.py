from dataclasses import replace
from pathlib import Path
import copy
import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from app.domain import Capability, TaskInstance
from app.engine.core import ConfigEngine
from app.engine import junos


def test_user_passive_cli_reference(registry):
    """Preserve the original supplied CLI independently of the confirmed automatic-description variant."""
    instance = TaskInstance("PASSIVE-REF", target_management_ip="192.0.2.239")
    values = {
        "local_interface": "et-3/0/32",
        "description": "## LA-POP239(et-3/0/32)-[Uplink]T-Mobile_Sprint(AS1239)`100G`08882137-1239`` ##",
        "mtu": 4484, "fec": "none", "ipv4_address": "144.223.171.102/30",
        "ipv6_address": "2600:0001:0600:0010::000b/127",
        "ipv4_filter_input": "Filter-DDOS-Protect-IN", "ipv4_filter_output": "Filter-ISP-OUT",
        "ipv6_filter_input": "Filter-DDOS-Protect-IN_v6",
        "isis_enabled": True, "isis_passive": True, "isis_level": 2, "isis_metric": 1000,
        "isis_hello_interval": 10, "isis_hold_time": 30, "mpls_enabled": True, "ldp_enabled": True,
        "rmon_enabled": True, "ifindex": 761, "cos_enabled": True, "link_mode": "external",
    }
    profile = registry.profiles["hub-gate"]
    sources = {key: "override" for key in values}
    junos.resolve_rules(values, sources, profile)
    changes = junos.lower(instance, values, profile)
    env = Environment(loader=FileSystemLoader(registry.root / "templates"), undefined=StrictUndefined, autoescape=False)
    actual = env.get_template("juniper/interface.create.j2").render(changes=changes).strip() + "\n"
    expected = (Path(__file__).parents[1] / "golden/passive_reference/reference.set").read_text(encoding="utf-8")
    assert actual == expected
    assert values["isis_metric"] == 0
    assert values["mpls_enabled"] is False and values["ldp_enabled"] is False
    assert all(sources[key] == "rule:isis_passive" for key in ("isis_metric", "mpls_enabled", "ldp_enabled"))


@pytest.mark.parametrize("common,overrides", [
    ({}, {"isis_metric": 500, "mpls_enabled": True, "ldp_enabled": True}),
    ({"isis_metric": 150, "mpls_enabled": "enable", "ldp_enabled": "enable"}, {}),
    ({}, {"isis_metric": 0, "mpls_enabled": False, "ldp_enabled": False}),
])
def test_passive_policy_is_shared_by_engine(synthetic_registry, instance, inventory, common, overrides):
    instance.overrides.update(isis_enabled=True, isis_passive=True, **overrides)
    result = ConfigEngine(synthetic_registry).generate([instance], inventory, common)
    assert not result.diagnostics
    p = result.resolved[instance.instance_id]
    assert p.values["isis_metric"] == 0
    assert p.values["mpls_enabled"] is False
    assert p.values["ldp_enabled"] is False
    assert instance.overrides.get("isis_metric") == overrides.get("isis_metric")


def test_passive_does_not_force_cos_policy(synthetic_registry, instance, inventory):
    instance.overrides.update(isis_enabled=True, isis_passive=True, cos_enabled=False)
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert not result.diagnostics
    assert result.resolved[instance.instance_id].values["cos_enabled"] is False


def test_passive_profile_lock_conflict_blocks(synthetic_registry, instance, inventory):
    profile = synthetic_registry.profiles["hub-gate"]
    synthetic_registry.profiles["hub-gate"] = replace(profile, locked={"mpls_enabled": True})
    instance.overrides.update(isis_enabled=True, isis_passive=True)
    result = ConfigEngine(synthetic_registry).generate([instance], inventory)
    assert any(d.code == "profile_rule_conflict" for d in result.diagnostics)
    assert not result.valid_instance_ids


def test_passive_keeps_scope_gate_for_other_os(registry, instance, inventory):
    instance.overrides.update(os_version="unverified-os", interface_type="et", local_interface="et-3/0/32", isis_enabled=True, isis_passive=True)
    result = ConfigEngine(registry).generate([instance], inventory)
    assert any(d.field == "isis_passive" and d.code == "capability_unknown" for d in result.diagnostics)
    assert not result.valid_instance_ids
