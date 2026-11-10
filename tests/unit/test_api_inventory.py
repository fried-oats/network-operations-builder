import io
import json
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
import pytest
from app.api_config import ApiSettings
from app.inventory.api_repository import ApiClient, ApiError, ApiInventoryRepository, NoRedirect


def router(ip="192.0.2.10", **updates):
    row = dict(ipaddr=int(ip_address(ip)), ipstr=ip, name="TEST-PTX", hierarchy="Core", group="LAB", location="TEST",
               operation_team="NOC", manufacturer="Juniper Networks", model="ptx10008", os_version="23.4R2-S1.6-EVO")
    return {**row, **updates}


class Opener:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply if isinstance(reply, bytes) else json.dumps(reply).encode())


def client(replies):
    opener = Opener(replies)
    return ApiClient(ApiSettings("http://127.0.0.1:8000/api/"), opener), opener


def test_anonymous_load_normalizes_inventory_and_reads_only():
    api, opener = client([[router()]])
    result = ApiInventoryRepository(api).load()
    record = result["192.0.2.10"]
    assert (record.manufacturer, record.model, record.os_family, record.os_version) == ("Juniper", "PTX10008", "Junos", "23.4R2-S1.6-EVO")
    request, timeout = opener.calls[0]
    assert request.full_url == "http://127.0.0.1:8000/api/router/"
    assert request.method == "GET" and request.get_header("Authorization") is None
    assert timeout == 10


def test_login_json_bearer_refresh_once():
    denied = HTTPError("http://test/router/", 401, "denied", {}, io.BytesIO(b"secret echoed by server"))
    api, opener = client([
        {"access_token": "old-access", "refresh_token": "old-refresh"}, denied,
        {"access_token": "new-access", "refresh_token": "new-refresh", "token_type": "bearer"}, [router()],
    ])
    api.login("viewer", "test-password")
    assert ApiInventoryRepository(api).load()["192.0.2.10"].name == "TEST-PTX"
    assert [req.method for req, _ in opener.calls] == ["POST", "GET", "POST", "GET"]
    assert [req.full_url.rsplit("/api", 1)[1] for req, _ in opener.calls] == ["/token", "/router/", "/token/refresh", "/router/"]
    assert json.loads(opener.calls[0][0].data) == {"id": "viewer", "pw": "test-password"}
    assert opener.calls[1][0].get_header("Authorization") == "Bearer old-access"
    assert opener.calls[3][0].get_header("Authorization") == "Bearer new-access"
    api.clear_tokens()
    assert api._access_token == api._refresh_token == ""


def test_refresh_has_no_retry_loop():
    def denied():
        return HTTPError("http://test/router/", 401, "denied", {}, None)
    api, opener = client([{"access_token": "a", "refresh_token": "r"}, denied(), {"access_token": "b", "refresh_token": "s"}, denied()])
    api.login("test", "test")
    with pytest.raises(ApiError):
        api.routers()
    assert len(opener.calls) == 4


@pytest.mark.parametrize("reply", [URLError("secret URL/user"), TimeoutError("secret URL/user"),
    HTTPError("http://test/secret", 403, "secret", {}, io.BytesIO(b"secret password")), b"not JSON", b'{"a":NaN}'])
def test_transport_errors_are_sanitized(reply):
    api, _ = client([reply])
    with pytest.raises(ApiError) as error:
        api.routers()
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("tokens", [None, [], {}, {"token_type": None}, {"token_type": []},
    {"access_token": "a\r\nInjected: yes", "refresh_token": "r"}, {"access_token": "토큰", "refresh_token": "r"}, {"access_token": "a", "refresh_token": ""}])
def test_bad_token_response_is_rejected(tokens):
    api, _ = client([tokens])
    with pytest.raises(ApiError):
        api.login("test", "test")


@pytest.mark.parametrize("changes", [{"ipaddr": True}, {"ipaddr": -1}, {"ipaddr": 2**128}, {"ipstr": "bad"},
    {"ipstr": "192.0.2.99"}, {"ipaddr": "3221225994"}, {"name": ""}, {"model": None}, {"os_version": 42}])
def test_bad_router_rejected(changes):
    api, _ = client([[router(**changes)]])
    with pytest.raises(ApiError):
        ApiInventoryRepository(api).load()


def test_null_os_and_integer_ip_fallback():
    api, _ = client([[router(ipstr="", os_version=None, manufacturer="Unknown", model="M")]])
    record = ApiInventoryRepository(api).load()["192.0.2.10"]
    assert record.os_family == record.os_version == ""


def test_ipv6_duplicate_canonical_ip_blocks_whole_load():
    api, _ = client([[router("2001:db8::1"), router("2001:0db8::1")]])
    with pytest.raises(ApiError, match="중복"):
        ApiInventoryRepository(api).load()


def test_non_array_and_oversized_response(monkeypatch):
    import app.inventory.api_repository as module
    api, _ = client([{"routers": []}])
    with pytest.raises(ApiError):
        ApiInventoryRepository(api).load()
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 64)
    api, _ = client([b" " * 65])
    with pytest.raises(ApiError, match="크기"):
        api.routers()
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "http://other/") is None


@pytest.mark.parametrize("value", ["https://host", '"http://192.168.0.53:8000"', "'http://host/api/' # comment"])
def test_env_config(tmp_path, value):
    env = tmp_path / ".env"
    env.write_text("# settings\nAPI_BASE_URL=" + value + "\n", encoding="utf-8-sig")
    assert ApiSettings.load(env).base_url.startswith(("http://", "https://"))


@pytest.mark.parametrize("value", ["", "ftp://host", "http://user:pass@host", "http://host?key=secret", "http://host/#part", "http://host:bad", "http://host /x"])
def test_bad_base_url(value):
    with pytest.raises(ValueError):
        ApiSettings(value)


def test_env_missing_duplicate_or_malformed(tmp_path):
    path = tmp_path / ".env"
    for text in ["# missing", 'API_BASE_URL="http://host', "API_BASE_URL=http://host\nAPI_BASE_URL=http://host"]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            ApiSettings.load(path)
