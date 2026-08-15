"""Tests for the parallel map helper and the single-call status probe."""

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


# --- _run_parallel ---


def test_run_parallel_preserves_input_order() -> None:
    result = cli._run_parallel([1, 2, 3, 4, 5], lambda n: n * n)
    assert result == [1, 4, 9, 16, 25]


def test_run_parallel_applies_fn_to_every_item() -> None:
    seen: set[int] = set()
    cli._run_parallel([10, 20, 30], lambda n: seen.add(n))
    assert seen == {10, 20, 30}


def test_run_parallel_empty_returns_empty() -> None:
    assert cli._run_parallel([], lambda n: n) == []


def test_run_parallel_single_item() -> None:
    assert cli._run_parallel([7], lambda n: n + 1) == [8]


# --- populate_status (single `git status --porcelain=v2 --branch` call) ---


def _porcelain(upstream: str | None = None, ab: str | None = None, entries: str = "") -> str:
    lines = [
        "# branch.oid e8514192b893d4a462b1b9cb3812d745a99c6b7c",
        "# branch.head main",
    ]
    if upstream is not None:
        lines.append(f"# branch.upstream {upstream}")
    if ab is not None:
        lines.append(f"# branch.ab {ab}")
    text = "\n".join(lines) + "\n"
    if entries:
        text += entries
    return text


def test_populate_status_clean_with_sync(monkeypatch) -> None:
    monkeypatch.setattr(
        cli, "run_git", lambda args, cwd=None: _ok(stdout=_porcelain("origin/main", "+2 -3"))
    )
    wt = _wt()
    cli.populate_status(wt)
    assert wt._dirty is False
    assert wt._has_upstream is True
    assert wt._upstream_ref == "origin/main"
    assert wt._sync_status == "↑2 ↓3"


def test_populate_status_dirty_detected_from_entry_lines(monkeypatch) -> None:
    entries = "1 .M N... 100644 100644 100644 aaa bbb file.py\n? untracked.txt\n"
    monkeypatch.setattr(
        cli,
        "run_git",
        lambda args, cwd=None: _ok(stdout=_porcelain("origin/main", "+0 -0", entries)),
    )
    wt = _wt()
    cli.populate_status(wt)
    assert wt._dirty is True
    assert wt._sync_status == "="


def test_populate_status_no_upstream(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout=_porcelain()))
    wt = _wt()
    cli.populate_status(wt)
    assert wt._dirty is False
    assert wt._has_upstream is False
    assert wt._upstream_ref is None
    assert wt._sync_status is None


def test_populate_status_upstream_without_ab_is_empty_sync(monkeypatch) -> None:
    # Upstream configured but no remote-tracking ref locally -> git omits branch.ab.
    # Matches the legacy rev-list-failure path which yielded "".
    monkeypatch.setattr(
        cli, "run_git", lambda args, cwd=None: _ok(stdout=_porcelain("origin/main"))
    )
    wt = _wt()
    cli.populate_status(wt)
    assert wt._has_upstream is True
    assert wt._sync_status == ""


def test_populate_status_ahead_only(monkeypatch) -> None:
    monkeypatch.setattr(
        cli, "run_git", lambda args, cwd=None: _ok(stdout=_porcelain("origin/main", "+4 -0"))
    )
    wt = _wt()
    cli.populate_status(wt)
    assert wt._sync_status == "↑4"


def test_populate_status_behind_only(monkeypatch) -> None:
    monkeypatch.setattr(
        cli, "run_git", lambda args, cwd=None: _ok(stdout=_porcelain("origin/main", "+0 -7"))
    )
    wt = _wt()
    cli.populate_status(wt)
    assert wt._sync_status == "↓7"


def test_populate_status_treats_git_failure_as_dirty(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail())
    wt = _wt()
    cli.populate_status(wt)
    assert wt._dirty is True
    assert wt._has_upstream is False
    assert wt._sync_status == ""


def test_populate_status_uses_porcelain_v2_branch(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake(args, cwd=None):
        calls.append(args)
        return _ok(stdout=_porcelain("origin/main", "+0 -0"))

    monkeypatch.setattr(cli, "run_git", fake)
    cli.populate_status(_wt())
    assert ["status", "--porcelain=v2", "--branch"] in calls


def test_get_sync_status_returns_cached_value_without_git(monkeypatch) -> None:
    def boom(args, cwd=None):
        raise AssertionError("get_sync_status must not call git when _sync_status is cached")

    monkeypatch.setattr(cli, "run_git", boom)
    wt = _wt()
    wt._sync_status = "↑1"
    assert cli.get_sync_status(wt) == "↑1"
