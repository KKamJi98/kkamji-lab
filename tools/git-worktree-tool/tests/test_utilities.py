"""Tests for utility functions: is_dirty, has_upstream, get_sync_status, etc."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import wt.cli as cli
from wt.cli import Worktree


def _ok(stdout: str = "", stderr: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stderr: str = "fatal: error") -> CompletedProcess[str]:
    return CompletedProcess(args=["git"], returncode=128, stdout="", stderr=stderr)


def _wt(branch: str = "main", path: str = "/repo/main", commit: str = "deadbeef") -> Worktree:
    return Worktree(path=Path(path), branch=branch, commit=commit)


# --- is_dirty ---


def test_is_dirty_returns_true_when_changes_exist(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout=" M file.py\n"))
    assert cli.is_dirty(_wt()) is True


def test_is_dirty_returns_false_when_clean(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout=""))
    assert cli.is_dirty(_wt()) is False


def test_is_dirty_returns_false_on_git_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail())
    # git failure returns empty stdout → not dirty
    assert cli.is_dirty(_wt()) is False


# --- has_upstream ---


def test_has_upstream_returns_true_on_success(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="origin/main\n"))
    assert cli.has_upstream(_wt()) is True


def test_has_upstream_returns_false_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail())
    assert cli.has_upstream(_wt()) is False


# --- get_sync_status ---


def test_get_sync_status_equal(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="0\t0\n"))
    assert cli.get_sync_status(_wt()) == "="


def test_get_sync_status_ahead(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="3\t0\n"))
    assert cli.get_sync_status(_wt()) == "↑3"


def test_get_sync_status_behind(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="0\t5\n"))
    assert cli.get_sync_status(_wt()) == "↓5"


def test_get_sync_status_diverged(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="2\t3\n"))
    assert cli.get_sync_status(_wt()) == "↑2 ↓3"


def test_get_sync_status_returns_empty_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail())
    assert cli.get_sync_status(_wt()) == ""


def test_get_sync_status_skips_detached_head() -> None:
    wt = Worktree(
        path=Path("/repo/detached"),
        branch="(detached abc1234)",
        commit="abc1234",
        is_detached=True,
    )
    # Should return empty without calling git at all
    assert cli.get_sync_status(wt) == ""


# --- has_remote_branch ---


def test_has_remote_branch_true(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="  origin/main\n"))
    assert cli.has_remote_branch(Path("/bare"), "main") is True


def test_has_remote_branch_false(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout=""))
    assert cli.has_remote_branch(Path("/bare"), "nonexistent") is False


# --- has_local_branch ---


def test_has_local_branch_true(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout="* main\n"))
    assert cli.has_local_branch(Path("/bare"), "main") is True


def test_has_local_branch_false(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout=""))
    assert cli.has_local_branch(Path("/bare"), "nonexistent") is False


# --- get_default_branch ---


def test_get_default_branch_from_symbolic_ref(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "run_git",
        lambda args, cwd=None: _ok(stdout="refs/remotes/origin/main\n"),
    )
    assert cli.get_default_branch(Path("/bare")) == "main"


def test_get_default_branch_fallback_to_master(monkeypatch) -> None:
    call_count = 0

    def fake_run_git(args, cwd=None):
        nonlocal call_count
        call_count += 1
        if args[0] == "symbolic-ref":
            return _fail()
        # First branch -r check for "main" → not found
        if call_count == 2:
            return _ok(stdout="")
        # Second check for "master" → found
        return _ok(stdout="  origin/master\n")

    monkeypatch.setattr(cli, "run_git", fake_run_git)
    assert cli.get_default_branch(Path("/bare")) == "master"


def test_get_default_branch_ultimate_fallback(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail())
    assert cli.get_default_branch(Path("/bare")) == "main"


# --- _parse_worktree_record ---


def test_parse_worktree_record_normal(tmp_path) -> None:
    wt_path = tmp_path / "main"
    wt_path.mkdir()
    record = {
        "worktree": str(wt_path),
        "HEAD": "abc12345def67890",
        "branch": "refs/heads/main",
    }
    wt = cli._parse_worktree_record(record)
    assert wt is not None
    assert wt.branch == "main"
    assert wt.commit == "abc12345"
    assert wt.is_detached is False


def test_parse_worktree_record_detached(tmp_path) -> None:
    wt_path = tmp_path / "detached"
    wt_path.mkdir()
    record = {
        "worktree": str(wt_path),
        "HEAD": "deadbeefcafebabe",
    }
    wt = cli._parse_worktree_record(record)
    assert wt is not None
    assert wt.branch == "(detached deadbeef)"
    assert wt.is_detached is True


def test_parse_worktree_record_bare_returns_none() -> None:
    record = {"worktree": "/repo/.bare", "bare": "true"}
    assert cli._parse_worktree_record(record) is None


def test_parse_worktree_record_nonexistent_path_returns_none() -> None:
    record = {
        "worktree": "/nonexistent/path/that/does/not/exist",
        "HEAD": "abc12345",
        "branch": "refs/heads/main",
    }
    assert cli._parse_worktree_record(record) is None


# --- find_bare_repo ---


def test_find_bare_repo_via_git_common_dir(tmp_path, monkeypatch) -> None:
    bare_dir = tmp_path / ".bare"
    bare_dir.mkdir()

    monkeypatch.setattr(
        cli,
        "run_git",
        lambda args, cwd=None: _ok(stdout=str(bare_dir) + "\n"),
    )
    assert cli.find_bare_repo(tmp_path) == bare_dir


def test_find_bare_repo_rejects_non_bare_dot_bare(tmp_path, monkeypatch) -> None:
    """A .bare directory that isn't a git bare repo should be rejected."""
    bare_dir = tmp_path / ".bare"
    bare_dir.mkdir()

    def fake_run_git(args, cwd=None):
        if args == ["rev-parse", "--git-common-dir"]:
            return _fail()
        if args == ["rev-parse", "--is-bare-repository"]:
            return _ok(stdout="false\n")
        return _fail()

    monkeypatch.setattr(cli, "run_git", fake_run_git)
    assert cli.find_bare_repo(tmp_path) is None


def test_find_bare_repo_returns_none_when_nothing_found(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail())
    assert cli.find_bare_repo(tmp_path) is None
