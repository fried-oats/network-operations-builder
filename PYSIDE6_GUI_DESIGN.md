# Network Operations Builder — PySide6 GUI 화면 설계서 (MVP v0.1)

> 상태: 구현 기준 초안 / 작성일: 2026-11-04  
> UI 프레임워크: PySide6 + Qt Widgets / 대상: Windows Desktop

## 1. 설계 목표

- **빠른 반복 작업:** Task 선택 → Schema 기반 파라미터 입력 → 실시간/명시적 Config 생성 → 검토/복사/저장.
- **공통 UX:** Single과 Bulk가 같은 Task/Schema/Capability/Renderer를 사용하며 화면의 가운데 입력 방식만 달라진다.
- **가벼운 실행:** 브라우저·서버·WebView·내장 HTTP 서버 없이 Qt Widgets만 사용한다.
- **넓은 모니터 최적화:** 좌/중/우 3단 분할, 드래그로 각 영역 너비 조절, 폭·창 상태 복원.
- **추적 가능성:** 좌측 Task Instance 클릭 시 우측 해당 CLI 시작 위치로 이동·강조.
- **안전한 정보 표현:** 지원되지 않는 Capability, 양식 버전 불일치, 검증 오류는 반드시 명확하게 드러난다.

## 2. 내비게이션과 정보 구조

```text
Network Operations Builder
├── File
│   ├── New Project / Open Project / Save / Save As
│   ├── Load Router Inventory CSV
│   ├── Export Config / Export Validation Report
│   └── Recent Projects / Exit
├── Task Builder
│   ├── Single Task
│   └── Bulk Task
├── Task Catalog
│   └── Interface
│       └── Interface 연동 생성
├── View
│   ├── Reset Panel Layout
│   ├── Show Validation Panel
│   └── Toggle Annotated / Clean
└── Help
    ├── Schema/Template Versions
    └── About
```

워크플로 빌더 메뉴는 v0.1에서 숨기거나 비활성 상태로 보여주되, 실제 동작 기능을 구현하지 않는다. 향후 `BGP`, `Routing Protocol`, `System` 카테고리와 Task Registry 확장 시 메뉴가 동적으로 추가될 수 있도록 한다.

## 3. 메인 윈도우 와이어프레임

