"""Parse OpenAPI 2.0/3.0 specs and extract GET endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml


@dataclass(frozen=True)
class Endpoint:
    """A single GET endpoint extracted from an OpenAPI spec."""

    path: str
    params: list[str] = field(default_factory=list)
    base_url: str = ""

    def resolve_url(self, param_values: dict[str, str] | None = None) -> str:
        """Build the full URL, substituting path parameters."""
        resolved = self.path
        for param in self.params:
            value = (param_values or {}).get(param, f"__{param}__")
            resolved = resolved.replace(f"{{{param}}}", value)
        return f"{self.base_url.rstrip('/')}{resolved}"


_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def fetch_spec(url: str) -> dict[str, Any]:
    """Download and parse an OpenAPI spec from a URL (JSON or YAML)."""
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "yaml" in content_type or url.endswith((".yaml", ".yml")):
        return yaml.safe_load(resp.text)
    return resp.json()


def _extract_base_url_v2(spec: dict[str, Any]) -> str:
    """Extract base URL from OpenAPI 2.0 (Swagger) spec."""
    host = spec.get("host", "localhost")
    base_path = spec.get("basePath", "")
    schemes = spec.get("schemes", ["https"])
    scheme = schemes[0] if schemes else "https"
    return f"{scheme}://{host}{base_path}"


def _extract_base_url_v3(spec: dict[str, Any], spec_url: str) -> str:
    """Extract base URL from OpenAPI 3.0 spec.

    Handles relative server URLs (e.g. ``/api/v3``) by resolving them
    against the origin of the spec URL.
    """
    servers = spec.get("servers", [])
    if not servers:
        return ""
    server_url = servers[0].get("url", "")
    if server_url.startswith("/"):
        parsed = urlparse(spec_url)
        return f"{parsed.scheme}://{parsed.netloc}{server_url}"
    return server_url


def parse_spec(url: str, base_url_override: str | None = None) -> list[Endpoint]:
    """Parse an OpenAPI spec and return all GET endpoints.

    Args:
        url: URL to the OpenAPI/Swagger JSON or YAML spec.
        base_url_override: If set, ignore the spec's server/host and use this instead.

    Returns:
        List of Endpoint objects for every GET operation found.
    """
    spec = fetch_spec(url)

    # Detect version
    if spec.get("swagger", "").startswith("2"):
        base_url = _extract_base_url_v2(spec)
    else:
        base_url = _extract_base_url_v3(spec, url)

    if base_url_override:
        base_url = base_url_override

    endpoints: list[Endpoint] = []
    paths: dict[str, Any] = spec.get("paths", {})

    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        if "get" not in methods:
            continue

        params = _PATH_PARAM_RE.findall(path)
        endpoints.append(Endpoint(path=path, params=params, base_url=base_url))

    return endpoints
