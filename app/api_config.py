"""Local API connection configuration, independent of Qt and the config engine."""
from dataclasses import dataclass
from pathlib import Path
import sys
from urllib.parse import urlsplit


def application_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def validate_base_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("API_BASE_URL에 공백/제어 문자를 사용할 수 없습니다")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValueError("API_BASE_URL의 주소/포트가 올바르지 않습니다") from None
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment or "\\" in value):
        raise ValueError("API_BASE_URL은 인증정보/쿼리 없는 http 또는 https 주소여야 합니다")
    return value.rstrip("/")


@dataclass(frozen=True)
class ApiSettings:
    base_url: str
    timeout: float = 10.0

    def __post_init__(self):
        object.__setattr__(self, "base_url", validate_base_url(self.base_url))
        if not 0 < self.timeout <= 60:
            raise ValueError("API timeout은 0초 초과, 60초 이하여야 합니다")

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else application_directory() / "config" / ".env"
        if not path.is_file():
            raise ValueError(f"API 설정 파일이 없습니다: {path}\nconfig/.env.example을 .env로 복사하고 API_BASE_URL을 설정하세요.")
        if path.stat().st_size > 64 * 1024:
            raise ValueError("API 설정 파일 크기 제한 초과")
        url = None
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.strip().partition("=")
            if key.strip() != "API_BASE_URL" or not separator:
                continue
            if url is not None:
                raise ValueError("API_BASE_URL이 중복 정의되었습니다")
            value = value.strip()
            if value.startswith(('"', "'")):
                quote = value[0]
                end = value.find(quote, 1)
                if end < 0 or value[end + 1:].strip() and not value[end + 1:].strip().startswith("#"):
                    raise ValueError("API_BASE_URL의 인용부호가 올바르지 않습니다")
                value = value[1:end]
            else:
                value = value.split(" #", 1)[0].strip()
            url = value
        if not url:
            raise ValueError("config/.env에 API_BASE_URL을 입력하세요")
        return cls(url)