```text
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ Network Operations Builder                            [New] [Open] [Save] [Export]        │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│ Project: HUB-GATE-Links   Inventory: router_inventory.csv   Profile: hub-gate  [Validating]│
├──────────────────────┬─────────────────────────────────────────┬───────────────────────────┤
│ LEFT                 ╎ CENTER                                  ╎ RIGHT                     │
│ Task Catalog         ╎ [Single Task] [Bulk Task]               ╎ [Task] [Router]            │
│ > Interface          ╎                                         ╎ [Annotated] [Clean]       │
│   Interface Create   ╎ Router: [Router-A ▼]                    ╎                           │
│ > BGP (future)       ╎ Model:  [PTX10008]                     ╎ // TASK IF-001            │
│                      ╎ Profile: [HUB-GATE ▼]                    ╎ set interfaces ...         │
│ Task Instances       ╎ ── Interface ───────────────────────── ╎                           │
│ [+ Add] [- Remove]   ╎ Local: [et-0/0/0]  Peer: [et-0/0/8]     ╎ // TASK IF-002            │
│ IF-001  et-0/0/0     ╎ IPv4:  [192.168.0.1/30]                ╎ set interfaces ...         │
│ IF-002  et-0/0/1     ╎ IPv6:  [2400::...]                      ╎                           │
│ IF-003  et-0/0/2     ╎ Speed: [100g ▼]  MTU: [4484]             ╎                           │
│                      ╎ FEC:   [none ▼] (capability dependent)   ╎                           │
│                      ╎ ── Features ─────────────────────────── ╎                           │
│                      ╎ [x] ISO/IS-IS [x] MPLS/LDP             ╎                           │
│                      ╎ [x] RMON     [x] CoS                   ╎                           │
│                      ╎ [Generate / Validate]                  ╎ [Copy] [Save Config]      │
├──────────────────────┴─────────────────────────────────────────┴───────────────────────────┤
│ Validation: 0 error · 0 warning | 3 Tasks | Juniper Junos | No network connection required│
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **기본 폭 비율:** Left 22%, Center 43%, Right 35% (사용자 조절 가능).
- 각 패널 최소 너비 제안: Left 220 px, Center 420 px, Right 360 px. 화면이 작으면 내부 스크롤 사용.
- 주요 Splitter: 최상위 `QSplitter(Qt.Horizontal)`로 좌·중·우 세 패널 분할; `setChildrenCollapsible(False)` 적용. `saveState()/restoreState()`를 QSettings로 저장/복원한다.
- 메뉴/툴바/상태바는 `QMainWindow`; 중앙 `QSplitter`가 메인 편집 영역.
- 앱 창 최소 크기는 1100×700 정도부터 검토하되 실제 DPI/해상도에서 조정한다.

## 4. 좌측 패널 — Task Catalog / Task Instance

### 4.1 컴포넌트

- 상단: `QTreeView` 또는 `QTreeWidget` — Task Catalog. MVP 항목은 `Interface > Interface 연동 생성` 한 개.
- 하단: `QListView` + `QAbstractListModel` — 현재 프로젝트의 Task Instance 목록.
- 검색 입력창: Task 이름/Instance ID/장비/인터페이스 부분 검색.
- 버튼: `Add Task`, `Duplicate`, `Remove`, `Rename`(선택), 향후 Import.
- Instance 항목 표시: `IF-001 · Router-A · et-0/0/0`, 별도의 검증 상태 아이콘.
- 클릭 시 가운데 선택 Instance 파라미터 로드, 우측 해당 `GeneratedSection` 스크롤.
- 더블클릭은 같은 기능. GUI가 Task ID 이름에 의존하지 않고 모델 ID를 사용.

### 4.2 선택/삭제/수정 규칙

- Instance 선택은 기존 변경값 저장(메모리 모델) 후 다른 Instance 로드; 변경사항 손실 방지.
- 삭제는 복구 불가능한 내용이 있다면 확인 대화상자 제공.
- 동일 Task Definition의 여러 Instance는 독립 데이터(서로 다른 인터페이스·IP)를 가진다.
- validation/preview 업데이트는 signal-slot으로 중앙·우측과 동기화.

## 5. 가운데 패널 — 입력 편집기

### 5.1 상단 공통

- `QTabWidget` 또는 토글: **Single Task / Bulk Task**. 탭 변경은 Task 인스턴스를 변환하지 않고 기존 데이터를 유지.
- Router 선택 `QComboBox` + 자동완성(`QCompleter`): CSV의 `Name` 및 `management_ip`로 검색.
- 선택 후 `management_ip`, Manufacturer, Model, Hierarchy를 표시 (읽기 전용); OS Version/Interface Type이 필요한 Capability는 명확한 추가 입력 필드.
- Profile 선택 `QComboBox`, 해당 Task에 유효한 Profile만 노출.

### 5.2 Single Task 폼

`QScrollArea` 내부에 기능별 `QGroupBox`(접기/펼치기 지원 가능)를 배치한다.

| Group | 입력/컨트롤 | 동작 |
|---|---|---|
| Link | Local/Peer Interface, Peer Router | Description 생성 규칙 반영 |
| Addresses | IPv4/IPv6 | 입력값 즉시 형식 검사, 빈칸 상속 |
| Physical | Speed, MTU, FEC | Capability 허용값만 제공; unknown은 별도 오류 |
| Filters | IPv4/IPv6 Input/Output | 개별 선택값 입력 |
| ISO/IS-IS | Enabled, Passive, Level, Metric | Enabled에 따라 상세 입력 활성화 |
| MPLS/LDP | MPLS Enabled, LDP Enabled | 관계 검증, 동기화 정책 적용 |
| SNMP RMON | Enabled, ifIndex, Alarm IDs | Enabled일 때 필수값 검증 |
| CoS | Enabled, Scheduler Map, Classifier | Profile 기본값 활용 |

#### 필드 상태의 차이

- `Inherited`: 빈칸/미입력 → 유효 기본값을 상속하며 회색 helper text로 `Profile: 4484` 같은 실제 적용값과 출처를 표시.
- `Enabled/Disabled`: 체크박스 또는 명시적인 세 상태 선택(상속/활성/비활성); Off는 값의 미입력과 다름.
- `Unsupported`: capability가 미지원임을 레이블에 표시하며 사용자가 이미 강제 입력한 값이 있으면 validation error.
- `Unknown`: 지원 여부를 판정할 데이터 부족 → 임의 출력 금지, 모델/OS/인터페이스 정보 확인 안내.
- Schema를 렌더링하는 `FieldWidgetFactory`를 만들어 `string`, `integer`, `ip_interface`, `bool/tri-state`, `enum`을 매핑한다. `visible_when`은 UI 표현이지만 실제 사용 가능 여부는 엔진이 재검증한다.

### 5.3 Bulk Task 편집기

상단 액션바:

`[Download XLSX Template] [Download CSV Template] [Import XLSX/CSV] [Revalidate] [Export Errors]`

중앙 테이블: `QTableView` + `QAbstractTableModel`(행 수가 늘어나도 안정적으로 편집). 행=Task Instance, 열=Schema 필드.

- 컬럼 고정: Instance ID, Target Router (`management_ip`), Local Interface, Peer Interface, IPv4, IPv6, Speed, MTU, ...
- 인라인 편집: 문자열/QLineEdit, Enum/QComboBox, Integer/QSpinBox 등을 delegate로 제공.
- 헤더에 필수/옵션/상속 정보를 Tooltip으로 표시.
- 행별 검증 아이콘, 오류 있는 셀 색/테두리, 하단 검증 상세 패널.
- 정렬/필터는 UI 표시 전용으로, 저장/내보내기 Instance 순서는 별도 명시.
- `Common Defaults` 편집 영역을 테이블 상단/별도 패널로 제공. 우선순위는 `행 값 > 공통값 > Profile > 시스템`.
- 업로드 파일의 버전 오류는 **가져오기 자체 거부**. 테이블에 부분 반영하지 않고 오류 대화상자에서 현재 지원 버전과 최신 양식 생성 버튼 제공.
- 업로드 성공 후 일부 셀 오류가 있으면 테이블에서 수정할 수 있고, 정상/경고/오류 개수를 요약 표시.
- `Generate Selected Valid`/`Generate All Valid`는 행 간 독립성을 확인하고 유효하지 않은 행 제외 여부를 명확히 표시.

## 6. 우측 패널 — Config Preview / Inspector

### 6.1 상단 컨트롤

- `Task View` / `Router View` (`QComboBox` 또는 탭)
- `Annotated` / `Clean` 토글
- 검색(특정 Interface/명령어), `Copy`, `Save Config`.
- Preview는 **읽기 전용** `QPlainTextEdit` 권장. Syntax highlighting은 `QSyntaxHighlighter`로 구현 가능.

### 6.2 출처 이동/강조

- 생성 엔진이 각 Instance의 출력 위치와 섹션/명령어 출처를 `GeneratedSection` 객체로 제공.
- 좌측 Instance 선택 시 해당 섹션의 `start_line`으로 텍스트 커서를 이동하고 `centerCursor()` 또는 동등한 스크롤 API 호출.
- 해당 섹션을 `ExtraSelection`으로 일시/선택 동안 강조.
- CLI 출력 순서나 중복 제거로 위치가 달라질 때는 **출력마다 매핑을 재계산**, 텍스트에서 `// TASK`를 검색하여 찾지 않는다.
- 한 CLI가 여러 Instance에서 공유되어 dedupe된 경우 출처 목록과 다중 위치 매핑이 가능하도록 모델 준비.

