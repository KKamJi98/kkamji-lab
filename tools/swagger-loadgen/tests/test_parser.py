from __future__ import annotations

import json

import httpx
import pytest

from swagger_loadgen import parser


def _json_response(url: str, payload: dict) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode(),
        request=request,
    )


def test_parse_swagger_config_resolves_relative_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_url = "https://example.com/docs/swagger-config"
    payload = {
        "urls": [
            {"name": "backend", "url": "/specs/backend.json"},
            {"name": "agent", "url": "specs/agent.json"},
        ]
    }

    def fake_get(url: str, follow_redirects: bool, timeout: int) -> httpx.Response:
        assert url == config_url
        assert follow_redirects is True
        assert timeout == 30
        return _json_response(url, payload)

    monkeypatch.setattr(parser.httpx, "get", fake_get)

    sources = parser.parse_swagger_config(config_url)

    assert len(sources) == 2
    assert sources[0].name == "backend"
    assert sources[0].url == "https://example.com/specs/backend.json"
    assert sources[1].name == "agent"
    assert sources[1].url == "https://example.com/docs/specs/agent.json"


def test_parse_swagger_config_supports_single_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_url = "https://example.com/swagger-config"
    payload = {"name": "backend", "url": "openapi.json"}

    def fake_get(url: str, follow_redirects: bool, timeout: int) -> httpx.Response:
        assert url == config_url
        assert follow_redirects is True
        assert timeout == 30
        return _json_response(url, payload)

    monkeypatch.setattr(parser.httpx, "get", fake_get)

    sources = parser.parse_swagger_config(config_url)

    assert len(sources) == 1
    assert sources[0].name == "backend"
    assert sources[0].url == "https://example.com/openapi.json"


def test_parse_spec_extracts_get_endpoints_with_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_url = "https://api.example.com/specs/backend.json"
    payload = {
        "openapi": "3.0.0",
        "servers": [{"url": "/api/v1"}],
        "paths": {
            "/ping": {"get": {}},
            "/users/{userId}": {"get": {}},
            "/items": {"post": {}},
        },
    }

    def fake_get(url: str, follow_redirects: bool, timeout: int) -> httpx.Response:
        assert url == spec_url
        assert follow_redirects is True
        assert timeout == 30
        return _json_response(url, payload)

    monkeypatch.setattr(parser.httpx, "get", fake_get)

    endpoints = parser.parse_spec(spec_url, source_name="backend")

    assert len(endpoints) == 2
    assert all(ep.source_name == "backend" for ep in endpoints)
    assert endpoints[0].base_url == "https://api.example.com/api/v1"
    assert endpoints[0].resolve_url() == "https://api.example.com/api/v1/ping"
    assert endpoints[1].params == ["userId"]
    assert (
        endpoints[1].resolve_url({"userId": "42"})
        == "https://api.example.com/api/v1/users/42"
    )


def test_parse_swagger_config_raises_when_no_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_url = "https://example.com/swagger-config"

    def fake_get(url: str, follow_redirects: bool, timeout: int) -> httpx.Response:
        assert url == config_url
        assert follow_redirects is True
        assert timeout == 30
        return _json_response(url, {"urls": []})

    monkeypatch.setattr(parser.httpx, "get", fake_get)

    with pytest.raises(ValueError, match="No spec source"):
        parser.parse_swagger_config(config_url)
