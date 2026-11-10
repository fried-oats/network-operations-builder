"""Lower only the Junos constructs supplied in the GL-PO239 Golden example."""
from app.domain import ConfigChange

OS_VERSION = "23.4R2-S1.6-EVO"


def passive_active(values):
    return values.get("isis_enabled") is True and values.get("isis_passive") is True


def is_golden_scope(record, values):
    return (record is not None and record.manufacturer == "Juniper" and record.model == "PTX10008"
            and values.get("os_family") == "Junos" and values.get("os_version") == OS_VERSION
            and values.get("interface_type") == "et")


def resolve_rules(values, sources, profile):
    if passive_active(values):
        for key, value in profile.rules.get("isis_passive_overrides", {}).items():
            values[key], sources[key] = value, "rule:isis_passive"
    if values.get("mpls_enabled") and sources.get("ldp_enabled") == "system":
        values["ldp_enabled"], sources["ldp_enabled"] = True, "rule:family_mpls"
    if values.get("rmon_enabled") and isinstance(values.get("ifindex"), int):
        for key, base in profile.rules.get("rmon_alarm_bases", {}).items():
            values[key], sources[key] = base + values["ifindex"], "rule:rmon_alarm_base"


def resolve_description(values, sources, record):
    required = ("local_interface", "peer_name", "peer_interface", "speed", "circuit_id")
    if record and all(values.get(key) for key in required):
        # Reuse the input string safety rules before embedding the Inventory display name in CLI.
        from .core import parse
        local_router = parse(record.name, {"type": "string"})
        values["description"] = (f"## {local_router}({values['local_interface']})-"
            f"{values['peer_name']}({values['peer_interface']})`{values['speed']}`"
            f"{values['circuit_id']}`{values.get('etc', '')}`##")
        sources["description"] = "rule:link_description"


def lower(instance, p, profile):
    changes = []
    interface = p["local_interface"]
    physical = f"interfaces {interface}"
    unit = f"{physical} unit 0"
    logical = f"{interface}.0"

    def add(group, target, prop, value=None, quoted=False):
        changes.append(ConfigChange(instance.target_management_ip, target, prop, value,
                                    instance.instance_id, group=group, quoted=quoted))

    add("interface", physical, "description", p["description"], True)
    if p.get("speed"):
        add("interface", physical, "speed", p["speed"])
    add("interface", physical, "mtu", p["mtu"])
    # Current policy is link-wide; archived Golden profiles retain their historical passive-only policy.
    flow_modes = profile.rules.get("no_flow_control_link_modes")
    no_flow_control = p.get("link_mode") in flow_modes if flow_modes is not None else passive_active(p)
    if no_flow_control:
        add("interface", physical + " ether-options", "no-flow-control")
    add("interface", physical + " ether-options", "fec", p["fec"])
    for direction in ("input", "output"):
        if p.get(f"ipv4_filter_{direction}"):
            add("interface", unit + " family inet", "filter " + direction, p[f"ipv4_filter_{direction}"])
    if p.get("ipv4_address"):
        add("interface", unit + " family inet", "address", p["ipv4_address"])
    if p.get("isis_enabled") and not passive_active(p):
        add("interface", unit + " family", "iso")
    for direction in ("input", "output"):
        if p.get(f"ipv6_filter_{direction}"):
            add("interface", unit + " family inet6", "filter " + direction, p[f"ipv6_filter_{direction}"])
    if p.get("ipv6_address"):
        add("interface", unit + " family inet6", "address", p["ipv6_address"])
    if p.get("mpls_enabled"):
        add("interface", unit + " family", "mpls")
    if p.get("isis_enabled"):
        target = f"protocols isis interface {logical}"
        if p.get("ldp_enabled") and not passive_active(p):
            add("isis", target, "ldp-synchronization")
        level = target + f" level {p['isis_level']}"
        add("isis", level, "metric", p["isis_metric"])
        if p.get("ipv6_address"):
            add("isis", level, "ipv6-unicast-metric", p["isis_metric"])
        if passive_active(p):
            add("isis", level, "passive")
        else:
            add("isis", level, "hello-interval", p["isis_hello_interval"])
            add("isis", level, "hold-time", p["isis_hold_time"])
            add("isis", target, "point-to-point")
    if p.get("ldp_enabled"):
        add("ldp", "protocols ldp", "interface", logical)
    if p.get("mpls_enabled"):
        add("mpls", "protocols mpls", "interface", logical)
    if p.get("rmon_enabled"):
        tag = interface.replace("-", "_").replace("/", "_")
        for kind, oid, suffix, group_name in (
            ("qdrop", "jnxCosQstatTotalDropPkts", ".0", "QDrop-Rmon"),
            ("crc", "ifJnxInFrameErrors", "", "CRC-Rmon"),
        ):
            target = f"snmp rmon alarm {p[kind + '_alarm_id']}"
            group = "rmon" if passive_active(p) else kind
            add(group, target, "apply-groups", group_name)
            add(group, target, "description", interface)
            add(group, target, "variable", f"{oid}.{p['ifindex']}{suffix}")
            add(group, target, "syslog-subtag", f"{kind.upper()}_{tag}")
    if p.get("cos_enabled"):
        changes.extend(lower_cos(instance, p, profile))
    return changes


def lower_cos(instance, p, profile):
    """Also models the supplied ae0 external CoS fragment, without approving ae base config."""
    target = f"class-of-service interfaces {p['local_interface']} unit 0"
    changes = []
    # Archived Golden definitions retain their original field; the current schema accepts link_mode only.
    mode = p["link_mode"] if "link_mode" in p else p["cos_mode"]
    if mode == "backbone":
        entries = [(f"rewrite-rules {family}", name + (f" protocol {protocol}" if protocol else ""))
                   for family, name, protocol in profile.rules["backbone_rewrites"]]
    else:
        entries = [(f"classifiers {family}", name) for family, name in profile.rules["external_classifiers"]]
    for prop, value in entries:
        changes.append(ConfigChange(instance.target_management_ip, target, prop, value, instance.instance_id, group="cos"))
    return changes