### 6.3 출력 형태

**Annotated Review** (사람 검토용):

```text
// TASK IF-001 | interface.create | Router-A | et-0/0/0
// Profile: hub-gate | management_ip: 10.10.10.1
set interfaces et-0/0/0 speed 100g
set interfaces et-0/0/0 mtu 4484
```

**Clean Config** (CLI만):

```text
set interfaces et-0/0/0 speed 100g
set interfaces et-0/0/0 mtu 4484
```

- `//` 주석은 Annotated Review 전용이며 Clean Config에서 절대 포함하지 않음.
- Validate 결과가 오류라면 해당 Instance의 Clean Config 저장/복사는 차단. 미지원 OS Renderer 선택 시 유효한 출력처럼 표시하지 않는다.
- Preview 하단에는 경고/오류 목록 클릭 시 관련 필드로 이동할 수 있는 Inspector를 둘 수 있다.

## 7. 사용자 흐름 (Step-by-step)

### A. Single Task

1. `New Project` → `Load Inventory CSV`.
2. Task Catalog > `Interface 연동 생성` 클릭 → `Add Task`.
3. Router 검색/선택 → `management_ip`, Vendor, Model 자동 조회.
4. Profile `HUB-GATE` 선택 → 기본값 상속됨.
5. Local/Peer Interface 및 IP 입력 → ISO/IS-IS, MPLS/LDP, RMON, CoS 선택.
6. 즉시 Schema/Capability 검증, 필요 시 Validate 버튼.
7. 우측 Task/Router, Annotated/Clean 확인 → 복사 또는 TXT 저장.
8. 프로젝트 `.nobproj` 저장 및 재열기.

