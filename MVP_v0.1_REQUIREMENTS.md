# Network Operations Builder — MVP v0.1 요구사항 명세서

> 상태: 구현 기준 초안 / 작성일: 2026-11-04  
> 대상: Codex 및 개발자 / 언어: Python 3 / 플랫폼: Windows Desktop

## 1. 목적 및 최상위 원칙

Network Operations Builder(NOB)는 통신망 운영자가 사전에 정의된 운영 정책에 따라 라우터 설정 명령어를 **생성·검토·내보내기** 하는 오프라인 데스크톱 애플리케이션이다. MVP v0.1은 Juniper Junos의 `Interface 연동 생성` Task 1종에 집중하며, 단일 입력과 Excel/CSV 다중 입력이 **동일한 Config Engine**을 호출한다.

1. 프로그램은 장비 접속·명령 실행·설정 적용을 **수행하지 않는다**.
2. 사용자의 네트워크 영향도 평가 및 작업 성공 여부 판단을 대신하지 않는다.
3. Profile(운영 정책), Schema(입력 정의), Template(제조사별 출력), Capability(지원 조건), Task Definition(작업 정의), Task Instance(입력값을 가진 개별 작업)를 분리한다.
4. GUI, Bulk 입력, 향후 Workflow는 동일한 Task Engine을 호출한다.
5. **장비 고유 식별자는 `management_ip`이다.** Inventory CSV의 `IP Address`는 관리/접속에 사용하는 고유 Loopback IP이므로 `management_ip`로 변환한다. 별도의 `device_id` 필드는 만들지 않는다.
6. 미지원·미확인 설정은 조용히 생략하거나 추측하지 않는다. Capability Validator에서 명시적인 오류로 처리한다. 단, 사용자가 명시적으로 선택하지 않았고 정책상 필요하지 않은 기능은 출력하지 않는다.
7. 실제 붙여넣기용 `Clean Config`와 출처 주석이 포함된 `Annotated Config`를 분리한다.
8. 기본 배포물은 **Standalone 폴더 → ZIP**이며 인터넷/서버/데이터베이스 연결 없이 실행한다.

## 2. MVP 범위

### 2.1 필수 포함 (Must)

| ID | 기능 | 요구사항 및 완료 조건 |
|---|---|---|
| FR-001 | 오프라인 데스크톱 | PySide6 Qt Widgets, Windows 실행, 외부 서버 불필요 |
| FR-002 | 3단 메인 화면 | 좌측 Task·Instance / 가운데 입력·Bulk / 우측 Config Preview, 너비 드래그 가능 |
| FR-003 | CSV Inventory | `IP Address,Name,Hierarchy,Group,Location,Operation Team,Manufacturer,Model` 로드; IP Address → management_ip |
| FR-004 | 장비 선택 | 이름·관리 IP 검색, 제조사/모델/계위 표시, 데이터 중복·오류 검사 |
| FR-005 | Task Registry | `interface.create` 정의를 YAML로 읽고 Single/Bulk가 공유 |
| FR-006 | Profile/Schema/Capability/Template | 외부 파일로 정의; GUI 입력과 백엔드 검증은 동일한 Schema 의미론 활용 |
| FR-007 | Single Task | 장비·Profile·Interface·주소·기능 입력 후 Config 생성 |
| FR-008 | Optional Features | ISO/IS-IS, MPLS/LDP, RMON, CoS 및 IPv4/IPv6 필터의 조건부 입력 |
| FR-009 | Bulk XLSX/CSV | 현재 Schema 버전의 양식 생성, 파일 읽기, 행별 검증, GUI에서 오류 셀 수정 |
| FR-010 | 엄격한 버전 호환 | 지원 대상과 일치하지 않는/버전이 없는 Bulk 양식은 업로드 거부, 최신 양식 생성 안내 |
| FR-011 | 출력 | Task별, management_ip별 통합, Clean/Annotated 형식, TXT 저장·클립보드 복사 |
| FR-012 | 출처 탐색 | 좌측 Instance 클릭 → 해당 Config 섹션으로 이동/강조; 정형화된 매핑 사용 |
| FR-013 | 프로젝트 파일 | Single/Bulk Task Instance 및 공통값을 JSON 기반 `.nobproj`로 저장/다시 열기 |
| FR-014 | QSettings | 최근 프로젝트 목록, 윈도우 크기·위치, QSplitter 크기, 마지막 파일 경로 등 |
| FR-015 | 검증과 오류 보고 | 필드/행별/전체 데이터/Capability 검증; 오류 보고 CSV/XLSX 내보내기 |
| FR-016 | Golden Config | pytest fixture를 통한 정확 출력 회귀 테스트; 테스트 케이스 신규 추가 체계 |
| FR-017 | 배포 | Standalone 실행 폴더를 ZIP으로 패키징, 사내 보안/라이선스 검토 가능한 구조 |

