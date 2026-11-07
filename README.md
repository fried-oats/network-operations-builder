# Network Operations Builder — MVP v0.1 Preview

Windows용 오프라인 PySide6 Qt Widgets 프로그램. 장비 접속/명령 실행 기능은 없습니다.

새 프로젝트(Ctrl+N)를 만들면 프로젝트 이름을 입력합니다. 파일 → 프로젝트 이름 변경으로
나중에 수정할 수 있으며, 이름은 창 제목/프로젝트 정보에 표시되고 .nobproj에 저장됩니다.
이름 변경은 Config Preview와 입력값을 유지합니다. 이 GUI 변경의 정의 버전은 기존 1.3.0과 같습니다.

사용자 Golden 범위의 CLI 생성이 연결되었습니다: **PTX10008 / 23.4R2-S1.6-EVO / et, unit 0**.
IS-IS P2P/passive를 지원합니다. 미확인 OS/인터페이스 유형과 speed/MTU/FEC 값은 차단됩니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
.\.venv\Scripts\python -m pytest -q --basetemp=.pytest_tmp
.\.venv\Scripts\python -m app.main
```

앱에서 `examples/ptx10008_golden.nobproj`를 열고 검증/생성을 누르면 제공된 사례를 재현합니다.
Passive 예제는 `examples/ptx10008_passive.nobproj`입니다. 같은 폴더의 Inventory를 사용하며,
Bulk는 Inventory 로드 후 `examples/passive_bulk.csv`로 시험할 수 있습니다.
예제 관리 IP 192.0.2.239/240은 테스트용 키입니다. 실제 작업에는 본인의 Inventory를 사용하세요.

Inventory는 기존 8개 컬럼에 선택 컬럼 `os_version`을 추가합니다. Juniper는 os_family=Junos로 자동 매핑하며,
라우터 선택 시 OS 정보가 자동 표시됩니다. 값이 없는 구형 CSV는 수동 입력이 가능합니다.
platform 입력은 Inventory Model과 중복되어 제거했습니다.

Description은 Inventory Name과 Link 입력으로 자동 생성합니다. 수동 입력은 제거했습니다.
다음 형식을 사용합니다.

```text
## {local_router}({local_interface})-{peer_name}({peer_interface})`{speed}`{circuit_id}`{etc}`##
```

 speed는 입력값 그대로 사용하며 100g 명령도 생성합니다.
circuit_id는 00000000-0000 또는 0000-0000-0000 형식으로 입력합니다. 없으면 Direct(기본값)를 사용합니다.
etc는 선택 입력입니다. isis_metric 기본값은 1000입니다.
peer_name의 Netflix(AS2906), [Uplink]T-Mobile_Sprint(AS1239) 같은 이름은 그대로 보존합니다.
peer_interface는 기존 규칙대로 별도 괄호에 붙으며, 사업자명 내부의 AS 괄호도 유지합니다.
Passive에서도 기존 Description 및 speed 명령 생성은 유지합니다.

IS-IS Enabled + Passive를 켜면 IPv4/IPv6 metric을 0으로 고정하고 family iso/mpls,
MPLS/LDP 및 LDP sync를 생성하지 않습니다. ether-options no-flow-control과 level 2 passive를 생성하며
P2P/hello/hold 명령은 생략합니다. 관련 입력은 비활성화되고 passive 해제 시 이전 값이 복원됩니다.
CoS mode는 별도 선택으로 유지합니다.
MPLS On은 LDP가 상속 상태일 때 LDP도 자동 활성화합니다. 명시적 LDP Off는 유지합니다.
RMON On + ifIndex는 QDrop=8000+ifIndex, CRC=9000+ifIndex를 자동 계산합니다.
Alarm ID 입력은 제거했고, 자동 계산 값의 장비 내 중복을 검사합니다.
Rx Optics +7000 정책은 추후 추가합니다. 생성 후 Single 필드 Tooltip에 적용값/출처를 표시합니다.
CoS backbone은 rewrite rules, external은 제공된 IN_ISP_IPv6/IPv4 classifiers 두 줄만 생성합니다.
ae 전체 Interface 생성은 여전히 추가 Golden이 필요합니다.

빈칸은 `행 > 공통값 > Profile > System` 상속, Off/CSV `disable`은 명시적 false입니다.
Bulk 탭에서 XLSX/CSV 양식을 생성하고 가져와 셀을 수정할 수 있습니다.
CSV 헤더는 대소문자를 구분하고 Inventory 헤더의 앞뒤 공백은 제거합니다.
가져오기는 Task 목록을 교체합니다. XLSX는 공통값도 교체하며 CSV는 GUI 공통값을 유지합니다.
입력 Placeholder는 default: 값으로 표시합니다.
Task/Schema/Profile/Template 버전은 **1.3.0**입니다. 이전 버전 양식/프로젝트는 자동 마이그레이션하지 않습니다.
버전 누락/불일치 Bulk는 전체 거부하며 기존 데이터를 보존합니다.
프로젝트는 원자적으로 .nobproj에 저장하고 Inventory 상대경로를 사용합니다.
창/패널/최근 경로는 QSettings에 저장합니다. 오류 Instance는 출력에서 제외합니다.

구조/단계: [구현 계획](docs/IMPLEMENTATION_PLAN.md).
완료/후속 항목: [구현 상태](docs/STATUS.md).
Golden 출처: [Golden 안내](tests/golden/README.md).

```powershell
.\packaging\build.ps1
```

출력: `dist/NetworkOperationsBuilder-v0.1-preview-win64.zip`.
압축 해제 후 내부 NetworkOperationsBuilder.exe를 실행합니다.
pytest와 onedir EXE 시작 점검 후 ZIP을 생성하며 예제/의존성/라이선스 자료를 포함합니다.
별도 오프라인 Windows PC 수용 테스트와 사내 보안/라이선스 검토는 아직 완료하지 않았습니다.
