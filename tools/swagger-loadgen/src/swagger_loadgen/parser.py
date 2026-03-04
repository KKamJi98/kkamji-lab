"""Parse OpenAPI 2.0/3.0 specs and extract GET endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml


@dataclass(frozen=True)
class SpecSource:
    """A named OpenAPI/Swagger specification source."""

    name: str
    url: str


@dataclass(frozen=True)
class Endpoint:
    """A single GET endpoint extracted from an OpenAPI spec."""

    path: str
    params: list[str] = field(default_factory=list)
    base_url: str = ""
    source_name: str = "default"
    spec_url: str = ""

    def resolve_url(self, param_values: dict[str, str] | None = None) -> str:
        """Build the full URL, substituting path parameters."""
        resolved = self.path
        for param in self.params:
            value = (param_values or {}).get(param, f"__{param}__")
            resolved = resolved.replace(f"{{{param}}}", value)
        return f"{self.base_url.rstrip('/')}{resolved}"


_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def fetch_document(url: str) -> Any:
    """Download and parse a JSON/YAML document from a URL."""
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "yaml" in content_type or url.endswith((".yaml", ".yml")):
        return yaml.safe_load(resp.text)

    try:
        return resp.json()
    except ValueError:
        return yaml.safe_load(resp.text)


def fetch_spec(url: str) -> dict[str, Any]:
    """Download and parse an OpenAPI spec from a URL (JSON or YAML)."""
    doc = fetch_document(url)
    if not isinstance(doc, dict):
        msg = f"Spec document must be a JSON/YAML object: {url}"
        raise TypeError(msg)
    return doc


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
    if not server_url:
        return ""

    parsed_server = urlparse(server_url)
    if parsed_server.scheme and parsed_server.netloc:
        return server_url

    if server_url.startswith("/"):
        parsed = urlparse(spec_url)
        return f"{parsed.scheme}://{parsed.netloc}{server_url}"
    return urljoin(spec_url, server_url)


def parse_spec(
    url: str,
    base_url_override: str | None = None,
    source_name: str = "default",
) -> list[Endpoint]:
    """Parse an OpenAPI spec and return all GET endpoints.

    Args:
        url: URL to the OpenAPI/Swagger JSON or YAML spec.
        base_url_override: If set, ignore the spec's server/host and use this instead.
        source_name: Logical source name for reporting.

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
        endpoints.append(
            Endpoint(
                path=path,
                params=params,
                base_url=base_url,
                source_name=source_name,
                spec_url=url,
            )
        )

    return endpoints


def parse_swagger_config(config_url: str) -> list[SpecSource]:
    """Parse a Swagger UI config endpoint and extract specification sources.

    Supported shapes:
    - ``{"urls": [{"name": "backend", "url": "/specs/backend.json"}]}``
    - ``{"url": "/openapi.json", "name": "default"}``
    """
    doc = fetch_document(config_url)
    if not isinstance(doc, dict):
        msg = f"Swagger config must be a JSON/YAML object: {config_url}"
        raise TypeError(msg)

    sources: list[SpecSource] = []
    urls = doc.get("urls")

    if isinstance(urls, list):
        for idx, item in enumerate(urls, start=1):
            if isinstance(item, str):
                sources.append(
                    SpecSource(
                        name=f"definition-{idx}",
                        url=urljoin(config_url, item),
                    )
                )
                continue
            if not isinstance(item, dict):
                continue
            raw_url = item.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            raw_name = item.get("name")
            name = (
                raw_name
                if isinstance(raw_name, str) and raw_name
                else f"definition-{idx}"
            )
            sources.append(SpecSource(name=name, url=urljoin(config_url, raw_url)))
    else:
        raw_url = doc.get("url")
        if isinstance(raw_url, str) and raw_url:
            raw_name = doc.get("name")
            name = raw_name if isinstance(raw_name, str) and raw_name else "default"
            sources.append(SpecSource(name=name, url=urljoin(config_url, raw_url)))

    if not sources:
        msg = f"No spec source found in swagger config: {config_url}"
        raise ValueError(msg)

    return sources