### B. Bulk Task

1. Task Catalog > `Interface 연동 생성` → 가운데 `Bulk Task` 탭.
2. Profile/공통값 선택 → `Download XLSX/CSV Template`.
3. Excel/CSV로 여러 Instance 행 입력.
4. `Import` → 버전/구조 검사; 불일치 시 전체 거부.
5. 테이블에 행별 검증 결과 표시 → 오류 셀 수정 → Revalidate.
6. 정상 Instance 전체 또는 선택 생성 → 우측 Router 통합 Config/Task별 Config 확인.
7. 좌측 IF-00x 클릭 → 우측 해당 출처 섹션으로 이동.
8. Config와 오류 보고서 저장, `.nobproj` 저장.

## 8. 대화상자와 오류 UX

| 이벤트 | UI 응답 |
|---|---|
| Inventory CSV 없음/열기 실패 | 파일 선택/재시도 메시지, 기존 입력 유지 |
| `management_ip` 중복 | 파일/행/중복 IP 표기 후 로드 거부 |
| Capability Unsupported | 문제 필드 및 플랫폼 정보 명시, Generate 차단 |
| Capability Unknown | 부족한 OS/모델/인터페이스 정보 명시, Generate 차단 |
| Bulk 구버전 | 지원/업로드 버전 비교, **최신 양식 다운로드** 제공, 가져오기 전체 취소 |
| Bulk 일부 행 오류 | 오류 셀 하이라이트, 상세 메시지, 보고서 다운로드 |
| 서로 충돌하는 Instance | 대상 Router/Interface/설정 키와 충돌 Instance IDs 표시 |
| 프로젝트 미저장 상태 닫기 | Save / Discard / Cancel |
| 파일 저장 실패 | 원본 파일 보존, 경로/권한 오류 표시 |
| 검증 통과 | 성공 개수/경고 개수 및 출력 준비 상태 표시 |

에러 메시지는 사용자가 **어디서, 무엇이, 왜** 잘못됐는지 알 수 있도록 `행 번호`, `instance_id`, `필드`, `입력값`, `사유`, `해결방법`을 포함한다. 단, OS/플랫폼 지원을 정확히 판단할 수 없으면 추정값을 제시하지 않는다.

## 9. 컴포넌트 계층 및 이벤트

```text
MainWindow(QMainWindow)
├── MainToolbar
├── ProjectInfoBar
├── MainSplitter(QSplitter, Horizontal)
│   ├── TaskPanel(QWidget)
│   │   ├── TaskCatalogView(QTreeView)
│   │   └── TaskInstanceList(QListView)
│   ├── EditorPanel(QWidget)
│   │   ├── ModeTabs(QTabWidget)
│   │   ├── SingleTaskEditor(QScrollArea)
│   │   └── BulkTaskEditor(QTableView)
│   └── ConfigPreviewPanel(QWidget)
│       ├── ViewOptions
│       ├── ConfigEditor(QPlainTextEdit, readOnly)
│       └── ValidationInspector
└── StatusBar
```

