"""Read-only router API client. Only authentication and GET /router/ are exposed."""
from ipaddress import ip_address
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from app.api_config import ApiSettings
from .normalization import inventory_record

API_INVENTORY_SOURCE = "api:/router/"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_ROUTERS = 100000


class ApiError(ValueError):
    pass


class ApiHttpError(ApiError):
    def __init__(self, status):
        self.status = status
        messages = {401: "인증이 필요하거나 만료되었습니다. API ID/비밀번호를 확인하세요.",
                    403: "라우터 조회 권한이 없습니다.", 422: "API 요청 형식이 서버 명세와 맞지 않습니다."}
        super().__init__(messages.get(status, f"API 요청 실패 (HTTP {status}). 서버 상태를 확인하세요."))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ApiClient:
    def __init__(self, settings: ApiSettings, opener=None):
        self.settings = settings
        self.opener = opener or build_opener(ProxyHandler({}), NoRedirect())
        self._access_token = ""
        self._refresh_token = ""

    def _request(self, method, path, payload=None, authenticated=False):
        headers = {"Accept": "application/json"}
        if authenticated and self._access_token:
            headers["Authorization"] = "Bearer " + self._access_token
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.settings.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.settings.timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ApiError("API 응답 크기 제한(20MB)을 초과했습니다")
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise ApiHttpError(status) from None
        except (TimeoutError, socket.timeout):
            raise ApiError("API 응답 시간이 초과되었습니다. 서버 주소와 연결 상태를 확인하세요.") from None
        except (URLError, OSError):
            raise ApiError("API 서버에 연결할 수 없습니다. API_BASE_URL과 네트워크 상태를 확인하세요.") from None
        try:
            return json.loads(body.decode("utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (UnicodeError, ValueError):
            raise ApiError("API 응답이 올바른 JSON이 아닙니다") from None

    def _set_tokens(self, payload):
        kind = payload.get("token_type", "bearer") if isinstance(payload, dict) else None
        if not isinstance(kind, str) or kind.lower() != "bearer":
            raise ApiError("API 인증 응답 형식이 올바르지 않습니다")
        tokens = [payload.get("access_token"), payload.get("refresh_token")]
        if any(not isinstance(t, str) or not t or len(t) > 8192 or any(not 33 <= ord(c) <= 126 for c in t) for t in tokens):
            raise ApiError("API 인증 응답에 유효한 토큰이 없습니다")
        self._access_token, self._refresh_token = tokens

    def login(self, user_id, password):
        if not isinstance(user_id, str) or not isinstance(password, str) or not user_id.strip() or not password:
            raise ApiError("API ID와 비밀번호를 모두 입력하세요")
        self._set_tokens(self._request("POST", "/token", {"id": user_id.strip(), "pw": password}))

    def routers(self):
        try:
            return self._request("GET", "/router/", authenticated=True)
        except ApiHttpError as exc:
            if exc.status != 401 or not self._refresh_token:
                raise
        self._set_tokens(self._request("POST", "/token/refresh", {"refresh_token": self._refresh_token}))
        return self._request("GET", "/router/", authenticated=True)

    def clear_tokens(self):
        self._access_token = self._refresh_token = ""


class ApiInventoryRepository:
    def __init__(self, client):
        self.client = client

    def load(self, source=None):
        rows = self.client.routers()
        if not isinstance(rows, list) or len(rows) > MAX_ROUTERS:
            raise ApiError("GET /router/ 응답은 라우터 목록이어야 하며 100000개 이하여야 합니다")
        records = {}
        names = ("name", "hierarchy", "group", "location", "operation_team", "manufacturer", "model")
        for number, row in enumerate(rows, 1):
            try:
                if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in names):
                    raise ValueError()
                integer = row.get("ipaddr")
                if type(integer) is not int or not 0 <= integer < 2 ** 128:
                    raise ValueError()
                text = row.get("ipstr", "")
                if not isinstance(text, str):
                    raise ValueError()
                address = ip_address(text.strip()) if text.strip() else ip_address(integer)
                if int(address) != integer:
                    raise ValueError()
                version = row.get("os_version")
                if version is None:
                    version = ""
                if not isinstance(version, str) or len(version) > 64:
                    raise ValueError()
                record = inventory_record(str(address), *(row[k] for k in names), os_version=version)
            except ValueError:
                raise ApiError(f"API 라우터 {number}번째 항목: 필수 필드/관리 IP/ipstr·ipaddr 일치 여부를 확인하세요.") from None
            if record.management_ip in records:
                raise ApiError(f"API 라우터 {number}번째 항목: 중복 management_ip {record.management_ip}")
            records[record.management_ip] = record
        return records


def fetch_api_inventory(settings, user_id="", password=""):
    client = ApiClient(settings)
    try:
        if user_id or password:
            client.login(user_id, password)
        return ApiInventoryRepository(client).load()
    finally:
        client.clear_tokens()
