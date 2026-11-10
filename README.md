# Network Operations Builder — MVP v0.1 Preview

Windows용 PySide6 Qt Widgets 프로그램. 장비 접속/명령 실행 기능은 없습니다.

라우터 Inventory는 FastAPI에서만 불러옵니다. CSV Inventory 기능은 제거했습니다. API는 **파일 → API Inventory 불러오기**를
사용하며, 서버는 `config/.env`의 `API_BASE_URL`로 설정합니다. 배포본은 `config/.env.example`을 복사해 설정하세요.
인증이 필요하면 조회 창에서 ID/비밀번호를 입력합니다. 상세 계약/설정: [API Inventory 안내](docs/API_INVENTORY.md).
API 조회 후 Config 생성은 기존 로컬 엔진을 사용합니다. Bulk 작업 입력용 XLSX/CSV는 계속 지원합니다.

새 프로젝트(Ctrl+N)를 만들면 프로젝트 이름을 입력합니다. 파일 → 프로젝트 이름 변경으로
나중에 수정할 수 있으며, 이름은 창 제목/프로젝트 정보에 표시되고 .nobproj에 저장됩니다.
이름 변경은 Config Preview와 입력값을 유지합니다. 이 GUI 변경의 정의 버전은 기존 1.4.1과 같습니다.

사용자 Golden 범위의 CLI 생성이 연결되었습니다: **PTX10008 / 23.4R2-S1.6-EVO / et, unit 0**.
IS-IS P2P/passive를 지원합니다. 미확인 OS/인터페이스 유형과 speed/MTU/FEC 값은 차단됩니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
.\.venv\Scripts\python -m pytest -q --basetemp=.pytest_tmp
.\.venv\Scripts\python -m app.main
```

`examples/ptx10008_golden.nobproj`와 `examples/ptx10008_passive.nobproj`는 입력 형식 참고 예제입니다.
프로젝트를 연 뒤 API Inventory를 불러오고, 테스트용 target_management_ip를 실제 API 장비로 변경하세요.
Bulk 예제 `examples/passive_bulk.csv`도 실제 API 장비의 관리 IP로 수정한 뒤 가져옵니다.
예제의 192.0.2.239/240은 실제 관리 IP가 아닙니다. 자동 로드할 Inventory CSV는 제공하지 않습니다.

API의 os_version과 Juniper→Junos 매핑으로 라우터 선택 시 OS가 자동 표시됩니다.
os_version이 비어 있으면 수동 입력으로 보완할 수 있습니다. platform 입력은 Inventory Model을 사용합니다.

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
MPLS/LDP 및 LDP sync를 생성하지 않습니다. level 2 passive를 생성하며
P2P/hello/hold 명령은 생략합니다. 관련 입력은 비활성화되고 passive 해제 시 이전 값이 복원됩니다.
Link 그룹의 link_mode에서 backbone/external을 선택합니다. 기본값은 backbone이며 CoS 비활성 시에도 선택할 수 있습니다.
CoS는 cos_enabled로 출력 여부를 선택하고, link_mode에 따라 기존 rewrite rules/classifiers를 생성합니다.
link_mode 선택만으로 IS-IS passive/MPLS 등의 다른 입력을 자동 변경하지 않습니다.
MPLS On은 LDP가 상속 상태일 때 LDP도 자동 활성화합니다. 명시적 LDP Off는 유지합니다.
RMON On + ifIndex는 QDrop=8000+ifIndex, CRC=9000+ifIndex를 자동 계산합니다.
Alarm ID 입력은 제거했고, 자동 계산 값의 장비 내 중복을 검사합니다.
Rx Optics +7000 정책은 추후 추가합니다. 생성 후 Single 필드 Tooltip에 적용값/출처를 표시합니다.
CoS backbone은 rewrite rules, external은 제공된 IN_ISP_IPv6/IPv4 classifiers 두 줄만 생성합니다.
ae 전체 Interface 생성은 여전히 추가 Golden이 필요합니다.

빈칸은 `행 > 공통값 > Profile > System` 상속, Off/CSV `disable`은 명시적 false입니다.
Bulk 탭에서 XLSX/CSV 양식을 생성하고 가져와 셀을 수정할 수 있습니다.
Bulk CSV 헤더는 대소문자를 구분합니다. Inventory CSV 가져오기와는 다른 기능입니다.
가져오기는 Task 목록을 교체합니다. XLSX는 공통값도 교체하며 CSV는 GUI 공통값을 유지합니다.
입력 Placeholder는 default: 값으로 표시합니다.
Task/Schema/Profile/Template 버전은 **1.4.1**입니다. 이전 버전 양식/프로젝트는 자동 마이그레이션하지 않습니다.
버전 누락/불일치 Bulk는 전체 거부하며 기존 데이터를 보존합니다.
프로젝트는 원자적으로 .nobproj에 저장하고 Inventory 출처는 API 참조로 기록합니다.
기존 CSV 참조 프로젝트는 파일을 읽지 않고 API 참조로 전환하며 Task/공통값을 유지합니다.
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

기존 cos_mode 입력은 link_mode로 변경되었습니다. 이전 프로젝트/양식은 지원 버전과 일치하지 않으면 거부합니다.

link_mode=external이면 IS-IS/CoS 활성 여부와 무관하게 ether-options no-flow-control을 FEC 앞에 생성합니다.
backbone은 FEC만 생성합니다. no-flow-control은 passive 조건에서 분리되었습니다.
