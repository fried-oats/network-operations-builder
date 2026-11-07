import csv
from dataclasses import asdict
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from app.domain import TaskInstance

MAX_ROWS = 10000
MAX_BYTES = 20 * 1024 * 1024


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


class BulkIO:
    def __init__(self, registry):
        self.registry = registry
        self.contract = registry.contract()
        self.fields = {key: spec for key, spec in registry.schemas["interface.create"].fields.items() if not spec.get("derived")}
        self.columns = ["instance_id", "target_management_ip", *self.fields]

    def export_template(self, path):
        path = Path(path)
        if path.suffix.lower() == ".csv":
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[*self.contract, *self.columns])
                writer.writeheader()
                # Metadata-only row makes even a blank template version-verifiable.
                writer.writerow(self.contract)
            guide = path.with_suffix(".field-guide.txt")
            guide.write_text("빈 셀: 상속, disable: 명시적 비활성. 공통값은 GUI에서 입력.\n" + "\n".join(f"{k}: {v}" for k, v in self.fields.items()), encoding="utf-8")
        elif path.suffix.lower() == ".xlsx":
            wb = Workbook()
            ws = wb.active
            ws.title = "Parameters"
            ws.append(self.columns)
            ws.freeze_panes = "C2"
            for index, (key, spec) in enumerate(self.fields.items(), 3):
                choices = ["enable", "disable"] if spec["type"] == "bool" else spec.get("choices")
                if choices:
                    validation = DataValidation(type="list", formula1='"' + ",".join(map(str, choices)) + '"', allow_blank=True)
                    ws.add_data_validation(validation)
                    from openpyxl.utils import get_column_letter
                    validation.add(f"{get_column_letter(index)}2:{get_column_letter(index)}{MAX_ROWS + 1}")
            common = wb.create_sheet("Common Defaults")
            common.append(["field", "value"])
            for key in self.fields:
                common.append([key, None])
            guide = wb.create_sheet("Field Guide")
            guide.append(["field", "type", "required", "condition", "default"])
            profile = self.registry.profiles["hub-gate"]
            for key, spec in self.fields.items():
                guide.append([key, spec["type"], spec.get("required", False), spec.get("required_when", ""), profile.defaults.get(key)])
            meta = wb.create_sheet("Metadata")
            for key, value in self.contract.items():
                meta.append([key, value])
            wb.save(path)
        else:
            raise ValueError("CSV/XLSX 확장자가 필요합니다")

    def check_contract(self, metadata):
        if metadata != self.contract:
            raise ValueError(f"Bulk 버전 불일치: 지원={self.contract}, 파일={metadata}. 최신 양식을 생성하세요.")

    def load(self, path):
        path = Path(path)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Bulk 파일 크기 제한 초과")
        common = {}
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or set(reader.fieldnames) != set([*self.contract, *self.columns]):
                    raise ValueError("Bulk 필수/버전 컬럼 누락 또는 알 수 없는/중복 컬럼")
                rows = []
                for number, row in enumerate(reader, 2):
                    if number > MAX_ROWS + 2:
                        raise ValueError("Bulk 행 수 제한 초과")
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError(f"{number}행: 컬럼 수 오류")
                    self.check_contract({k: row[k] for k in self.contract})
                    if any(row[k] for k in self.columns):
                        rows.append({k: row[k] for k in self.columns})
                if not rows and number_if_any(reader) is None:
                    # A header-only CSV has no verifiable metadata.
                    raise ValueError("Bulk 버전 메타데이터 행이 없습니다")
        elif path.suffix.lower() == ".xlsx":
            # Bound expanded ZIP size before XML parsing.
            from zipfile import ZipFile
            with ZipFile(path) as archive:
                if sum(x.file_size for x in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("XLSX 압축 해제 크기 제한 초과")
            wb = load_workbook(path, read_only=True, data_only=False)
            try:
                if not {"Parameters", "Common Defaults", "Field Guide", "Metadata"} <= set(wb.sheetnames):
                    raise ValueError("필수 시트 누락")
                metadata_rows = list(wb["Metadata"].iter_rows(values_only=True))
                if len(metadata_rows) != len(self.contract) or any(len(r) != 2 for r in metadata_rows):
                    raise ValueError("잘못된 Metadata 시트")
                self.check_contract(dict(metadata_rows))
                ws = wb["Parameters"]
                if ws.max_row > MAX_ROWS + 1 or ws.max_column != len(self.columns):
                    raise ValueError("Bulk 행/컬럼 제한 초과")
                iterator = ws.iter_rows()
                if [c.value for c in next(iterator)] != self.columns:
                    raise ValueError("Parameters 컬럼 불일치")
                rows = []
                for row_number, row in enumerate(iterator, 2):
                    if any(c.data_type == "f" for c in row):
                        raise ValueError(f"{row_number}행: 수식 파라미터 금지")
                    if any(c.value is not None for c in row):
                        rows.append(dict(zip(self.columns, (c.value for c in row))))
                cs = wb["Common Defaults"]
                if cs.max_row > len(self.fields) + 1 or cs.max_column != 2:
                    raise ValueError("Common Defaults 구조 오류")
                if list(next(cs.iter_rows(values_only=True))) != ["field", "value"]:
                    raise ValueError("Common Defaults 컬럼 오류")
                for key, cell in cs.iter_rows(min_row=2):
                    if key.value not in self.fields or key.value in common or cell.data_type == "f":
                        raise ValueError("공통값 필드/수식 오류")
                    if cell.value is not None:
                        common[key.value] = cell.value
            finally:
                wb.close()
        else:
            raise ValueError("CSV/XLSX 파일만 지원합니다")
        instances = []
        for row in rows:
            instances.append(TaskInstance(str(row.get("instance_id") or ""), target_management_ip=str(row.get("target_management_ip") or ""),
                                          overrides={k: row[k] for k in self.fields if row.get(k) is not None}))
        return instances, common


def number_if_any(reader):
    return reader.line_num if reader.line_num > 1 else None


def export_report(path, diagnostics):
    headers = ["row", "instance_id", "field", "code", "message", "value", "remedy"]
    rows = [[safe_cell(asdict(d).get(k)) for k in headers] for d in diagnostics]
    if Path(path).suffix.lower() == ".xlsx":
        wb = Workbook()
        wb.active.append(headers)
        for row in rows:
            wb.active.append(row)
        wb.save(path)
    else:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
