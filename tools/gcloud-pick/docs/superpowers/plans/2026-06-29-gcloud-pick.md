# gcloud-pick (gp) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `gcloud-pick`, a Python uv CLI (`gp` wrapper) that switches the gcloud CLI auth (active configuration) and ADC (Application Default Credentials) identity together, per-shell and synced across panes.

**Architecture:** A flat `gcloud_pick` package (mirrors `kube-pick`) with `config.py` (read gcloud configurations + accounts + ADC files), `shell.py` (generate `export`/`unset` lines + write a shared profile file; never edits rc), and `cli.py` (rich-based picker + orchestration + `--login`). A shell wrapper `gp()` evals the printed exports; a `gcloudpick_sync` precmd re-applies the shared profile in every shell. The starship `custom.gcloud_adc` warning (already shipped) is the drift safety net.

**Tech Stack:** Python 3.9+, uv + hatchling + ruff, `rich` for display, stdlib `configparser`/`json`/`urllib`/`subprocess`. Tests with pytest.

## Global Constraints

- Python: `requires-python = ">=3.9"`.
- Dependencies: runtime `rich>=13.0.0,<14.0.0` only; everything else stdlib. Dev: `pytest>=8.0.0`, `ruff>=0.8.0`.
- Build backend: `hatchling`. Entry point: `gcloud-pick = "gcloud_pick.cli:main"`.
- Naming: package `gcloud_pick`, command `gcloud-pick`, shell wrapper `gp`. Version `1.0.0`.
- Output discipline: ALL human-facing output (lists, prompts, warnings, status) goes to stderr (`rich.Console(stderr=True)`); ONLY `export`/`unset` lines go to stdout (`print()`).
- Platform: macOS (darwin) primary; bash/zsh/fish export syntax supported.
- Secrets: never print token/credential contents. ADC files saved with mode `0600`, parent dir `0700`.
- Typography: ASCII only in all files (no em/en dash, smart quotes, ellipsis).
- Commits: Conventional Commits. `git add` ONLY `tools/gcloud-pick/...` paths (the monorepo has unrelated `git-worktree-tool` WIP that must not be swept in). The shell-glue task edits live `$HOME` dotfiles (not tracked here) - no commit there.
- Switch emits exactly: `CLOUDSDK_ACTIVE_CONFIG_NAME=<config>` and either `GOOGLE_APPLICATION_CREDENTIALS=<adc-path>` (when the per-account ADC file exists) or `unset GOOGLE_APPLICATION_CREDENTIALS` (when it does not).
- Shared profile file: `~/.config/gcloudpick/profile`, two lines: line1 = config name, line2 = ADC path or empty.

---

### Task 1: Project scaffold + version baseline

**Files:**
- Create: `tools/gcloud-pick/pyproject.toml`
- Create: `tools/gcloud-pick/gcloud_pick/__init__.py`
- Create: `tools/gcloud-pick/gcloud_pick/cli.py`
- Create: `tools/gcloud-pick/tests/__init__.py`
- Create: `tools/gcloud-pick/tests/conftest.py`
- Create: `tools/gcloud-pick/tests/test_cli.py`