권장 이벤트:

- `inventoryLoaded(records)` → Router Selector, Capability Context 갱신
- `instanceSelected(instance_id)` → Editor 전환 + Config 위치 이동
- `parametersChanged(instance_id, changed_fields)` → 엔진 재검증/Preview 재생성
- `bulkImported(instances)` → 목록/테이블/검증 갱신
- `validationCompleted(report)` → 상태/오류 패널 업데이트
- `generationCompleted(result)` → Config 뷰/출처 매핑 업데이트
- `projectModified(dirty)` → 제목에 `*` 표시, 종료 전 저장 확인

무거운 Bulk 파싱/검증은 `QThreadPool`/`QRunnable` 또는 적절한 worker로 UI 스레드와 분리한다. 위젯은 메인 UI 스레드에서만 조작하고, Worker는 signal로 결과를 전달한다. 작은 Single 변경은 debounce하여 반응성을 확보한다.

## 10. UI 상태·접근성·성능

- MVP는 한국어 UI 기본, 내부 필드 ID는 영문 snake_case.
- Tab/Shift+Tab 포커스 순서, Esc로 대화상자 닫기, Ctrl+S 저장, Ctrl+O 열기, Ctrl+C 복사 등 표준 단축키.
- 오류는 색상만으로 표시하지 않고 아이콘/문구를 병행.
- 사용자가 가로 폭을 조절한 Splitter 상태는 재실행 후 복원.
- 대량 테이블은 `QTableView + QAbstractTableModel`; 수백 행에서도 정상 스크롤/선택 및 오류 표시 가능해야 한다.
- Preview 텍스트는 고정폭 폰트, 줄 번호 표시 여부는 구현 중 선택.
- 단일 Task의 실시간 Preview는 입력 중 파싱 오류가 발생하더라도 UI가 멈추지 않도록 이전 성공 결과와 현재 검증 상태를 명확히 구분.
- UI 색상/아이콘을 제조사별 지원 여부의 유일한 표현 수단으로 사용하지 않는다.

## 11. 화면별 완료 기준

| 화면 | 확인 방법 |
|---|---|
| 메인 Splitter | 세 패널 경계 드래그로 폭 조정, 재시작 후 동일 크기 복원 |
| Router Picker | CSV 이름/관리 IP로 검색, PTX10008 등 모델에 따른 Capability 반영 |
| Single Editor | 빈칸 상속, `disable` 명시 해석, 필드별 오류 표시 |
| Bulk Editor | 최신 XLSX/CSV 양식 생성, 구버전 거부, 10행 표시/수정/검증 |
| Config Preview | Clean/Annotated, Task/Router 전환, 좌측 Instance 선택 시 섹션 탐색 |
| Project File | `.nobproj` 저장/열기 후 인스턴스와 공통값이 동일 |
| Export | TXT/오류 보고서 생성, 오류/미지원 출력 차단 |

## 12. Codex 구현 주의사항

1. GUI 위젯에 CLI 템플릿 로직을 넣지 않는다.
2. 사용자가 입력한 원시값과 기본값 상속 후 최종값을 구분한다.
3. UI에서 숨겨진 필드도 엔진 검증을 우회할 수 없다.
4. Preview 탐색은 주석 텍스트 검색이 아닌 구조화된 line mapping을 사용한다.
5. 초기에는 과도한 UI 애니메이션, 복잡한 QML, 내장 웹뷰를 사용하지 않는다.
6. Bulk Import 거부 시 기존 프로젝트 데이터가 사라지지 않도록 임시 모델에서 파싱·검증한 후에만 반영한다.
7. 사용자 제공 Golden Config와 Capability 자료가 없으면 CLI의 유효성을 가정하지 않고 검증 필요 항목으로 남긴다.