### 2.2 명시적 제외 (Out of scope)

- Workflow 편집기 및 실행 상태 머신 (단, 향후 참조 가능한 Task Instance 모델은 설계)
- Cisco IOS XR, Nokia SR OS 실제 CLI Renderer
- BGP Task, Interface Delete/Shutdown 등 다른 Task 구현
- 장비 SSH/NETCONF/SNMP 연결, 장비 상태 자동 조회, 컨피그 자동 적용
- 자동 위험도 판단, 자동 실행 승인, AI Agent
- 중앙 서버, 웹 프런트엔드, MariaDB 실시간 연동, 다중 사용자 로그인
- 임의의 기존 장비 설정을 분석하여 안전한 병합을 보장하는 기능

## 3. 도메인 모델

### 3.1 객체와 책임

| 개념 | 정의 | MVP에서의 형태 |
|---|---|---|
| `TaskDefinition` | 수행 가능한 Task의 정적 정의 | `interface.create` YAML |
| `TaskInstance` | 정의 + 개별 파라미터 + 고유 Instance ID | 메모리/프로젝트 JSON |
| `Profile` | Task 유형별 기본값·고정 규칙 | `hub-gate` YAML |
| `Schema` | 타입, 입력 컨트롤, 필수 여부, 조건부 표시/검증 | YAML + Python/Pydantic 검증 |
| `Capability` | 제조사/OS/모델/인터페이스 조건별 지원·미지원·미확인 | 외부 YAML + Validator |
| `Template` | 출력 CLI 형식 | Junos Jinja2 (`*.j2`) |
| `InventoryRecord` | 장비 정보 | CSV에서 로드, `management_ip`가 PK |
| `GeneratedSection` | Instance의 CLI와 원본 매핑 | `instance_id`, `management_ip`, `commands`, `line_range` |
| `GenerationResult` | 결과/경고/오류/출처 묶음 | Python 객체; UI와 Export가 공유 |

### 3.2 Task Instance 예시

```json
{
  "instance_id": "IF-001",
  "task_id": "interface.create",
  "task_version": "1.0.0",
  "target_management_ip": "10.10.10.1",
  "profile_id": "hub-gate",
  "overrides": {
    "local_interface": "et-0/0/0",
    "peer_name": "Router-B",
    "peer_interface": "et-0/0/8",
    "ipv4_address": "192.168.0.1/30",
    "ipv6_address": "2400::100:192:168:0:1/126",
    "isis_enabled": true,
    "mpls_enabled": true
  }
}
```

`instance_id`는 작업 식별자이고 `management_ip`는 장비 식별자이다. 같은 장비에 여러 Instance가 연결될 수 있다. `management_ip`가 변경될 가능성이 생기면 향후 명시적 마이그레이션 정책을 도입한다.

### 3.3 파라미터 값 해석 및 우선순위

`TaskInstance override > Bulk/Workflow 공통값 > Profile 기본값 > 시스템 기본값`.

