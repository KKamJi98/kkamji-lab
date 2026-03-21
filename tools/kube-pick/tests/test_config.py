"""Tests for kube_pick.config and kube_pick.shell._atomic_write_text."""

from pathlib import Path
from unittest.mock import patch

import pytest

from kube_pick.config import list_kubeconfig_files
from kube_pick.shell import _atomic_write_text

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_VALID_KUBECONFIG = """\
apiVersion: v1
kind: Config
clusters:
- name: my-cluster
  cluster:
    server: https://localhost
users: []
contexts: []
"""

_NO_CLUSTERS_KEY = """\
apiVersion: v1
kind: Config
users: []
contexts: []
"""


def _make_valid_kubeconfig(path: Path) -> None:
    """Write a minimal valid kubeconfig YAML to *path*."""
    path.write_text(_VALID_KUBECONFIG, encoding="utf-8")


# ---------------------------------------------------------------------------
# list_kubeconfig_files
# ---------------------------------------------------------------------------


class TestListKubeconfigFiles:
    """list_kubeconfig_files() in kube_pick.config."""

    def test_detects_valid_kubeconfig(self, tmp_path):
        """Given a file named 'config' with a valid kubeconfig body,
        list_kubeconfig_files should return that file."""
        cfg = tmp_path / "config"
        _make_valid_kubeconfig(cfg)

        with patch("kube_pick.config.get_kube_dir", return_value=tmp_path):
            result = list_kubeconfig_files()

        assert cfg in result

    def test_skips_invalid_yaml(self, tmp_path):
        """Given a file named 'config' whose content is not valid YAML,
        list_kubeconfig_files should skip it and return an empty list."""
        bad = tmp_path / "config"
        bad.write_text(":: not valid yaml :::\n[[[", encoding="utf-8")

        with patch("kube_pick.config.get_kube_dir", return_value=tmp_path):
            result = list_kubeconfig_files()

        assert bad not in result

    def test_skips_yaml_without_clusters_key(self, tmp_path):
        """Given a file named 'config' that is valid YAML but lacks a 'clusters' key,
        list_kubeconfig_files should skip it."""
        not_kube = tmp_path / "config"
        not_kube.write_text(_NO_CLUSTERS_KEY, encoding="utf-8")

        with patch("kube_pick.config.get_kube_dir", return_value=tmp_path):
            result = list_kubeconfig_files()

        assert not_kube not in result

    def test_excludes_bak_extension(self, tmp_path):
        """Files ending in .bak should be excluded even if they contain 'config'."""
        backup = tmp_path / "config.bak"
        _make_valid_kubeconfig(backup)

        with patch("kube_pick.config.get_kube_dir", return_value=tmp_path):
            result = list_kubeconfig_files()

        assert backup not in result

    def test_excludes_backup_extension(self, tmp_path):
        """Files ending in .backup should be excluded."""
        backup = tmp_path / "config.backup"
        _make_valid_kubeconfig(backup)

        with patch("kube_pick.config.get_kube_dir", return_value=tmp_path):
            result = list_kubeconfig_files()

        assert backup not in result

    def test_returns_empty_when_kube_dir_missing(self, tmp_path):
        """When ~/.kube does not exist, list_kubeconfig_files should return []."""
        missing_dir = tmp_path / "nonexistent"

        with patch("kube_pick.config.get_kube_dir", return_value=missing_dir):
            result = list_kubeconfig_files()

        assert result == []

    def test_result_is_sorted_by_name(self, tmp_path):
        """Multiple valid kubeconfigs should be returned in alphabetical order."""
        for name in ("config_z", "config_a", "config_m"):
            _make_valid_kubeconfig(tmp_path / name)

        with patch("kube_pick.config.get_kube_dir", return_value=tmp_path):
            result = list_kubeconfig_files()

        names = [p.name for p in result]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# _atomic_write_text
# ---------------------------------------------------------------------------


class TestAtomicWriteText:
    """_atomic_write_text() in kube_pick.shell."""

    def test_writes_content_to_target(self, tmp_path):
        """Given a valid target path, the file should contain the expected content."""
        target = tmp_path / "state"
        _atomic_write_text(target, "hello-world")

        assert target.read_text(encoding="utf-8") == "hello-world"

    def test_no_temp_file_left_on_success(self, tmp_path):
        """After a successful write, no .tmp leftover files should remain."""
        target = tmp_path / "state"
        _atomic_write_text(target, "clean")

        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == []

    def test_raises_on_permission_error_and_removes_tmp(self, tmp_path):
        """When os.replace raises PermissionError, the exception is re-raised and
        the temporary file must be cleaned up."""
        target = tmp_path / "state"

        with patch("kube_pick.shell.os.replace", side_effect=PermissionError("simulated")):
            with pytest.raises(PermissionError):
                _atomic_write_text(target, "data")

        # No tmp leftovers after failure
        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == []
