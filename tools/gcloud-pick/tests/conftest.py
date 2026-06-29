# tests/conftest.py
"""Shared pytest fixtures for gcloud-pick tests."""

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