- GUI 빈 문자열(`""`), CSV/XLSX 빈 셀, 미입력은 **미지정/상속** 의미다.
- 미입력과 명시적 비활성화는 다르다. Boolean/Feature 비활성화는 `disable` (Bulk) 또는 GUI의 명시적 Off 선택으로 표현한다. 입력 경계에서 정규화하여 내부적으로 `false`/열거형 상태로 저장한다.
- 단순 빈 문자열을 장비 CLI 값으로 전달하지 않는다.
- 상속된 값이 실제 어떤 출처인지 UI/검증 로그에서 추적한다.
- Profile의 `locked` 값 및 제한 규칙을 개별 override로 무시할 수 없다.
- 적용 순서: 원시값 파싱 → 상속/정규화 → Schema 검사 → Profile 제약 → Capability 검사 → Rule/의존성 검사 → 의미적 충돌 검사 → Renderer.
- Bulk 공통값은 같은 컬럼에 행 값이 존재할 때 행 값으로 대체된다. `disable`은 명시적 값으로서 기본값을 상속하지 않는다.

## 4. Inventory 사양

- 필수 CSV 헤더: `IP Address`, `Name`, `Hierarchy`, `Group`, `Location`, `Operation Team`, `Manufacturer`, `Model` (대소문자/공백 처리 규칙은 파서에서 고정 및 문서화).
- `IP Address`는 `management_ip`로 변환; IPv4/IPv6 주소 형식을 검증하고 앞뒤 공백 제거.
- `management_ip` 중복은 **파일 로드 오류**. 동일 IP의 서로 다른 Router가 있을 수 있다고 가정하지 않는다.
- `Name`은 표시명이며 고유키가 아니다.
- `Manufacturer`를 Juniper/Juniper Networks 등 사전 정의 별칭에서 정규화한다. 알 수 없는 값은 자동 추정하지 않는다.
- `Model`도 표준화 테이블로 확인하며 Capability 정의와 매칭하지 못하면 해당 기능 지원 여부를 **unknown**으로 처리.
- CSV에는 OS/Version/Interface Type이 없으므로 필요시 GUI에서 추가 입력 또는 프로젝트 값으로 보완한다. 기본값을 근거 없이 부여하지 않는다.
- 초기에는 CSV 파일 경로를 프로젝트에 기록하거나 다시 로드할 수 있다. 외부 파일이 없을 경우 해당 오류를 안내하고 기존 입력값을 함부로 덮어쓰지 않는다.
- 추후 MariaDB를 Inventory Provider로 도입해도 상위 로직은 `InventoryRepository` 인터페이스를 통해 유지한다.

## 5. Interface Create — MVP 입력 필드

| 그룹 | 필드 | 타입/예시 | 기본/조건 |
|---|---|---|---|
| Target | `target_management_ip` | IP, Inventory 선택 | 필수 |
| Target | `os_family`, `os_version`, `platform` | Junos/버전/모델 | Capability 확인에 필요할 수 있음 |
| Link | `local_interface` | `et-0/0/0` | 필수 |
| Link | `peer_name`, `peer_interface` | `Router-B`, `et-0/0/8` | Description 생성에 필요 |
| IP | `ipv4_address` | `192.168.0.1/30` | 선택, 형식 검사 |
| IP | `ipv6_address` | `2400::100:192:168:0:1/126` | 선택, 형식 검사 |
| Physical | `speed` | `100g` | Profile 기본 100g, 지원 항목만 표시 |
| Physical | `mtu` | `4484` | Profile 기본 4484, 플랫폼 범위 확인 |
| Physical | `fec` | `none` / 기타 | Profile 기본 none; **미지원 모델에서는 생성 금지** |
| IPv4 Filter | `ipv4_filter_input/output` | 문자열 | 비어 있으면 미생성/상속 규칙 적용 |
| IPv6 Filter | `ipv6_filter_input/output` | 문자열 | 비어 있으면 미생성/상속 규칙 적용 |
| IS-IS | `isis_enabled`, `isis_passive` | On/Off | ISO family 연결, conditional |
| IS-IS | `isis_level`, `isis_metric` | 2, 120 | IPv6 unicast metric에도 동일 metric 사용 |
| MPLS | `mpls_enabled`, `ldp_enabled` | On/Off | LDP는 MPLS와 구분된 내부 필드로 유지 |
| RMON | `rmon_enabled`, `ifindex`, `crc_alarm_id`, `qdrop_alarm_id` | 525,9525,8525 | RMON 사용 시 필수, ID 충돌 검증 |
| CoS | `cos_enabled`, `scheduler_map`, `classifiers` | 표준 프로필 값 | CoS 사용 시 Template 출력 |

