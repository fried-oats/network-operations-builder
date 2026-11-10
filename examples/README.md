# API 전용 예제 프로젝트

ptx10008_golden.nobproj / ptx10008_passive.nobproj는 입력 형식 참고 예제입니다.
프로젝트를 연 뒤 파일 → API Inventory 불러오기를 실행하고 실제 API 장비를 선택하세요.
Inventory CSV는 사용하지 않습니다. 프로젝트는 API 출처를 참조합니다.

192.0.2.239/240은 테스트용 키이며 실제 관리 IP가 아닙니다. 테스트 대상이 API에 없다면
실제 API 장비로 target_management_ip를 변경하고 회선 입력값도 실제 작업에 맞춰 수정하세요.
passive_bulk.csv는 Bulk 입력용 CSV이며, 해당 파일의 대상 IP도 같은 방식으로 수정합니다.

Description 자동 조합, speed100g, RMON QDrop=8000+ifIndex / CRC=9000+ifIndex,
backbone/external CoS 및 IS-IS passive(metric0/ISO·MPLS·LDP 생략)를 시험할 수 있습니다.
모델/OS 지원 범위는 PTX10008 / 23.4R2-S1.6-EVO / et unit 0입니다.
예제 peer_interface et-0/0/1도 실제 사업자 포트가 아닌 예제 입력입니다.

정의 1.4.1: link_mode external은 no-flow-control을 FEC 앞에 생성합니다. backbone은 FEC만 생성합니다.
