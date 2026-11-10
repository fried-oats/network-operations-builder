from ipaddress import ip_address
from app.domain import InventoryRecord

MANUFACTURER_ALIASES = {"juniper": "Juniper", "juniper networks": "Juniper"}
MODEL_ALIASES = {"t4000": "T4000", "ptx10008": "PTX10008"}


def inventory_record(management_ip, name, hierarchy, group, location, operation_team, manufacturer, model, os_version=""):
    fields = [management_ip, name, hierarchy, group, location, operation_team, manufacturer, model, os_version]
    if any(not isinstance(value, str) for value in fields):
        raise ValueError("Inventory 필드는 문자열이어야 합니다")
    fields = [value.strip() for value in fields]
    fields[0] = str(ip_address(fields[0]))
    if not fields[1]:
        raise ValueError("Inventory Name은 필수입니다")
    fields[6] = MANUFACTURER_ALIASES.get(fields[6].casefold(), fields[6])
    fields[7] = MODEL_ALIASES.get(fields[7].casefold(), fields[7])
    family = {"Juniper": "Junos"}.get(fields[6], "")
    return InventoryRecord(*fields[:8], os_family=family, os_version=fields[8])
