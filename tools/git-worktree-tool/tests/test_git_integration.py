"""Integration tests that exercise real git repositories."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import wt.cli as cli


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )


def _require_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr


def _make_remote(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    _require_ok(_git(source, "init"))
    _require_ok(_git(source, "config", "user.email", "test@example.com"))
    _require_ok(_git(source, "config", "user.name", "Test User"))
    _require_ok(_git(source, "checkout", "-b", "main"))
    (source / "README.md").write_text("# demo\n", encoding="utf-8")
    _require_ok(_git(source, "add", "README.md"))
    _require_ok(_git(source, "commit", "-m", "initial commit"))

    remote = tmp_path / "remote.git"
    _require_ok(_git(tmp_path, "clone", "--bare", str(source), str(remote)))
    return remote


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")
def test_cmd_remove_keeps_unmerged_branch_in_real_repo(tmp_path, capsys) -> None:
    remote = _make_remote(tmp_path)
    project = tmp_path / "project"
    cli.Color.init()

    assert cli.cmd_init(str(remote), str(project), None) == 0

    bare_repo = project / ".bare"
    feature_wt = project / "feat-keep"
    _require_ok(_git(bare_repo, "worktree", "add", "-b", "feat/keep", str(feature_wt), "main"))
    _require_ok(_git(feature_wt, "config", "user.email", "test@example.com"))
    _require_ok(_git(feature_wt, "config", "user.name", "Test User"))
    (feature_wt / "feature.txt").write_text("unmerged\n", encoding="utf-8")
    _require_ok(_git(feature_wt, "add", "feature.txt"))
    _require_ok(_git(feature_wt, "commit", "-m", "add unmerged feature"))

    result = cli.cmd_remove(
        bare_repo,
        identifiers=["feat/keep"],
        force=False,
        delete_branch=True,
        yes=True,
    )

    output = capsys.readouterr().out
    assert result == 2
    assert "branch kept" in output
    assert not feature_wt.exists()
    branch = _git(bare_repo, "branch", "--list", "feat/keep")
    assert "feat/keep" in branch.stdout
