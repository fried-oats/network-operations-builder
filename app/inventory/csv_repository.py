import csv
from ipaddress import ip_address
from pathlib import Path
from typing import Protocol
from app.domain import InventoryRecord


class InventoryRepository(Protocol):
    def load(self, path: Path) -> dict[str, InventoryRecord]: ...


class CsvInventoryRepository:
    """Headers are case sensitive; surrounding whitespace is stripped."""
    headers = ["IP Address", "Name", "Hierarchy", "Group", "Location", "Operation Team", "Manufacturer", "Model"]
    aliases = {"juniper": "Juniper", "juniper networks": "Juniper"}
    models = {"t4000": "T4000", "ptx10008": "PTX10008"}

    def load(self, path):
        records = {}
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = [x.strip() for x in reader.fieldnames or []]
            if len(headers) != len(set(headers)) or not set(self.headers) <= set(headers):
                raise ValueError("Inventory 필수 헤더가 없거나 중복됩니다")
            reader.fieldnames = headers
            for rownum, row in enumerate(reader, 2):
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"Inventory {rownum}행: 컬럼 수 오류")
                values = [row[h].strip() for h in self.headers]
                try:
                    values[0] = str(ip_address(values[0]))
                except ValueError as exc:
                    raise ValueError(f"Inventory {rownum}행: 잘못된 관리 IP") from exc
                if values[0] in records:
                    raise ValueError(f"Inventory {rownum}행: 중복 management_ip {values[0]}")
                if not values[1]:
                    raise ValueError(f"Inventory {rownum}행: Name 필수")
                values[6] = self.aliases.get(values[6].casefold(), values[6])
                values[7] = self.models.get(values[7].casefold(), values[7])
                version = row.get("os_version", "").strip()
                # Explicit vendor mapping; unknown vendors never acquire an assumed OS.
                family = {"Juniper": "Junos"}.get(values[6], "")
                records[values[0]] = InventoryRecord(*values, os_family=family, os_version=version)
        return records