**Interfaces:**
- Produces: `gcloud_pick.__version__` (str); `gcloud_pick.cli.parse_args(argv) -> argparse.Namespace`; `gcloud_pick.cli.main(argv=None) -> int`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "gcloud-pick"
version = "1.0.0"
description = "A simple CLI tool to switch gcloud CLI auth and ADC together in your shell environment"
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "kkamji", email = "rlaxowl5460@gmail.com" }]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Utilities",
]
requires-python = ">=3.9"
dependencies = ["rich>=13.0.0,<14.0.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "ruff>=0.8.0"]

[project.scripts]
gcloud-pick = "gcloud_pick.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

- [ ] **Step 2: Write `gcloud_pick/__init__.py`**

```python
"""gcloud-pick: switch gcloud CLI auth and ADC together."""

__version__ = "1.0.0"
```

- [ ] **Step 3: Write a minimal `gcloud_pick/cli.py`**

```python
"""Command-line interface for gcloud-pick."""

import argparse
import logging
import sys
from typing import Optional

from rich.console import Console

from gcloud_pick import __version__

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

console = Console(stderr=True)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gcloud-pick",
        description="gcloud-pick - switch gcloud CLI auth and ADC together",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help="Configuration to switch to (skips the interactive picker)",
    )
    parser.add_argument(
        "--login",
        nargs="?",
        const="",
        default=None,
        metavar="CONFIG",
        help="Run ADC login and save a per-account ADC file (optionally verify against CONFIG)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    try:
        parse_args(argv)
        console.print("[yellow]gcloud-pick: not implemented yet[/yellow]")
        return 0
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `tests/__init__.py` (empty) and `tests/conftest.py`**

```python
# tests/conftest.py
"""Shared pytest fixtures for gcloud-pick tests."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_gcloud_home(tmp_path, monkeypatch):
    """Point CLOUDSDK_CONFIG and HOME at a temp dir; return the gcloud dir."""
    home = tmp_path / "home"
    home.mkdir()
    gcloud = home / ".config" / "gcloud"
    (gcloud / "configurations").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(gcloud))
    monkeypatch.delenv("CLOUDSDK_ACTIVE_CONFIG_NAME", raising=False)
    monkeypatch.delenv("CLOUDSDK_CORE_ACCOUNT", raising=False)
    return gcloud


def write_config(gcloud_dir: Path, name: str, account: str = "", project: str = "") -> None:
    """Write a configurations/config_<name> INI file."""
    lines = ["[core]"]
    if account:
        lines.append(f"account = {account}")
    if project:
        lines.append(f"project = {project}")
    (gcloud_dir / "configurations" / f"config_{name}").write_text("\n".join(lines) + "\n")


def set_active(gcloud_dir: Path, name: str) -> None:
    (gcloud_dir / "active_config").write_text(name + "\n")
```

- [ ] **Step 5: Write the failing test `tests/test_cli.py`**

```python
import pytest

from gcloud_pick.cli import parse_args


def test_parse_args_positional_config():
    args = parse_args(["infra"])
    assert args.config == "infra"
    assert args.login is None


def test_parse_args_login_without_value():
    args = parse_args(["--login"])
    assert args.login == ""


def test_parse_args_login_with_config():
    args = parse_args(["--login", "infra"])
    assert args.login == "infra"


def test_version_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "1.0.0" in out
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/code/code-personal/kkamji-lab/tools/gcloud-pick && uv sync && uv run pytest -v`
Expected: 4 passed.

- [ ] **Step 7: Lint/format**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: no errors. (If format reports diffs, run `uv run ruff format .` then re-check.)

- [ ] **Step 8: Commit**

```bash
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/pyproject.toml tools/gcloud-pick/gcloud_pick tools/gcloud-pick/tests tools/gcloud-pick/docs
git commit -m "feat(gcloud-pick): scaffold package, CLI arg parsing, version"
```

---

### Task 2: config.py - configuration discovery

**Files:**
- Create: `tools/gcloud-pick/gcloud_pick/config.py`
- Test: `tools/gcloud-pick/tests/test_config.py`

**Interfaces:**
- Produces:
  - `GcloudConfig` dataclass: `name: str`, `account: str`, `project: str` (frozen).
  - `gcloud_dir() -> Path`
  - `list_configurations() -> list[GcloudConfig]` (sorted by name)
  - `current_config() -> Optional[str]`
  - `adc_dir() -> Path`, `adc_path_for(account: str) -> Path`, `adc_exists(account: str) -> bool`

- [ ] **Step 1: Write failing tests in `tests/test_config.py`**

```python
from gcloud_pick.config import (
    GcloudConfig,
    adc_exists,
    adc_path_for,
    current_config,
    gcloud_dir,
    list_configurations,
)
from tests.conftest import set_active, write_config


def test_gcloud_dir_respects_cloudsdk_config(fake_gcloud_home):
    assert gcloud_dir() == fake_gcloud_home


def test_list_configurations_parses_account_project(fake_gcloud_home):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr", project="my-proj")
    configs = list_configurations()
    assert configs == [
        GcloudConfig(name="default", account="ethan.kim@bunjang.co.kr", project=""),
        GcloudConfig(name="infra", account="infra@bunjang.co.kr", project="my-proj"),
    ]


def test_list_configurations_empty_when_none(fake_gcloud_home):
    assert list_configurations() == []


def test_current_config_prefers_env(fake_gcloud_home, monkeypatch):
    set_active(fake_gcloud_home, "infra")
    monkeypatch.setenv("CLOUDSDK_ACTIVE_CONFIG_NAME", "default")
    assert current_config() == "default"


def test_current_config_falls_back_to_active_file(fake_gcloud_home):
    set_active(fake_gcloud_home, "infra")
    assert current_config() == "infra"


def test_adc_path_and_exists(fake_gcloud_home):
    acct = "infra@bunjang.co.kr"
    assert adc_exists(acct) is False
    p = adc_path_for(acct)
    assert p == fake_gcloud_home / "adc" / f"{acct}.json"
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    assert adc_exists(acct) is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (ImportError: cannot import name from gcloud_pick.config).

- [ ] **Step 3: Write `gcloud_pick/config.py`**

```python
"""Read gcloud configurations, accounts, and ADC file locations."""

import os
from configparser import ConfigParser, Error as ConfigParserError
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
        name = item.name[len(prefix):]
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/config.py tools/gcloud-pick/tests/test_config.py
git commit -m "feat(gcloud-pick): read gcloud configurations and ADC file paths"
```

---

### Task 3: config.py - ADC account resolution

**Files:**
- Modify: `tools/gcloud-pick/gcloud_pick/config.py` (append functions)
- Test: `tools/gcloud-pick/tests/test_config.py` (append)

**Interfaces:**
- Consumes: `gcloud_dir()` from Task 2.
- Produces:
  - `_print_adc_access_token() -> str` (network; mocked in tests)
  - `_tokeninfo_email(token: str) -> str` (network; mocked in tests)
  - `resolve_adc_account(adc_file: Optional[Path] = None) -> Optional[str]`
    - `service_account` JSON -> `client_email` (no network)
    - `authorized_user`/other -> token introspection

- [ ] **Step 1: Write failing tests (append to `tests/test_config.py`)**

```python
import json

from gcloud_pick import config as cfgmod
from gcloud_pick.config import resolve_adc_account


def test_resolve_service_account_uses_client_email(fake_gcloud_home, tmp_path):
    adc = tmp_path / "sa.json"
    adc.write_text(json.dumps({"type": "service_account", "client_email": "svc@p.iam.gserviceaccount.com"}))
    assert resolve_adc_account(adc) == "svc@p.iam.gserviceaccount.com"


def test_resolve_user_cred_uses_token_introspection(fake_gcloud_home, tmp_path, monkeypatch):
    adc = tmp_path / "user.json"
    adc.write_text(json.dumps({"type": "authorized_user", "refresh_token": "x"}))
    monkeypatch.setattr(cfgmod, "_print_adc_access_token", lambda: "tok123")
    monkeypatch.setattr(cfgmod, "_tokeninfo_email", lambda token: "ethan.kim@bunjang.co.kr")
    assert resolve_adc_account(adc) == "ethan.kim@bunjang.co.kr"


def test_resolve_returns_none_when_token_fails(fake_gcloud_home, tmp_path, monkeypatch):
    adc = tmp_path / "user.json"
    adc.write_text(json.dumps({"type": "authorized_user"}))
    monkeypatch.setattr(cfgmod, "_print_adc_access_token", lambda: "")
    assert resolve_adc_account(adc) is None


def test_resolve_returns_none_when_file_missing(fake_gcloud_home, tmp_path):
    assert resolve_adc_account(tmp_path / "nope.json") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_config.py -k resolve -v`
Expected: FAIL (cannot import name 'resolve_adc_account').

- [ ] **Step 3: Append to `gcloud_pick/config.py`**

Add these imports at the top of the file (merge with existing import block):

```python
import json
import subprocess
import urllib.parse
import urllib.request
```

Append these functions:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 10 passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/config.py tools/gcloud-pick/tests/test_config.py
git commit -m "feat(gcloud-pick): resolve ADC account (SA email or token introspection)"
```

---

### Task 4: shell.py - export/unset command generation

**Files:**
- Create: `tools/gcloud-pick/gcloud_pick/shell.py`
- Test: `tools/gcloud-pick/tests/test_shell.py`

**Interfaces:**
- Produces:
  - `detect_shell() -> str`
  - `normalize_shell(name: str) -> str` (returns one of "bash", "zsh", "fish")
  - `generate_export_commands(config_name: str, adc_path: Optional[Path], shell_name: Optional[str] = None) -> str`

- [ ] **Step 1: Write failing tests in `tests/test_shell.py`**

```python
from pathlib import Path

from gcloud_pick.shell import generate_export_commands, normalize_shell


def test_normalize_shell():
    assert normalize_shell("/bin/zsh") == "zsh"
    assert normalize_shell("bash") == "bash"
    assert normalize_shell("fish") == "fish"
    assert normalize_shell("dash") == "zsh"  # fallback


def test_export_with_adc_zsh():
    out = generate_export_commands("infra", Path("/h/.config/gcloud/adc/infra@x.json"), "zsh")
    assert out == (
        'export CLOUDSDK_ACTIVE_CONFIG_NAME="infra"\n'
        'export GOOGLE_APPLICATION_CREDENTIALS="/h/.config/gcloud/adc/infra@x.json"'
    )


def test_export_without_adc_unsets_zsh():
    out = generate_export_commands("default", None, "zsh")
    assert out == (
        'export CLOUDSDK_ACTIVE_CONFIG_NAME="default"\n'
        "unset GOOGLE_APPLICATION_CREDENTIALS"
    )


def test_export_fish_syntax():
    out = generate_export_commands("infra", None, "fish")
    assert out == (
        'set -gx CLOUDSDK_ACTIVE_CONFIG_NAME "infra"\n'
        "set -e GOOGLE_APPLICATION_CREDENTIALS"
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_shell.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Write `gcloud_pick/shell.py` (this part)**

```python
"""Generate shell export/unset commands and manage the shared profile file."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUPPORTED = ("bash", "zsh", "fish")


def detect_shell() -> str:
    """Detect the current shell name."""
    shell_path = os.environ.get("SHELL", "")
    if shell_path:
        return os.path.basename(shell_path)
    try:
        result = subprocess.run(
            ["ps", "-p", str(os.getppid()), "-o", "comm="],
            capture_output=True,
            text=True,
            check=True,
        )
        name = result.stdout.strip()
        return os.path.basename(name) if "/" in name else name
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to detect shell: %s", e)
        return "zsh"


def normalize_shell(name: str) -> str:
    """Map a detected shell name to a supported one (default zsh)."""
    base = os.path.basename(name).lower()
    for supported in _SUPPORTED:
        if base.startswith(supported):
            return supported
    return "zsh"


def _export_line(shell: str, var: str, value: str) -> str:
    if shell == "fish":
        return f'set -gx {var} "{value}"'
    return f'export {var}="{value}"'


def _unset_line(shell: str, var: str) -> str:
    if shell == "fish":
        return f"set -e {var}"
    return f"unset {var}"


def generate_export_commands(
    config_name: str, adc_path: Optional[Path], shell_name: Optional[str] = None
) -> str:
    """Return the export/unset lines to switch CLI config and ADC."""
    shell = normalize_shell(shell_name or detect_shell())
    lines = [_export_line(shell, "CLOUDSDK_ACTIVE_CONFIG_NAME", config_name)]
    if adc_path is not None:
        lines.append(_export_line(shell, "GOOGLE_APPLICATION_CREDENTIALS", str(adc_path)))
    else:
        lines.append(_unset_line(shell, "GOOGLE_APPLICATION_CREDENTIALS"))
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_shell.py -v`
Expected: 4 passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/shell.py tools/gcloud-pick/tests/test_shell.py
git commit -m "feat(gcloud-pick): generate shell export/unset commands"
```

---

### Task 5: shell.py - shared profile read/write

**Files:**
- Modify: `tools/gcloud-pick/gcloud_pick/shell.py` (append)
- Test: `tools/gcloud-pick/tests/test_shell.py` (append)

**Interfaces:**
- Produces:
  - `shared_profile_path() -> Path` (`~/.config/gcloudpick/profile`)
  - `write_shared_profile(config_name: str, adc_path: Optional[Path]) -> Path` (atomic)
  - `read_shared_profile() -> tuple[Optional[str], Optional[str]]` (config name, adc path string)

- [ ] **Step 1: Write failing tests (append to `tests/test_shell.py`)**

```python
from gcloud_pick.shell import read_shared_profile, shared_profile_path, write_shared_profile


def test_shared_profile_roundtrip_with_adc(fake_gcloud_home):
    path = write_shared_profile("infra", Path("/h/adc/infra@x.json"))
    assert path == shared_profile_path()
    assert read_shared_profile() == ("infra", "/h/adc/infra@x.json")


def test_shared_profile_roundtrip_without_adc(fake_gcloud_home):
    write_shared_profile("default", None)
    assert read_shared_profile() == ("default", "")


def test_read_shared_profile_missing_returns_none(fake_gcloud_home):
    assert read_shared_profile() == (None, None)
```

Note: `shared_profile_path()` derives from `Path.home()`, and the `fake_gcloud_home` fixture sets `HOME`, so writes land under the temp dir.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_shell.py -k shared_profile -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Append to `gcloud_pick/shell.py`**

```python
def shared_profile_path() -> Path:
    """Path to the cross-shell profile file read by the precmd sync hook."""
    return Path.home() / ".config" / "gcloudpick" / "profile"


def _atomic_write_text(target: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_shared_profile(config_name: str, adc_path: Optional[Path]) -> Path:
    """Write '<config>\\n<adc-path-or-empty>\\n' atomically for cross-shell sync."""
    path = shared_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    second = str(adc_path) if adc_path is not None else ""
    _atomic_write_text(path, f"{config_name}\n{second}\n")
    return path


def read_shared_profile() -> tuple[Optional[str], Optional[str]]:
    """Read (config_name, adc_path) from the shared profile file."""
    path = shared_profile_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, None
    config_name = lines[0].strip() if lines else ""
    adc = lines[1].strip() if len(lines) > 1 else ""
    return (config_name or None), adc
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_shell.py -v`
Expected: 7 passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/shell.py tools/gcloud-pick/tests/test_shell.py
git commit -m "feat(gcloud-pick): read/write shared profile file for cross-shell sync"
```

---

### Task 6: cli.py - display + selection helpers

**Files:**
- Modify: `tools/gcloud-pick/gcloud_pick/cli.py` (add helpers; keep existing parse_args)
- Test: `tools/gcloud-pick/tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `GcloudConfig`, `list_configurations`, `current_config` (Task 2).
- Produces:
  - `display_configurations(configs: list[GcloudConfig], current: Optional[str]) -> None` (rich Table to stderr)
  - `validate_selection(selection: str, configs: list[GcloudConfig]) -> Optional[GcloudConfig]` (number / exact name / case-insensitive / unique partial)
  - `get_user_selection(configs: list[GcloudConfig]) -> Optional[GcloudConfig]`

- [ ] **Step 1: Write failing tests (append to `tests/test_cli.py`)**

```python
from gcloud_pick.cli import validate_selection
from gcloud_pick.config import GcloudConfig

CONFIGS = [
    GcloudConfig("default", "ethan.kim@bunjang.co.kr", ""),
    GcloudConfig("infra", "infra@bunjang.co.kr", ""),
]


def test_validate_selection_by_number():
    assert validate_selection("2", CONFIGS) == CONFIGS[1]


def test_validate_selection_out_of_range():
    assert validate_selection("9", CONFIGS) is None


def test_validate_selection_exact_name():
    assert validate_selection("infra", CONFIGS) == CONFIGS[1]


def test_validate_selection_unique_partial():
    assert validate_selection("inf", CONFIGS) == CONFIGS[1]


def test_validate_selection_invalid():
    assert validate_selection("zzz", CONFIGS) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -k validate_selection -v`
Expected: FAIL (cannot import name 'validate_selection').

- [ ] **Step 3: Edit `gcloud_pick/cli.py`**

Add imports near the top (merge into existing import block):

```python
from rich.table import Table

from gcloud_pick.config import (
    GcloudConfig,
    adc_exists,
    current_config,
    list_configurations,
)
```

Add these helpers (above `main`):

```python
def display_configurations(configs: list[GcloudConfig], current: Optional[str]) -> None:
    """Render the available gcloud configurations as a table to stderr."""
    table = Table(title="gcloud configurations", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Config", style="green")
    table.add_column("Account", style="white")
    table.add_column("Project", style="dim")
    table.add_column("ADC", justify="center", width=5)

    for idx, cfg in enumerate(configs, 1):
        active = cfg.name == current
        marker = "[bold green]*[/bold green]" if active else ""
        name_style = "bold green" if active else "green"
        adc_mark = "[green]ok[/green]" if adc_exists(cfg.account) else "[red]-[/red]"
        table.add_row(
            f"{idx}{marker}",
            f"[{name_style}]{cfg.name}[/{name_style}]",
            cfg.account or "[dim](none)[/dim]",
            cfg.project or "",
            adc_mark,
        )
    console.print(table)
    console.print("[dim]* = current. ADC ok = saved per-account file exists.[/dim]")


def validate_selection(selection: str, configs: list[GcloudConfig]) -> Optional[GcloudConfig]:
    """Resolve a selection (number, exact name, or unique partial) to a config."""
    selection = selection.strip()
    if not selection:
        return None
    try:
        idx = int(selection)
        if 1 <= idx <= len(configs):
            return configs[idx - 1]
        return None
    except ValueError:
        pass
    for cfg in configs:
        if cfg.name == selection or cfg.name.lower() == selection.lower():
            return cfg
    matches = [c for c in configs if selection.lower() in c.name.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def get_user_selection(configs: list[GcloudConfig]) -> Optional[GcloudConfig]:
    """Prompt for a configuration selection (number or name)."""
    while True:
        try:
            print("Select config (number/name, q to quit): ", end="", file=sys.stderr, flush=True)
            raw = input().strip()
            if not raw or raw.lower() in ("q", "quit", "exit"):
                return None
            cfg = validate_selection(raw, configs)
            if cfg:
                return cfg
            console.print("[red]Invalid selection.[/red]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all prior + 5 new passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/cli.py tools/gcloud-pick/tests/test_cli.py
git commit -m "feat(gcloud-pick): configuration table display and selection helpers"
```

---

### Task 7: cli.py - main orchestration (interactive + direct)

**Files:**
- Modify: `tools/gcloud-pick/gcloud_pick/cli.py` (replace `main` body, add `_switch`)
- Test: `tools/gcloud-pick/tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `list_configurations`, `current_config`, `adc_exists`, `adc_path_for` (config); `generate_export_commands`, `write_shared_profile` (shell); `display_configurations`, `get_user_selection`, `validate_selection` (Task 6).
- Produces: `_switch(cfg: GcloudConfig) -> int` (writes shared profile, prints exports to stdout, warns to stderr when ADC missing); updated `main`.

- [ ] **Step 1: Write failing tests (append to `tests/test_cli.py`)**

```python
from gcloud_pick import cli as climod
from tests.conftest import write_config


def test_main_direct_switch_with_adc(fake_gcloud_home, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    adc = fake_gcloud_home / "adc" / "infra@bunjang.co.kr.json"
    adc.parent.mkdir(parents=True)
    adc.write_text("{}")

    rc = climod.main(["infra"])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="infra"' in out
    assert f'export GOOGLE_APPLICATION_CREDENTIALS="{adc}"' in out


def test_main_direct_switch_without_adc_unsets(fake_gcloud_home, capsys):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")
    rc = climod.main(["default"])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="default"' in out
    assert "unset GOOGLE_APPLICATION_CREDENTIALS" in out


def test_main_unknown_config_errors(fake_gcloud_home, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    rc = climod.main(["nope"])
    assert rc == 1
    assert capsys.readouterr().out == ""  # nothing on stdout


def test_main_no_configs_errors(fake_gcloud_home):
    assert climod.main([]) == 1


def test_main_interactive_uses_selection(fake_gcloud_home, capsys, monkeypatch):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    monkeypatch.setattr(climod, "get_user_selection", lambda configs: configs[0])
    rc = climod.main([])
    assert rc == 0
    assert 'CLOUDSDK_ACTIVE_CONFIG_NAME="infra"' in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -k "main_" -v`
Expected: FAIL (main is the stub returning 0 / prints nothing as designed).

- [ ] **Step 3: Edit `gcloud_pick/cli.py`**

Add imports (merge into existing blocks):

```python
from gcloud_pick.config import adc_path_for  # add to the existing gcloud_pick.config import
from gcloud_pick.shell import generate_export_commands, write_shared_profile
```

Add `_switch` (above `main`):

```python
def _switch(cfg: GcloudConfig) -> int:
    """Write the shared profile and print export commands for a configuration."""
    if cfg.account and adc_exists(cfg.account):
        adc_path = adc_path_for(cfg.account)
    else:
        adc_path = None
        console.print(
            f"[yellow]No saved ADC file for account '{cfg.account or '(none)'}'. "
            f"ADC will fall back to the default credentials.[/yellow]"
        )
        console.print(f"[dim]Run 'gp --login {cfg.name}' to create one.[/dim]")

    write_shared_profile(cfg.name, adc_path)
    print(generate_export_commands(cfg.name, adc_path))

    account = cfg.account or "(none)"
    console.print(f"[green]Switched to[/green] [bold]{cfg.name}[/bold] [dim]({account})[/dim]")
    console.print("[dim]Other terminals sync on next prompt.[/dim]")
    return 0
```

Replace the body of `main` (keep the `try/except` wrapper and `--login` branch placeholder for Task 8):

```python
def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    try:
        args = parse_args(argv)

        if args.login is not None:
            return _do_login(args.login)

        configs = list_configurations()
        if not configs:
            console.print("[red]No gcloud configurations found.[/red]")
            console.print("[dim]Create one with: gcloud config configurations create <name>[/dim]")
            return 1

        if args.config:
            cfg = validate_selection(args.config, configs)
            if cfg is None:
                console.print(f"[red]Unknown configuration: {args.config}[/red]")
                return 1
            return _switch(cfg)

        display_configurations(configs, current_config())
        cfg = get_user_selection(configs)
        if cfg is None:
            logger.info("No selection made")
            return 1
        return _switch(cfg)

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error")
        return 1
```

Add a temporary stub for `_do_login` (replaced in Task 8) so the module imports:

```python
def _do_login(config_name: str) -> int:
    console.print("[yellow]--login not implemented yet[/yellow]")
    return 1
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/cli.py tools/gcloud-pick/tests/test_cli.py
git commit -m "feat(gcloud-pick): switch orchestration for interactive and direct modes"
```

---

### Task 8: cli.py - `--login` ADC file setup

**Files:**
- Modify: `tools/gcloud-pick/gcloud_pick/cli.py` (replace `_do_login`)
- Test: `tools/gcloud-pick/tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `resolve_adc_account`, `adc_path_for`, `gcloud_dir`, `list_configurations`, `validate_selection`.
- Produces: real `_do_login(config_name: str) -> int`, and `_run_adc_login() -> int` (the interactive `gcloud` call, mocked in tests).

- [ ] **Step 1: Write failing tests (append to `tests/test_cli.py`)**

```python
import json as _json


def test_do_login_saves_per_account_adc(fake_gcloud_home, monkeypatch):
    default_adc = fake_gcloud_home / "application_default_credentials.json"
    default_adc.write_text(_json.dumps({"type": "authorized_user", "refresh_token": "r"}))

    monkeypatch.setattr(climod, "_run_adc_login", lambda: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: "ethan.kim@bunjang.co.kr")

    rc = climod.main(["--login"])
    assert rc == 0
    saved = fake_gcloud_home / "adc" / "ethan.kim@bunjang.co.kr.json"
    assert saved.is_file()
    assert _json.loads(saved.read_text())["type"] == "authorized_user"
    assert (saved.stat().st_mode & 0o777) == 0o600


def test_do_login_warns_on_account_mismatch(fake_gcloud_home, monkeypatch, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    default_adc = fake_gcloud_home / "application_default_credentials.json"
    default_adc.write_text(_json.dumps({"type": "authorized_user"}))
    monkeypatch.setattr(climod, "_run_adc_login", lambda: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: "ethan.kim@bunjang.co.kr")

    rc = climod.main(["--login", "infra"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "mismatch" in err.lower() or "infra@bunjang.co.kr" in err


def test_do_login_fails_when_login_aborts(fake_gcloud_home, monkeypatch):
    monkeypatch.setattr(climod, "_run_adc_login", lambda: 1)
    assert climod.main(["--login"]) == 1


def test_do_login_fails_when_account_unresolved(fake_gcloud_home, monkeypatch):
    (fake_gcloud_home / "application_default_credentials.json").write_text("{}")
    monkeypatch.setattr(climod, "_run_adc_login", lambda: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: None)
    assert climod.main(["--login"]) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -k do_login -v`
Expected: FAIL (stub returns 1 / no file saved).

- [ ] **Step 3: Edit `gcloud_pick/cli.py`**

Add imports (merge):

```python
import os
import shutil
import subprocess

from gcloud_pick.config import gcloud_dir, resolve_adc_account
```

Replace the `_do_login` stub with:

```python
def _run_adc_login() -> int:
    """Run the interactive ADC login. Returns the gcloud exit code."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "login"],
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"[red]Failed to run gcloud: {e}[/red]")
        return 1
    return result.returncode


def _do_login(config_name: str) -> int:
    """Run ADC login and save a per-account ADC file."""
    if _run_adc_login() != 0:
        console.print("[red]ADC login failed or was cancelled.[/red]")
        return 1

    default_adc = gcloud_dir() / "application_default_credentials.json"
    account = resolve_adc_account(default_adc)
    if not account:
        console.print("[red]Could not resolve the ADC account after login.[/red]")
        return 1

    if config_name:
        cfg = validate_selection(config_name, list_configurations())
        if cfg and cfg.account and cfg.account != account:
            console.print(
                f"[yellow]Account mismatch: ADC logged in as {account}, "
                f"but config '{config_name}' uses {cfg.account}.[/yellow]"
            )

    dest = adc_path_for(account)
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(dest.parent, 0o700)
    shutil.copy2(default_adc, dest)
    os.chmod(dest, 0o600)
    console.print(f"[green]Saved ADC for {account}[/green] [dim]-> {dest}[/dim]")
    return 0
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -v`
Expected: all passed.

- [ ] **Step 5: Lint/format then commit**

```bash
uv run ruff check . && uv run ruff format .
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/gcloud_pick/cli.py tools/gcloud-pick/tests/test_cli.py
git commit -m "feat(gcloud-pick): --login creates per-account ADC file with verification"
```

---

### Task 9: Shell glue (gp wrapper + precmd sync) in live dotfiles

**Files:**
- Modify: `~/.zsh_aliases` (add `gp` next to `ap`/`kp`)
- Modify: `~/.zshrc` (add `gcloudpick_sync` next to `awspick_sync`)

This task edits live `$HOME` dotfiles (not tracked in this repo). No git commit. Verify manually.

- [ ] **Step 1: Confirm anchor locations**

Run: `grep -n 'function ap()' ~/.zsh_aliases; grep -n 'awspick_sync' ~/.zshrc`
Expected: shows the existing `ap()` block and `awspick_sync` block (anchors to insert beside).

- [ ] **Step 2: Add `gp()` to `~/.zsh_aliases`** (immediately after the `kp()` block)

```zsh
# gcloud-pick
function gp() {
  eval "$(command gcloud-pick "$@")"
}
```

- [ ] **Step 3: Add `gcloudpick_sync` to `~/.zshrc`** (in the gcloud/cloud section, mirroring `awspick_sync`)

```zsh
gcloudpick_sync() {
  local f="$HOME/.config/gcloudpick/profile"
  [ -f "$f" ] || return
  local cfg adc
  IFS= read -r cfg < "$f"
  adc="$(sed -n '2p' "$f")"
  [ -n "$cfg" ] && export CLOUDSDK_ACTIVE_CONFIG_NAME="$cfg"
  if [ -n "$adc" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$adc"
  else
    unset GOOGLE_APPLICATION_CREDENTIALS
  fi
}
if [[ -z "${precmd_functions[(r)gcloudpick_sync]}" ]]; then
  precmd_functions+=(gcloudpick_sync)
fi
```

- [ ] **Step 4: Verify shell syntax**

Run: `zsh -n ~/.zshrc ~/.zsh_aliases`
Expected: no output (syntax OK).

---

### Task 10: Editable install, docs, monorepo map, end-to-end verification

**Files:**
- Create: `tools/gcloud-pick/README.md`
- Create: `tools/gcloud-pick/LAST_AGENT_RUN.md`
- Modify: `kkamji-lab/AGENTS.md` (Directory Structure tools list + section 5.1 entry-point table)

**Interfaces:**
- Consumes: the installed `gcloud-pick` command.

- [ ] **Step 1: Editable install**

Run: `cd ~/code/code-personal/kkamji-lab/tools/gcloud-pick && uv tool install --editable .`
Expected: installs `gcloud-pick` to `~/.local/bin/gcloud-pick`. Verify: `gcloud-pick --version` prints `gcloud-pick 1.0.0`.

- [ ] **Step 2: Write `README.md`**

```markdown
# gcloud-pick (gp)

Switch the gcloud CLI auth (active configuration) and ADC (Application Default
Credentials) identity together, per-shell and synced across panes.

## Why

gcloud has two independent auth systems: the CLI uses the active configuration's
account; SDKs/Terraform use ADC. They can silently diverge and cause wrong-account
writes. `gp` switches both in lockstep. The starship `custom.gcloud_adc` module
warns (red) when they drift anyway.

## Install

```bash
uv tool install --editable .
```

Add the shell glue (zsh) to your dotfiles:

```zsh
# ~/.zsh_aliases
function gp() { eval "$(command gcloud-pick "$@")" }

# ~/.zshrc
gcloudpick_sync() {
  local f="$HOME/.config/gcloudpick/profile"
  [ -f "$f" ] || return
  local cfg adc
  IFS= read -r cfg < "$f"
  adc="$(sed -n '2p' "$f")"
  [ -n "$cfg" ] && export CLOUDSDK_ACTIVE_CONFIG_NAME="$cfg"
  if [ -n "$adc" ]; then export GOOGLE_APPLICATION_CREDENTIALS="$adc"; else unset GOOGLE_APPLICATION_CREDENTIALS; fi
}
if [[ -z "${precmd_functions[(r)gcloudpick_sync]}" ]]; then
  precmd_functions+=(gcloudpick_sync)
fi
```

## Usage

```bash
gp                 # interactive picker over gcloud configurations
gp infra           # switch directly to the 'infra' configuration
gp --login         # ADC login, save the per-account ADC file
gp --login infra   # ADC login and verify it matches 'infra' account
```

Each switch sets `CLOUDSDK_ACTIVE_CONFIG_NAME` and `GOOGLE_APPLICATION_CREDENTIALS`
(to `~/.config/gcloud/adc/<account>.json`), or unsets the latter when no saved ADC
file exists yet.

## ADC files

`gp --login` saves the ADC credential to `~/.config/gcloud/adc/<account>.json`
(mode 0600). These hold long-lived refresh tokens; treat them like the default ADC
file.
```

- [ ] **Step 3: Write `LAST_AGENT_RUN.md`** (match the brief style of sibling tools)

```markdown
# Last Agent Run

- Tool created: gcloud-pick (gp)
- Purpose: switch gcloud CLI auth + ADC together, per-shell, synced.
- Modules: config.py (configs/accounts/ADC paths + resolution), shell.py (export/unset + shared profile), cli.py (picker + --login).
- Verify: `uv run ruff check . && uv run ruff format --check . && uv run pytest`
- Shell glue: gp() in ~/.zsh_aliases, gcloudpick_sync in ~/.zshrc.
```

- [ ] **Step 4: Update `kkamji-lab/AGENTS.md`**

In section 4 (Directory Structure), add under `tools/` (alphabetical, after `git-worktree-tool`):

```
│   ├── gcloud-pick/            # gcloud CLI auth + ADC 동시 전환 (gp)
```

In section 5.1 entry-point table, add a row:

```
| gcloud-pick | `gcloud-pick` | `gcloud_pick.cli:main` |
```

- [ ] **Step 5: Full verification**

Run: `cd ~/code/code-personal/kkamji-lab/tools/gcloud-pick && uv run ruff check . && uv run ruff format --check . && uv run pytest -v`
Expected: ruff clean, all tests pass.

- [ ] **Step 6: Manual end-to-end (record results)**

In a fresh `exec zsh`:
- `gp` shows the configuration table; selecting `infra` prints exports and the starship prompt shows `infra`.
- `gp default` switches; if no `adc/ethan.kim@bunjang.co.kr.json` exists, ADC unsets and the starship ADC warning may show red until `gp --login default`.
- Open a second pane: it syncs to the same config on next prompt.

- [ ] **Step 7: Commit**

```bash
cd ~/code/code-personal/kkamji-lab
git add tools/gcloud-pick/README.md tools/gcloud-pick/LAST_AGENT_RUN.md AGENTS.md
git commit -m "docs(gcloud-pick): README, agent run log, monorepo map update"
```

---

## Self-Review

- **Spec coverage:** purpose/levers (Task 4,7), per-shell `CLOUDSDK_ACTIVE_CONFIG_NAME` + `GOOGLE_APPLICATION_CREDENTIALS` (Task 4,7), shared profile sync (Task 5,9), picker (Task 6,7), `--login` + per-account ADC files (Task 8), missing-ADC unset+warn (Task 7), package layout/tooling (Task 1), tests (Tasks 2-8), shell glue (Task 9), docs + monorepo map (Task 10), starship relationship (README, Task 10). `--list`/group-filter are spec non-goals - intentionally absent.
- **Placeholder scan:** none; `_do_login` stub in Task 7 is explicitly replaced in Task 8.
- **Type consistency:** `GcloudConfig(name, account, project)` used consistently; `generate_export_commands(config_name, adc_path, shell_name)`, `write_shared_profile(config_name, adc_path)`, `adc_path_for(account)`, `resolve_adc_account(adc_file)`, `validate_selection`/`get_user_selection` returning `GcloudConfig` align across tasks.
