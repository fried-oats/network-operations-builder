# 사용자 제공 Golden Config

ptx10008_backbone은 GL-PO239 입력/기대 CLI 및 후속 확인을 보관합니다.
범위: PTX10008 / 23.4R2-S1.6-EVO / et, unit 0, 100g/MTU4484/FEC none,
dual stack/필터, IS-IS L2 P2P, MPLS/LDP, RMON, backbone CoS.

- input.json: Inventory, instances, common_overrides
- expected.set: 정확한 Clean CLI (순서/빈 줄/LF 비교)
- metadata.yaml: 사용자 출처, 모델/OS/인터페이스, 후속 수정 근거

후속 확인으로 speed 명령을 description 다음에 추가했습니다.
QDrop=8000+ifIndex, CRC=9000+ifIndex를 확인받았으며 Rx Optics는 추후 구현합니다.
실제 관리 IP가 제공되지 않아 192.0.2.239를 테스트용 Inventory 키로 사용합니다.

cos_external/reference.set은 제공된 ae0 CoS 단편만 비교하며 전체 ae 생성 승인이 아닙니다.
IS-IS passive는 아래 1.3.0 Golden으로 지원합니다. 다른 OS/MTU/FEC와 전체 ae 생성에는 추가 사례가 필요합니다.
새 승인 사례를 같은 파일 구조로 추가하면 test_golden.py가 자동으로 발견합니다.
TEST_ONLY 템플릿은 인프라 대역으로 Junos Golden이 아닙니다.

## 1.2.0 입력 개편

Inventory Name 기반 Description 자동 조합(speed 원문, circuit_id, etc), 기본 metric1000,
RMON ID 계산 전용, external et CoS를 반영했습니다.
ptx10008_backbone / ptx10008_external은 새 출력이며, ptx10008_backbone_v1_1은
기존 출력 및 정의 스냅샷을 보존한 회귀 사례입니다. 기본 metric은 1000이지만 Golden은 명시 입력150을 유지합니다.

## 1.3.0 Passive

ptx10008_passive는 사용자 확인 모델/OS, 기존 Description/speed 유지 방침을 반영한 전체 Golden입니다.
passive_reference는 최초 수신 CLI 원문을 독립적으로 보존합니다.
현재 및 1.2.0/1.1.0 Golden 스냅샷을 모두 회귀 비교합니다.

## 1.4.0 Link mode

현재 Golden 입력은 cos_mode 대신 link_mode를 사용하며 CLI 기대 결과는 변경하지 않았습니다.
1.3.0 입력/정의/기대 결과 스냅샷도 보존해 회귀 검증합니다.

## 1.4.1 Link flow control

현재 external Golden은 사용자 추가 CLI에 따라 no-flow-control을 FEC 앞에 포함합니다.
backbone/passive Golden 출력은 각각의 link_mode 규칙에 맞춰 검증합니다. 1.4.0 정의/Golden도 보존합니다.
