# MVP v0.1 구현 계획 및 경계

## 구조와 책임

| 경로 | 역할 |
|---|---|
| app/domain | Qt 의존성 없는 정적 정의, Instance, 해석값/출처, 진단, 의미적 변경, 출력 매핑 |
| app/engine | Registry, 입력 정규화, 상속, Schema/Profile/Capability/의존성/교차 행 검증, Jinja 렌더링 |
| app/inventory | API Repository, 정수 IP/문자열 IP 검증, management_ip 키 |
| app/bulk | 정확한 양식 버전 계약, XLSX/CSV 생성/가져오기, 수식 거부, 오류 보고서 |
| app/persistence | JSON .nobproj, 엄격한 버전, 원자적 저장 |
| app/services | GUI와 엔진 연결, 프로젝트/입출력 조정 |
| app/gui | Qt Widgets 3단 화면, Schema 폼, editable table model, worker, Preview/매핑 |
| definitions | 독립 Task/Profile/Schema/Capability/Template 외부 파일 |
| tests | unit, integration, 사용자 승인 Golden 사례 |
| packaging | Windows onedir 빌드와 ZIP, 라이선스/의존성 명세 |

## 단계

1. 도메인/Registry/Schema 및 pytest 기반 마련.
2. 공통 엔진: 파싱 → 상속 → Schema → Profile → Capability → 의존성/교차 행 충돌 → 의미적 변경 → Renderer → 매핑.
3. Inventory API, Bulk XLSX/CSV, 버전 거부, 프로젝트 저장/재열기 및 회귀 테스트.
4. PySide6 Single/Bulk 편집, 비동기 검증, 출처 탐색, QSettings, 파일 입출력.
5. 사용자 Golden 수령 → 실제 Junos semantic lowering/Template 확정, 기능별 Capability 범위 승인, 정확 비교 회귀.
6. Standalone 폴더/ZIP 및 별도 오프라인 Windows PC 수용 테스트.

## Golden 반영 현황 (정의 버전 1.4.1)

사용자 제공 PTX10008 / 23.4R2-S1.6-EVO / et unit 0 사례와 후속 speed/RMON 정책을 반영했습니다.
실제 Junos ConfigChange lowering과 템플릿을 연결하고 정확 출력 회귀를 추가했습니다.
Inventory OS 자동 입력과 Description 자동 조합을 반영했고, speed100g는 명령 생성, RMON ID는 8000/9000+ifIndex입니다.
External et CoS를 지원하며, IS-IS passive를 구현했으며 전체 ae 생성/다른 OS는 추가 Golden이 필요합니다.
상세 완료/후속 항목은 STATUS.md를 참조하세요.

현재 Inventory는 사용자 후속 요청에 따라 API 전용입니다. 초기 설계의 CSV Inventory 요구는 대체되었으며,
Bulk 작업 입력용 CSV/XLSX는 계속 지원합니다.
