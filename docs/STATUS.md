# MVP v0.1 Preview 구현 상태 — 정의 버전 1.4.1

## 추가 기능: API Inventory

config/.env의 API_BASE_URL, JSON 로그인/Bearer 인증/토큰 갱신, GET /router/ 조회를 지원합니다.
Inventory는 API 전용이며 CSV Inventory 메뉴/파서는 제거했습니다. 기존 InventoryRecord/Config Engine은 유지합니다. 실패/잘못된 응답은 기존 데이터를 보존합니다.
네트워크는 Worker에서 처리하며 자격 증명은 저장하지 않습니다. API 프로젝트는 재열기 시 명시적으로 재조회합니다.
Bulk 작업 입력용 CSV/XLSX와 로컬 Config 생성은 유지합니다. 자세한 사용법은 API_INVENTORY.md를 참고하세요.

새 프로젝트 이름 입력 및 파일 메뉴의 프로젝트 이름 변경을 지원합니다.
공백 이름은 거부하고 취소 시 기존 프로젝트를 유지합니다. 이름은 저장/재열기 후 복원되며,
이름 변경은 기존 Task/Inventory/Config Preview를 보존합니다. 정의/양식 버전은 1.4.1 그대로입니다.

## 이번에 연결된 사용자 Golden

PTX10008 / Junos 23.4R2-S1.6-EVO / et, unit 0에 대해 사용자가 제공한 기대 CLI를
정확 비교합니다. speed100g, MTU4484, FEC none, dual stack/필터, ISO/IS-IS L2 P2P,
metric/IPv6 metric, hello10/hold30, LDP sync, MPLS/LDP, RMON, backbone CoS를 포함합니다.
Description은 Inventory Name과 Link 필드로 자동 생성합니다. circuit_id/ etc 입력을 사용합니다.
isis_metric 기본값은 1000이며, platform/수동 Description/RMON ID 입력은 제거했습니다.
Inventory os_version 및 Juniper→Junos 매핑으로 OS를 자동 입력합니다. MPLS는 상속 LDP를 활성화하고 명시적 Off는 유지합니다.
RMON은 QDrop=8000+ifIndex, CRC=9000+ifIndex 정책으로 ID를 계산하고 교차 충돌을 검사합니다.
Rx Optics +7000은 추후 추가합니다.

external CoS의 et classifiers 두 줄은 전체 Task Golden으로 검증합니다. 기존 ae0 단편도 보존합니다.
IS-IS passive는 사용자 확인 Golden으로 구현했습니다. ae 전체 생성은 추가 Golden이 필요하므로 차단합니다. 미확인 OS/기능/값도 생성하지 않습니다.

## 기존 기반 기능

독립 도메인/정의 모델, Registry, Single/Bulk 공통 엔진, 상속/명시적 Off/출처,
Schema/Profile/Capability/의존성 검증, 관리 IP Inventory, 장비별 인터페이스/주소/Alarm ID 충돌,
의미적 ConfigChange와 Jinja Renderer, Clean/Annotated 및 장비별 매핑을 구현했습니다.

Bulk XLSX 4개 시트/CSV+가이드, 엄격한 버전, 수식 거부/보고서 이스케이프,
3단 Qt Splitter, Schema 폼, editable Bulk 모델, worker 검증, 출처 강조,
프로젝트 원자적 저장/API Inventory 참조, QSettings, LF/CRLF TXT/클립보드/보고서,
Standalone ZIP 빌드 및 EXE 시작 점검이 있습니다.

## 남은 작업

- 다른 모델/OS/물리값 및 ae 전체 생성에 대한 Golden/Capability 확장.
- Rx Optics 정책(+7000) 구현. Description 자동 조합은 구현됨.
- Capability 기반 선택지 제한 UX, Bulk 타입별 delegate, 선택한 정상 행만 생성.
  현재는 전체를 검증해 독립적인 정상 Instance 전체를 생성합니다.
- 공통값은 JSON 편집기이며 별도 Schema 폼으로 개선 가능.
- 보고서 행 번호는 Instance 데이터 행 기준으로 원본 중간 빈 행은 추적하지 않습니다.
- Task View는 연결된 출력이며 개별 Task 파일 선택 UX는 후속 항목입니다.
- 별도 오프라인 Windows PC/DPI/접근성 수용 검증 및 사내 라이선스/보안 검토.

Task/Schema/Profile/Template 1.4.1으로 갱신했습니다. 이전 버전 프로젝트/양식은 엄격히 거부하며
자동 마이그레이션하지 않습니다. 예제 Inventory 관리 IP는 테스트용 192.0.2.239입니다.

기존 1.1.0 Golden과 정의 스냅샷을 보존하며, 1.3.0 backbone/external 출력도 정확 비교합니다.
Placeholder는 default: 값으로 표시합니다. circuit_id는 두 숫자 포맷 또는 Direct를 검증합니다.

## IS-IS passive 완료

PTX10008 / 23.4R2-S1.6-EVO / et에서 metric0, ISO/MPLS/LDP 차단, no-flow-control,
level2 passive를 지원합니다. 기존 Description/speed 생성과 사업자명 AS 괄호를 보존합니다.
1.1.0/1.2.0 Golden 스냅샷, 현재 backbone/external/passive 전체 출력 및 GUI 원시값 복원을 검증합니다.
상세 규칙은 PASSIVE_IMPLEMENTATION.md를 참고하세요.

기존 CSV 참조 프로젝트는 CSV를 읽지 않고 API 참조로 전환하며 Task/공통값을 보존합니다.
예제 Inventory CSV는 배포에서 제외했고, 예제 프로젝트도 API 출처로 변경했습니다.

## Link mode 입력 개편 (1.4.0)

CoS의 cos_mode를 제거하고 Link에 link_mode(backbone/external)를 추가했습니다.
기본값은 backbone이며 CoS On/Off와 독립적으로 입력/저장/검증합니다. CoS 출력은 link_mode를 참조합니다.
IS-IS/passive 등 기존 기능은 별도 입력을 유지하고, CLI는 기존 Golden과 일치합니다.
1.3.0 Golden/정의도 스냅샷으로 보존했습니다. 새 Bulk 양식은 link_mode 컬럼을 사용합니다.

## Link mode flow control (1.4.1)

no-flow-control은 passive 여부가 아닌 link_mode=external 조건으로 생성합니다.
backbone은 passive여도 FEC만 생성하며, external은 P2P/passive/IS-IS Off 및 CoS Off에서도
no-flow-control 다음 FEC 순서로 생성합니다. 기존 1.4.0 Golden과 정의는 스냅샷으로 보존합니다.
