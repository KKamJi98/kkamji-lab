"""YAML configuration loader for swagger-loadgen."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from swagger_loadgen.parser import Endpoint


@dataclass
class LoadgenConfig:
    """Runtime configuration loaded from a YAML file."""

    params: dict[str, str] = field(default_factory=dict)
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    def filter_endpoints(self, endpoints: list[Endpoint]) -> list[Endpoint]:
        """Apply include/exclude glob patterns to endpoint list."""
        result: list[Endpoint] = []
        for ep in endpoints:
            if self.include and not any(fnmatch(ep.path, p) for p in self.include):
                continue
            if self.exclude and any(fnmatch(ep.path, p) for p in self.exclude):
                continue
            result.append(ep)
        return result


def load_config(path: str | Path | None) -> LoadgenConfig:
    """Load a YAML config file. Returns default config when path is None."""
    if path is None:
        return LoadgenConfig()

    config_path = Path(path)
    if not config_path.is_file():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    raw: dict[str, Any] = yaml.safe_load(config_path.read_text()) or {}

    return LoadgenConfig(
        params=raw.get("params", {}),
        include=raw.get("include", []),
        exclude=raw.get("exclude", []),
        headers=raw.get("headers", {}),
    )
