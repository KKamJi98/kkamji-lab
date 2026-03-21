"""dns_monitor.config 단위 테스트."""

from __future__ import annotations

import pytest

from dns_monitor.config import ConfigSources, MonitorConfig, load_env_vars

# ---------------------------------------------------------------------------
# MonitorConfig 생성
# ---------------------------------------------------------------------------


def test_monitor_config_basic_creation():
    """필수 필드만으로 MonitorConfig를 생성할 수 있어야 한다."""
    cfg = MonitorConfig(
        endpoint="https://api.example.com",
        hosted_zone_id="Z1234567890ABC",
        record_name="api.example.com",
    )
    assert cfg.endpoint == "https://api.example.com"
    assert cfg.tps == 10  # 기본값
    assert cfg.http_enabled is True  # 기본값


def test_monitor_config_tps_below_minimum_raises():
    """TPS가 1 미만이면 ValueError가 발생해야 한다."""
    with pytest.raises(ValueError, match="TPS must be >= 1"):
        MonitorConfig(
            endpoint="https://api.example.com",
            hosted_zone_id="Z1234567890ABC",
            record_name="api.example.com",
            tps=0,
        )


def test_monitor_config_tps_above_maximum_raises():
    """TPS가 100 초과이면 ValueError가 발생해야 한다."""
    with pytest.raises(ValueError, match="TPS must be <= 100"):
        MonitorConfig(
            endpoint="https://api.example.com",
            hosted_zone_id="Z1234567890ABC",
            record_name="api.example.com",
            tps=101,
        )


def test_monitor_config_tps_boundary_values_valid():
    """TPS 경계값 1과 100은 유효해야 한다."""
    cfg_min = MonitorConfig(
        endpoint="https://a.example.com",
        hosted_zone_id="Z001",
        record_name="a.example.com",
        tps=1,
    )
    cfg_max = MonitorConfig(
        endpoint="https://a.example.com",
        hosted_zone_id="Z001",
        record_name="a.example.com",
        tps=100,
    )
    assert cfg_min.tps == 1
    assert cfg_max.tps == 100


# ---------------------------------------------------------------------------
# ConfigSources.build()
# ---------------------------------------------------------------------------


def test_config_sources_build_missing_endpoint_raises():
    """endpoint가 없으면 ValueError가 발생해야 한다."""
    sources = ConfigSources(cli={"hosted_zone_id": "Z001"})
    with pytest.raises(ValueError, match="endpoint is required"):
        sources.build()


def test_config_sources_build_missing_zone_id_raises():
    """hosted_zone_id가 없으면 ValueError가 발생해야 한다."""
    sources = ConfigSources(cli={"endpoint": "https://api.example.com"})
    with pytest.raises(ValueError, match="hosted_zone_id is required"):
        sources.build()


def test_config_sources_cli_overrides_toml():
    """CLI 값이 TOML 값보다 우선해야 한다."""
    sources = ConfigSources(
        toml={"endpoint": "https://toml.example.com", "hosted_zone_id": "Z_TOML"},
        cli={"endpoint": "https://cli.example.com", "hosted_zone_id": "Z_CLI"},
    )
    cfg = sources.build()
    assert cfg.endpoint == "https://cli.example.com"
    assert cfg.hosted_zone_id == "Z_CLI"


def test_config_sources_env_overrides_toml():
    """환경변수 값이 TOML 값보다 우선해야 한다."""
    sources = ConfigSources(
        toml={"endpoint": "https://toml.example.com", "hosted_zone_id": "Z_TOML"},
        env={"endpoint": "https://env.example.com", "hosted_zone_id": "Z_ENV"},
    )
    cfg = sources.build()
    assert cfg.endpoint == "https://env.example.com"


def test_config_sources_record_name_extracted_from_endpoint():
    """record_name이 없으면 endpoint URL에서 호스트명을 추출해야 한다."""
    sources = ConfigSources(
        cli={
            "endpoint": "https://api.example.com/path",
            "hosted_zone_id": "Z001",
        }
    )
    cfg = sources.build()
    assert cfg.record_name == "api.example.com"


# ---------------------------------------------------------------------------
# load_env_vars
# ---------------------------------------------------------------------------


def test_load_env_vars_reads_endpoint(monkeypatch):
    """DNSMON_ENDPOINT 환경변수가 endpoint로 매핑돼야 한다."""
    monkeypatch.setenv("DNSMON_ENDPOINT", "https://env.example.com")
    monkeypatch.delenv("DNSMON_HOSTED_ZONE_ID", raising=False)
    monkeypatch.delenv("DNSMON_RECORD_NAME", raising=False)
    monkeypatch.delenv("DNSMON_TPS", raising=False)
    monkeypatch.delenv("DNSMON_NO_HTTP", raising=False)

    result = load_env_vars()
    assert result["endpoint"] == "https://env.example.com"


def test_load_env_vars_tps_invalid_raises(monkeypatch):
    """DNSMON_TPS에 정수가 아닌 값이 들어오면 ValueError가 발생해야 한다."""
    monkeypatch.setenv("DNSMON_TPS", "not_a_number")

    with pytest.raises(ValueError, match="not a valid integer"):
        load_env_vars()


def test_load_env_vars_no_http_disables_http(monkeypatch):
    """DNSMON_NO_HTTP=true이면 http_enabled가 False여야 한다."""
    monkeypatch.setenv("DNSMON_NO_HTTP", "true")

    result = load_env_vars()
    assert result["http_enabled"] is False


def test_load_env_vars_no_http_false_enables_http(monkeypatch):
    """DNSMON_NO_HTTP=false이면 http_enabled가 True여야 한다."""
    monkeypatch.setenv("DNSMON_NO_HTTP", "false")

    result = load_env_vars()
    assert result["http_enabled"] is True