MVP는 사용자가 제공한 Junos CLI 예시를 초기 기대 출력으로 삼되, 모델별 지원/구문은 **Golden Config가 확보될 때 확정**한다. T4000 FEC 미지원, PTX10008 지원은 사용자 제공 운영 예시이며 Capability 샘플 데이터로 사용하되 실제 OS/인터페이스 유형 범위는 테스트로 확정한다.

### 5.1 의존성 규칙

- `isis_enabled=true` → ISO family, IS-IS 섹션을 생성. `isis_passive=false`이면 P2P 생성, `true`이면 passive 명령을 생성하고 P2P 생략 (대상 OS/정책 기준 검증).
- IS-IS metric은 L2 metric 및 IPv6 unicast metric에 동일 값 사용.
- MPLS/LDP는 별개의 의미를 가진다. `ldp_enabled=true`는 정책상 MPLS가 필요하며 둘의 조합이 해당 모델에서 지원되는지 검사한다.
- `isis + ldp` 및 non-passive 상태에서 정책상 필요하면 LDP synchronization 생성.
- RMON은 `ifindex`, Alarm ID 및 대상 변수에 대한 필수값 검사. Alarm ID는 같은 장비 전체에서 중복 금지.
- CoS/Filter 등은 활성화 여부 및 지원 능력에 따라 생성한다.
- 지원 여부가 `unsupported` 또는 `unknown`인 기능을 사용자가 명시 요청하면 **생성 차단**, 진단 정보 표시.

## 6. Bulk 입출력 계약

### 6.1 XLSX 양식

- 프로그램이 Task Definition + Schema + Profile을 기준으로 **현재 버전 양식**을 생성.
- 시트: `Parameters`(한 행=Task Instance), `Common Defaults`, `Field Guide`, `Metadata`.
- `Metadata`에 `task_id`, `schema_version`, `template_format_version`, `profile_id`, `profile_version`를 기록.
- `Parameters`는 `instance_id`, `target_management_ip` 및 Schema 입력 필드가 포함된다. 셀 데이터 유효성 검사/드롭다운은 UX 보조일 뿐 서버 측에 상응하는 Python 검증이 필수.
- 임의 수식 실행 금지; 수식이 있는 파라미터 셀은 값으로 해석하지 않고 오류 처리.

### 6.2 CSV 양식

- 단일 UTF-8 with BOM CSV로 제공해 Excel 호환성을 확보한다.
- 고정 필드 `schema_version`, `template_format_version`, `task_id`, `profile_id`, `profile_version`를 각 행에 포함. 모든 행에서 동일해야 한다.
- `Common Defaults`는 GUI에서 지정하거나 CSV의 명시적인 공통값 입력 기능으로 관리; CSV 헤더/의미는 별도 Field Guide에 명시.

### 6.3 업로드 검증

1. 파일 형식, 크기, 행 수, 필수 시트/컬럼 및 버전 검사.
2. 현재 프로그램이 허용하는 **정확한 버전 집합**과 불일치하면 업로드 전체 거부. 자동 마이그레이션·경고 후 강행 없음.
3. 업로드 성공 후 행 파싱 및 상속값 적용. 행별 셀 오류와 파일 전역 오류를 구분.
4. 같은 관리 IP의 동일 인터페이스 중복, 같은 장비 내 IP/Alarm ID 충돌, 같은 Instance ID 중복 등 교차 행 검증.
5. GUI에서 셀 수정 및 재검증 가능. 원본 파일을 자동 수정하지 않는다.
6. 기본은 전체 검증 결과를 보여주며, **독립적인 정상 Instance만 선택적으로 생성** 가능. 오류/미지원 Instance는 내보내기 대상에서 제외. 의존성이 있는 묶음은 부분 생성 금지.
7. 오류 보고서: 행 번호, Instance ID, 컬럼, 코드, 메시지, 입력값, 권장 조치.
8. XLSX/CSV의 셀 데이터는 실행 가능한 코드가 아니며, 출력 보고서에 CSV formula injection 방지 처리 적용.

