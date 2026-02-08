from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import wt.cli as cli


def _ok(stdout: str = "", stderr: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stderr: str = "fatal: not a git repository") -> CompletedProcess[str]:
    return CompletedProcess(args=["git"], returncode=128, stdout="", stderr=stderr)


def test_cmd_init_does_not_create_root_git_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "demo-repo"
    bare_path = target / ".bare"

    monkeypatch.setattr(cli, "get_default_branch", lambda _bare_repo: "main")
    monkeypatch.setattr(cli, "has_remote_branch", lambda _bare_repo, _branch: False)

    def fake_run_git(args: list[str], cwd: Path | None = None) -> CompletedProcess[str]:
        if args[:2] == ["clone", "--bare"]:
            bare_path.mkdir(parents=True, exist_ok=True)
            return _ok()

        if args[:2] == ["worktree", "add"]:
            Path(args[2]).mkdir(parents=True, exist_ok=True)
            return _ok()

        return _ok()

    monkeypatch.setattr(cli, "run_git", fake_run_git)

    result = cli.cmd_init("git@github.com:org/repo.git", str(target), None)

    assert result == 0
    assert bare_path.is_dir()
    assert (target / "main").is_dir()
    assert not (target / ".git").exists()


def test_find_bare_repo_can_use_parent_dot_bare_without_root_git_file(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "repo"
    branch_dir = root / "main"
    bare_dir = root / ".bare"
    branch_dir.mkdir(parents=True)
    bare_dir.mkdir(parents=True)

    monkeypatch.setattr(cli, "run_git", lambda _args, cwd=None: _fail())

    assert cli.find_bare_repo(root) == bare_dir
    assert cli.find_bare_repo(branch_dir) == bare_dir
