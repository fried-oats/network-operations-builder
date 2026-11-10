# API Inventory 사용

## 설정과 접속

소스 실행은 프로젝트 루트, Standalone 실행은 EXE 옆의 `config/.env`를 읽습니다.
실행한 터미널의 현재 폴더가 달라도 설정 위치는 바뀌지 않습니다.

배포 ZIP의 `config/.env.example`을 `.env`로 복사한 후 주소를 설정하세요.

```ini
API_BASE_URL="http://192.168.0.53:8000"
```

설정 파일은 UTF-8입니다. 작은/큰 인용부호, 공백, 주석을 지원합니다.
설정값을 셸 명령으로 실행하거나 환경변수로 확장하지 않습니다.
기본 연결 timeout은 요청당 10초입니다.

**파일 → API Inventory 불러오기**를 선택합니다.
로그인이 필요한 서버는 API ID/비밀번호를 입력하고 불러오기를 누르세요.
익명 조회를 허용하는 서버만 두 칸을 비워서 조회할 수 있습니다.
ID/비밀번호/토큰은 QSettings, 프로젝트, 로그 또는 .env에 저장하지 않습니다.

로그인 토큰은 조회 작업 중 메모리에서만 사용하고 작업이 끝나면 클라이언트에서 제거합니다.
API 조회는 Worker에서 수행하며, 프로젝트를 변경한 뒤 도착한 응답은 반영하지 않습니다.
Inventory는 API 전용입니다. CSV Inventory 메뉴/파서는 제거했습니다. Bulk 작업 입력용 CSV/XLSX는 유지합니다.

## 적용한 OpenAPI 계약

| 요청 | 형식 |
|---|---|
| POST /token | JSON `{"id": "...", "pw": "..."}` |
| GET /router/ | 인증 시 `Authorization: Bearer <access_token>` |
| POST /token/refresh | GET이 401일 때 보유한 refresh_token으로 한 번 갱신 후 재조회 |

라우터 목록은 RouterRead 객체의 JSON 배열입니다. 페이지네이션은 제공된 명세에 없어 사용하지 않습니다.
라우터/제조사/사용자 생성·수정·삭제 API는 호출하지 않습니다.
HTTP 리다이렉트는 따라가지 않고 서버 오류 본문이나 인증 정보를 오류창에 출력하지 않습니다.

## Inventory 변환

- `ipaddr`: 필수 정수 IP. `ipstr`이 없거나 빈 문자열이면 정수에서 관리 IP를 결정합니다.
- `ipstr`: 있으면 IP 형식을 검사하고 정수 `ipaddr`와 같은 주소인지 확인합니다.
- 관리 IP는 표준 IP 표기로 정규화하며, 중복 주소는 응답 전체 로드 오류입니다.
- name/hierarchy/group/location/operation_team/manufacturer/model은 RouterRead의 필수 문자열입니다.
- os_version의 null/누락은 빈 값으로 유지합니다. 사용자 입력으로 보완할 수 있습니다.
- Juniper/Juniper Networks → Juniper, 알려진 모델 별칭을 공통 Inventory 정규화 규칙으로 변환합니다.
- Juniper는 os_family=Junos입니다. 알 수 없는 제조사/모델/OS 지원은 추정하지 않습니다.

20MB 응답 및 100000개 라우터 제한을 적용합니다. 한 행이라도 잘못되면 기존 Inventory를 보존합니다.
실패해도 Task/공통값/프로젝트 경로는 바뀌지 않습니다. 정상 결과만 원자적으로 교체합니다.
변환 후 Single/Bulk는 기존 Config Engine을 그대로 사용합니다.

## 프로젝트 저장과 재열기

API Inventory의 출처는 프로젝트에 `api:/router/`로 기록합니다. 서버 주소/자격 증명을 기록하지 않습니다.
API 목록 자체도 프로젝트에 내장하지 않습니다. 재열기 시 기존 Task/공통값을 유지하고 API 재조회를 안내합니다.
프로젝트 열기나 앱 시작 시 자동으로 네트워크 요청을 보내지 않습니다.
기존 CSV 출처의 프로젝트는 CSV 파일을 읽지 않고 API 참조로 전환합니다.
Task/공통값은 유지하며 API 재조회를 안내합니다. 저장하면 이전 CSV 경로는 제거됩니다.
Config 및 Bulk 정의/양식 버전은 1.4.1 그대로입니다.

## 검증

로그인 JSON/Bearer 헤더, 토큰 갱신, 권한/timeout/잘못된 응답, IP 변환·중복,
GUI 목록 갱신과 실패 시 데이터 보존, API 프로젝트 저장/재열기, 기존 CSV 참조 프로젝트 전환 및 Bulk CSV/Golden 회귀를 테스트합니다.
사내 실서버는 연결 및 인증 필요 응답을 확인했습니다. 실계정 로그인과 실제 목록 조회는 계정 입력 후 확인해야 합니다.