## 7. Config 생성 및 결과 매핑

- 엔진은 템플릿의 단순 문자열 결합보다 앞서 의미적인 설정 변경을 모델링한다(예: target/interface, operation, property, value, owner_instance_id).
- **완전히 동일한 설정**은 안전하게 deduplicate 가능하나, 서로 다른 값을 같은 설정 대상에 쓰는 경우 충돌 오류를 발생시킨다. 원본 Instance 출처 목록은 유지한다.
- 출력: (1) Task별 CLI, (2) 장비(`management_ip`)별 통합 CLI, (3) Annotated, (4) Clean.
- Annotated 헤더 예: `// TASK IF-001 | interface.create | Router-A | et-0/0/0` (검토용에서만 사용).
- **Clean 출력에는 사용자가 복사해 적용할 수 있는 Junos CLI만 포함**하며 주석/추적용 텍스트를 섞지 않는다.
- UI 탐색은 CLI 주석 문자열 검색이 아니라 `GeneratedSection(instance_id, output_kind, start_line, end_line, commands)` 위치 매핑을 사용한다.
- 검증 통과하지 않은 항목의 Clean 출력은 원칙적으로 차단한다.
- Windows CRLF/LF의 파일 저장 옵션과 UTF-8 인코딩을 일관적으로 처리한다.

## 8. 프로젝트 파일 및 버전 추적

프로젝트 확장자: `.nobproj` (UTF-8 JSON). 구조 예:

```json
{
  "project_format_version": "1.0",
  "name": "HUB-GATE links",
  "inventory_source": "router_inventory.csv",
  "common_overrides": {"mtu": 4484},
  "instances": [],
  "tool_versions": {
    "task": "1.0.0",
    "schema": "1.0.0",
    "profile": "1.0.0",
    "template": "1.0.0"
  }
}
```

- 프로젝트 파일은 입력/참조/버전 정보를 저장. 외부 Inventory 파일 경로는 프로젝트 기준 상대경로를 우선 고려.
- 결과 재현을 위해 향후 resolved parameters, 파일 해시, 엔진 버전, 생성된 출력 SHA-256 추가 가능하도록 모델 확장.
- 저장은 임시 파일 작성 → 원자적 교체 방식으로 손상 위험을 줄인다. 버전 불일치 시 읽기 전용 또는 오류로 안전하게 처리.
- 최근 프로젝트 목록·윈도우 위치/크기·Splitter 상태·마지막 열기/저장 경로는 QSettings에 저장. 프로젝트의 Task 데이터는 QSettings에 넣지 않는다.

## 9. 테스트와 수용 기준

### 9.1 Golden Config 수집 원칙

- 기능별/플랫폼별 실제 기대 CLI가 필요해지면 **사용자에게 입력 조건과 기대 결과 샘플을 요청**한다. 근거 없는 명령어를 Golden 기준으로 만들어 확정하지 않는다.
- Fixture 구성: `tests/golden/<case_id>/input.json`, `expected.set`, `metadata.yaml`.
- pytest에서 Clean CLI 정확 비교와 의미적으로 중요한 규칙 검사 모두 수행. 변경 시 모든 기존 사례를 재검증.
- 기본 후보: 일반 IPv4/IPv6+IS-IS+MPLS, IS-IS passive, MPLS Off, FEC 미지원, IPv6 Off, RMON 변경, Bulk 10개 정상/중복, 구버전 양식 차단.

### 9.2 완료 기준 (Definition of Done)

