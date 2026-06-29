"""Read gcloud configurations, accounts, and ADC file locations."""

import json
import os
import subprocess
import urllib.parse
import urllib.request
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


def _adc_type_and_email(adc_file: Path) -> tuple[str, str]:
    try:
        data = json.loads(adc_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    return data.get("type", ""), data.get("client_email", "")


def _print_adc_access_token() -> str:
    """Mint an ADC access token via gcloud (network). Empty string on failure."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _tokeninfo_email(token: str) -> str:
    """Resolve the account email for an access token via Google tokeninfo (network)."""
    url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode(
        {"access_token": token}
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    if not isinstance(data, dict):
        return ""
    return data.get("email", "") or ""


def resolve_adc_account(adc_file: Optional[Path] = None) -> Optional[str]:
    """Resolve which account an ADC credential belongs to.

    service_account -> client_email (no network).
    authorized_user/other -> token introspection (network).
    Returns None if the file is missing or the account cannot be determined.
    """
    if adc_file is None:
        adc_file = gcloud_dir() / "application_default_credentials.json"
    if not adc_file.is_file():
        return None
    adc_type, email = _adc_type_and_email(adc_file)
    if adc_type == "service_account":
        return email or None
    token = _print_adc_access_token()
    if not token:
        return None
    return _tokeninfo_email(token) or None
