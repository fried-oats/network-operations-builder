# GL-PO239 Golden 재현 예제

앱에서 `ptx10008_golden.nobproj`를 열고 검증/생성을 누르세요.
옆의 Inventory CSV는 프로젝트 상대경로로 읽습니다.

**192.0.2.239는 실제 관리 IP가 아닌 테스트용 키**입니다. 사용자가 관리 IP를 제공하지 않았으므로
장비 이름이나 인터페이스 IP를 관리 IP로 추정하지 않았습니다. 실제 작업에는 본인의 Inventory가 필요합니다.

Inventory의 os_version 자동 입력, Description 자동 조합, speed100g, RMON QDrop=8000+ifIndex/CRC=9000+ifIndex가 반영됩니다.
Backbone 또는 external CoS를 선택할 수 있습니다. ae 전체 생성은 추가 Golden이 필요합니다.
circuit_id / etc가 Link 입력에 추가되었고 RMON ID / platform / 수동 Description 입력은 제거했습니다.

## Passive 예제 (1.3.0)

ptx10008_passive.nobproj를 열거나, router_inventory.example.csv 로드 후 passive_bulk.csv를 가져오세요.
LA-POP239의 metric0/no-flow-control/ISO·MPLS·LDP 생략을 확인할 수 있습니다.
192.0.2.240과 peer_interface et-0/0/1은 테스트용 입력이며 실제 관리 IP/사업자 포트를 뜻하지 않습니다.
peer_name은 AS 괄호를 포함해 그대로 보존합니다. 기존 Description/speed 생성은 유지됩니다.