- 승인된 Junos Golden Config를 대상으로 출력이 일치한다.
- Single 1개 Instance와 같은 행을 갖는 Bulk 1행의 Clean Config 출력이 동일하다.
- Bulk 10개 정상 행에서 10개 Instance가 생성되고, 유효한 장비별 출력으로 묶인다.
- FEC 미지원/미확인 모델에 FEC를 요청하면 생성이 거부된다.
- 중복 관리 IP CSV, 중복 인터페이스, 중복 RMON Alarm ID, 잘못된 IP는 진단된다.
- 구버전/버전 없는 Bulk 양식은 **파라미터 처리 전에** 거부된다.
- 좌측 Instance 선택 시 해당 Annotated/Clean 섹션으로 이동할 수 있다.
- 프로젝트 저장→종료→재열기 후 Task/공통값이 유지되고 Splitter 폭은 QSettings로 복원된다.
- 네트워크에 연결되지 않은 Windows PC에서 Standalone ZIP 압축 해제 후 실행 가능하다(보안 소프트웨어 허용 전제).
- 테스트 실패/미검증 항목을 정상 출력이라고 안내하지 않는다.

## 10. 권장 구현 구조

```text
network-operations-builder/
├── app/
│   ├── main.py
│   ├── gui/                # PySide6 Widgets, models, dialogs
│   ├── services/           # GUI - Engine bridge
│   ├── domain/             # TaskDefinition, Instance, GenerationResult
│   ├── engine/             # resolve, validate, rules, render, mapping
│   ├── inventory/          # CSV provider, repository interface
│   ├── bulk/               # XLSX/CSV template/import/export
│   ├── persistence/        # .nobproj and QSettings
│   └── resources/
├── definitions/
│   ├── tasks/
│   ├── profiles/
│   ├── schemas/
│   ├── capabilities/
│   └── templates/juniper/
├── tests/
│   ├── golden/
│   ├── unit/
│   └── integration/
├── packaging/
├── pyproject.toml
└── README.md
```

**구현 순서:** ① 도메인/Schema/테스트 Harness → ② Junos Interface Engine → ③ PySide6 Single GUI → ④ Schema 기반 Excel/CSV 생성·검증 → ⑤ Bulk GUI → ⑥ 내보내기/프로젝트 저장 → ⑦ Standalone ZIP → ⑧ Golden 회귀/수용 테스트.

## 11. 개발 중 미확정 정보의 처리

아래는 설계를 막는 결정이 아니라 실제 CLI를 확정하기 위한 **검증 입력**이다. 해당 기능 구현 시 사용자에게 최소한의 Golden 사례를 요청한다.

- Junos 장비별/버전별 FEC, speed, MTU 허용 값 및 CLI 위치
- `rmon` OID, Alarm ID 생성 규칙과 장비 내 충돌 검사 범위
- ISO/IS-IS passive 및 LDP synchronization의 표준 운영 규격
- CoS scheduler-map/classifier, IPv4/IPv6 filter 정책
- Interface 이름/Unit 및 Description 포맷의 확정 규칙

## 12. Codex 수행 지침

1. 먼저 이 명세와 `PYSIDE6_GUI_DESIGN.md`를 읽고 `TaskDefinition`, `TaskInstance`, `ResolvedParameters`, `GenerationResult` 데이터 모델 및 핵심 테스트부터 작성한다.
2. GUI에 CLI 생성 코드를 넣지 않는다. UI는 애플리케이션 서비스 API만 호출한다.
3. Profile/Schema/Template/Capability의 책임 경계를 유지한다. 불필요한 범용 규칙 엔진을 초기에 구현하지 않는다.
4. 미확정 장비 명령어는 지원된다고 추정하지 않는다. Golden Config가 없는 항목은 `TODO: needs golden config`로 식별하고 검증 차단 또는 샘플 모드로 표시한다.
5. 스키마, 양식, 템플릿 변경 시 버전을 갱신하고 Golden 테스트를 업데이트한다.
6. 프로젝트 생성·가져오기·내보내기 코드에 신뢰할 수 없는 로컬 파일 입력 검증을 적용한다.
