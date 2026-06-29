"""Read gcloud configurations, accounts, and ADC file locations."""

import os
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def gcloud_dir() -> Path:
    """Return the gcloud config dir, honoring CLOUDSDK_CONFIG."""
    env = os.environ.get("CLOUDSDK_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".config" / "gcloud"


@dataclass(frozen=True)
class GcloudConfig:
    """A gcloud named configuration (the 'profile' analog)."""

    name: str
    account: str
    project: str


def _read_account_project(cfg_path: Path) -> tuple[str, str]:
    parser = ConfigParser()
    try:
        parser.read(cfg_path, encoding="utf-8")
    except (OSError, ConfigParserError):
        return "", ""
    if not parser.has_section("core"):
        return "", ""
    account = parser.get("core", "account", fallback="") or ""
    project = parser.get("core", "project", fallback="") or ""
    return account.strip(), project.strip()


def list_configurations() -> list[GcloudConfig]:
    """List gcloud named configurations from configurations/config_*."""
    conf_dir = gcloud_dir() / "configurations"
    if not conf_dir.is_dir():
        return []
    prefix = "config_"
    out: list[GcloudConfig] = []
    for item in sorted(conf_dir.glob(f"{prefix}*")):
        if not item.is_file():
            continue
        name = item.name[len(prefix) :]
        account, project = _read_account_project(item)
        out.append(GcloudConfig(name=name, account=account, project=project))
    return out


def current_config() -> Optional[str]:
    """Return the active config name (env override, then active_config file)."""
    env = os.environ.get("CLOUDSDK_ACTIVE_CONFIG_NAME")
    if env:
        return env
    try:
        val = (gcloud_dir() / "active_config").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return val or None


def adc_dir() -> Path:
    """Directory holding per-account saved ADC files."""
    return gcloud_dir() / "adc"


def adc_path_for(account: str) -> Path:
    """Path to the saved ADC file for an account."""
    return adc_dir() / f"{account}.json"


def adc_exists(account: str) -> bool:
    """Whether a saved per-account ADC file exists."""
    return bool(account) and adc_path_for(account).is_file()
