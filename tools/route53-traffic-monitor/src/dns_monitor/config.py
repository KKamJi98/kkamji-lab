"""설정 로딩 모듈.

우선순위: CLI args → 환경변수 → .env → config.toml → defaults
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass
class MonitorConfig:
    """모니터링 설정."""

    endpoint: str
    hosted_zone_id: str
    record_name: str
    tps: int = 10
    http_enabled: bool = True

    def __post_init__(self):
        if self.tps < 1:
            raise ValueError("TPS must be >= 1")
        if self.tps > 100:
            raise ValueError("TPS must be <= 100")


@dataclass
class ConfigSources:
    """설정 소스별 값을 수집 후 병합."""

    cli: dict[str, object] = field(default_factory=dict)
    env: dict[str, object] = field(default_factory=dict)
    toml: dict[str, object] = field(default_factory=dict)

    def _merged(self) -> dict[str, object]:
        """CLI > env > toml 순서로 병합."""
        merged: dict[str, object] = {}
        merged.update(self.toml)
        merged.update(self.env)
        merged.update(self.cli)
        return merged

    def build(self) -> MonitorConfig:
        m = self._merged()
        endpoint = m.get("endpoint")
        if not endpoint:
            raise ValueError("endpoint is required (--endpoint or DNSMON_ENDPOINT)")
        hosted_zone_id = m.get("hosted_zone_id")
        if not hosted_zone_id:
            raise ValueError("hosted_zone_id is required (--zone-id or DNSMON_HOSTED_ZONE_ID)")

        record_name = m.get("record_name") or _extract_host(str(endpoint))

        return MonitorConfig(
            endpoint=str(endpoint),
            hosted_zone_id=str(hosted_zone_id),
            record_name=record_name,
            tps=int(m.get("tps", 10)),
            http_enabled=bool(m.get("http_enabled", True)),
        )


def load_env_vars() -> dict[str, object]:
    """환경변수에서 설정을 읽는다."""
    result: dict[str, object] = {}
    mapping = {
        "DNSMON_ENDPOINT": "endpoint",
        "DNSMON_HOSTED_ZONE_ID": "hosted_zone_id",
        "DNSMON_RECORD_NAME": "record_name",
        "DNSMON_TPS": "tps",
        "DNSMON_NO_HTTP": "no_http",
    }
    for env_key, config_key in mapping.items():
        val = os.environ.get(env_key)
        if val is not None:
            if config_key == "tps":
                result[config_key] = int(val)
            elif config_key == "no_http":
                result["http_enabled"] = val.lower() not in ("true", "1", "yes")
            else:
                result[config_key] = val
    return result


def load_toml_file(path: Path) -> dict[str, object]:
    """TOML 설정 파일을 읽는다."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    section = data.get("dnsmon", data)
    result: dict[str, object] = {}
    key_map = {
        "endpoint": "endpoint",
        "hosted_zone_id": "hosted_zone_id",
        "record_name": "record_name",
        "tps": "tps",
        "no_http": "no_http",
        "http_enabled": "http_enabled",
    }
    for toml_key, config_key in key_map.items():
        if toml_key in section:
            val = section[toml_key]
            if toml_key == "no_http":
                result["http_enabled"] = not bool(val)
            else:
                result[config_key] = val
    return result


def build_config(
    *,
    endpoint: str | None = None,
    zone_id: str | None = None,
    record_name: str | None = None,
    tps: int | None = None,
    no_http: bool = False,
    config_file: Path | None = None,
    env_file: Path | None = None,
) -> MonitorConfig:
    """모든 소스에서 설정을 로딩하고 병합한다."""
    # .env 로딩
    if env_file and env_file.exists():
        load_dotenv(env_file)
    elif Path(".env").exists():
        load_dotenv(Path(".env"))

    sources = ConfigSources()

    # TOML
    toml_path = config_file or Path("dnsmon.toml")
    sources.toml = load_toml_file(toml_path)

    # 환경변수
    sources.env = load_env_vars()

    # CLI args (None이 아닌 것만)
    cli: dict[str, object] = {}
    if endpoint is not None:
        cli["endpoint"] = endpoint
    if zone_id is not None:
        cli["hosted_zone_id"] = zone_id
    if record_name is not None:
        cli["record_name"] = record_name
    if tps is not None:
        cli["tps"] = tps
    if no_http:
        cli["http_enabled"] = False
    sources.cli = cli

    return sources.build()


def _extract_host(url: str) -> str:
    """URL에서 호스트명을 추출한다."""
    parsed = urlparse(url)
    host = parsed.hostname or parsed.path
    return host.rstrip(".")
