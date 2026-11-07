# IS-IS passive 구현 (정의 1.3.0)

## 구현한 정책

IS-IS Enabled + Passive가 모두 활성일 때 다음 값을 엔진에서 강제 적용한다.

| 항목 | P2P | Passive |
|---|---|---|
| IPv4/IPv6 metric | 입력값 / 기본 1000 | 0 |
| family iso | 생성 | 생략 |
| family mpls, protocols mpls | MPLS 선택에 따름 | 생략 |
| protocols ldp, LDP sync | LDP 선택에 따름 | 생략 |
| ether-options no-flow-control | 생략 | 생성 |
| IS-IS 명령 | point-to-point, hello/hold | level 2 passive |
| RMON / CoS | 선택에 따름 | 선택에 따름 |

metric 하나를 IPv4/IPv6 공통값으로 사용하므로 두 출력 metric 모두 0이다.
CoS는 별도 선택으로 유지하며, external 선택 시 기존 IN_ISP classifiers를 생성한다.
passive 활성 시 metric/MPLS/LDP 입력과 hello/hold 입력을 비활성화한다.
원시 입력은 보존하므로 passive 해제 시 이전 값이 복원된다.
자동 적용값의 출처는 rule:isis_passive로 기록한다. Profile 고정값과 충돌하면 출력 차단한다.

## 확인된 범위와 검증

- 사용자 제공 CLI를 tests/golden/passive_reference/reference.set에 그대로 보존했다.
- Renderer 단위 테스트에서 Description을 주어진 문자열, speed 명령을 미선택한 입력으로
  전체 CLI/빈 줄/IPv6 표기까지 정확 비교한다.
- 사용자 확인: LA-POP239는 PTX10008 / Junos 23.4R2-S1.6-EVO이다. 해당 et 범위의 passive Capability를 활성화했다.
- 사용자 확인: 기존 자동 Description과 speed 입력/명령 생성을 유지한다.
- Netflix(AS2906) 같은 사업자 이름과 AS 괄호는 그대로 보존하고, peer_interface를 기존 형식대로 별도 괄호에 붙인다.
- 기존 1.1.0/1.2.0 Golden 및 정의 스냅샷을 보존해 이전 출력도 계속 비교한다.

전체 엔진 Golden은 tests/golden/ptx10008_passive에 보관한다. 최초 원문은 변경하지 않았으며,
전체 엔진 Golden에만 사용자 확인에 따른 자동 Description 및 speed 명령을 반영했다.
예제에서 제공되지 않은 관리 IP/peer port는 테스트용 값임을 metadata와 예제 안내에 명시했다.
Single/CSV/XLSX의 동일 출력, 미확인 모델·OS 차단, IPv4/IPv6 선택, GUI 값 복원을 검증한다.
