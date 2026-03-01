"""Integration tests for cmd_status, cmd_pull, cmd_add, cmd_prune using monkeypatch."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import wt.cli as cli
from wt.cli import Worktree


def _ok(stdout: str = "", stderr: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stderr: str = "fatal: error") -> CompletedProcess[str]:
    return CompletedProcess(args=["git"], returncode=128, stdout="", stderr=stderr)


def _make_worktrees(tmp_path: Path, specs: list[dict]) -> list[Worktree]:
    """Create worktree directories and return Worktree objects."""
    worktrees = []
    for spec in specs:
        wt_dir = tmp_path / spec.get("dirname", spec["branch"].replace("/", "-"))
        wt_dir.mkdir(exist_ok=True)
        worktrees.append(
            Worktree(
                path=wt_dir,
                branch=spec["branch"],
                commit=spec.get("commit", "deadbeef"),
                is_detached=spec.get("is_detached", False),
            )
        )
    return worktrees


# ──────────────────────────────── cmd_status ────────────────────────────────


class TestCmdStatus:
    def test_all_clean(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(
            tmp_path,
            [
                {"branch": "main"},
                {"branch": "develop"},
            ],
        )
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: False)
        monkeypatch.setattr(cli, "has_upstream", lambda wt: True)
        monkeypatch.setattr(cli, "get_sync_status", lambda wt: "=")
        cli.Color.init()

        result = cli.cmd_status(tmp_path)

        assert result == 0
        output = capsys.readouterr().out
        assert "clean=2" in output
        assert "dirty=0" in output

    def test_dirty_worktree_returns_2(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}, {"branch": "feat"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: wt.branch == "feat")
        monkeypatch.setattr(cli, "has_upstream", lambda wt: True)
        monkeypatch.setattr(cli, "get_sync_status", lambda wt: "=")
        cli.Color.init()

        result = cli.cmd_status(tmp_path)

        assert result == 2
        output = capsys.readouterr().out
        assert "dirty=1" in output

    def test_no_upstream_shown(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: False)
        monkeypatch.setattr(cli, "has_upstream", lambda wt: False)
        cli.Color.init()

        cli.cmd_status(tmp_path)

        output = capsys.readouterr().out
        assert "no upstream" in output

    def test_detached_shown(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "(detached abc1234)", "is_detached": True}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: False)
        cli.Color.init()

        cli.cmd_status(tmp_path)

        output = capsys.readouterr().out
        assert "detached" in output

    def test_empty_worktrees(self, tmp_path, monkeypatch, capsys) -> None:
        monkeypatch.setattr(cli, "get_worktrees", lambda _: [])

        result = cli.cmd_status(tmp_path)

        assert result == 1
        assert "No worktrees found" in capsys.readouterr().out

    def test_json_output(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}, {"branch": "feat"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: wt.branch == "feat")
        monkeypatch.setattr(cli, "has_upstream", lambda wt: True)
        monkeypatch.setattr(cli, "get_sync_status", lambda wt: "=")

        result = cli.cmd_status(tmp_path, json_output=True)

        output = json.loads(capsys.readouterr().out)
        assert result == 2
        assert output["summary"]["total"] == 2
        assert output["summary"]["dirty"] == 1
        assert output["worktrees"][0]["branch"] == "main"
        assert output["worktrees"][0]["status"] == "clean"
        assert output["worktrees"][1]["status"] == "dirty"


# ──────────────────────────────── cmd_pull ────────────────────────────────


class TestCmdPull:
    def _setup_pull(
        self,
        monkeypatch,
        tmp_path,
        worktrees,
        dirty_branches=None,
        no_upstream=None,
        no_remote=None,
    ):
        """Common setup for cmd_pull tests."""
        dirty_branches = dirty_branches or set()
        no_upstream = no_upstream or set()
        no_remote = no_remote or set()

        monkeypatch.setattr(cli, "get_worktrees", lambda _: worktrees)
        monkeypatch.setattr(cli, "cmd_fetch", lambda _: 0)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: wt.branch in dirty_branches)
        monkeypatch.setattr(cli, "has_upstream", lambda wt: wt.branch not in no_upstream)
        monkeypatch.setattr(cli, "has_remote_branch", lambda bare, branch: branch not in no_remote)

    def test_ff_only_success(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts)

        head_calls = []

        def fake_run_git(args, cwd=None):
            if args[:2] == ["rev-parse", "HEAD"]:
                head_calls.append(1)
                # Return different hash on second call to simulate ff
                if len(head_calls) == 1:
                    return _ok(stdout="aaa\n")
                return _ok(stdout="bbb\n")
            if args[:2] == ["merge", "--ff-only"]:
                return _ok(stdout="Updating aaa..bbb\n")
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_pull(tmp_path)

        assert result == 0
        output = capsys.readouterr().out
        assert "fast-forwarded" in output

    def test_ff_only_already_up_to_date(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts)

        def fake_run_git(args, cwd=None):
            if args[:2] == ["rev-parse", "HEAD"]:
                return _ok(stdout="same_hash\n")
            if args[:2] == ["merge", "--ff-only"]:
                return _ok(stdout="Already up to date.\n")
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_pull(tmp_path)

        assert result == 0
        output = capsys.readouterr().out
        assert "already up to date" in output

    def test_ff_only_diverged(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts)

        def fake_run_git(args, cwd=None):
            if args[:2] == ["rev-parse", "HEAD"]:
                return _ok(stdout="aaa\n")
            if args[:2] == ["merge", "--ff-only"]:
                return _fail(stderr="fatal: Not possible to fast-forward")
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_pull(tmp_path)

        assert result == 2
        output = capsys.readouterr().out
        assert "cannot fast-forward" in output

    def test_skip_dirty(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts, dirty_branches={"main"})
        cli.Color.init()

        cli.cmd_pull(tmp_path)

        output = capsys.readouterr().out
        assert "dirty" in output.lower()

    def test_skip_no_upstream(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts, no_upstream={"main"})
        cli.Color.init()

        cli.cmd_pull(tmp_path)

        output = capsys.readouterr().out
        assert "no upstream" in output

    def test_skip_detached(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "(detached abc1234)", "is_detached": True}])
        self._setup_pull(monkeypatch, tmp_path, wts)
        cli.Color.init()

        cli.cmd_pull(tmp_path)

        output = capsys.readouterr().out
        assert "detached HEAD" in output

    def test_rebase_success(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts)

        head_calls = []

        def fake_run_git(args, cwd=None):
            if args[:2] == ["rev-parse", "HEAD"]:
                head_calls.append(1)
                if len(head_calls) == 1:
                    return _ok(stdout="aaa\n")
                return _ok(stdout="bbb\n")
            if args[0] == "rebase":
                return _ok(stdout="Successfully rebased\n")
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_pull(tmp_path, rebase=True)

        assert result == 0
        output = capsys.readouterr().out
        assert "rebased" in output

    def test_rebase_conflict_aborts(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        self._setup_pull(monkeypatch, tmp_path, wts)

        abort_called = []

        def fake_run_git(args, cwd=None):
            if args[:2] == ["rev-parse", "HEAD"]:
                return _ok(stdout="aaa\n")
            if args[0] == "rebase" and "--abort" in args:
                abort_called.append(True)
                return _ok()
            if args[0] == "rebase":
                return _fail(stderr="CONFLICT")
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_pull(tmp_path, rebase=True)

        assert result == 2
        assert abort_called
        output = capsys.readouterr().out
        assert "rebase failed" in output

    def test_fetch_failure_aborts(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(cli, "cmd_fetch", lambda _: 1)

        result = cli.cmd_pull(tmp_path)

        assert result == 1


# ──────────────────────────────── cmd_add ────────────────────────────────


class TestCmdAdd:
    def test_add_existing_remote_branch(self, tmp_path, monkeypatch, capsys) -> None:
        bare_repo = tmp_path / ".bare"
        bare_repo.mkdir()

        def fake_run_git(args, cwd=None):
            if args[:2] == ["branch", "-r"]:
                return _ok(stdout="  origin/feat/login\n")
            if args[:2] == ["branch", "--list"]:
                return _ok(stdout="")
            if args[:2] == ["worktree", "add"]:
                Path(args[-2]).mkdir(parents=True, exist_ok=True)
                return _ok()
            if args[:2] == ["branch", "--set-upstream-to"]:
                return _ok()
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_add(bare_repo, "feat/login", None, create=False, base=None)

        assert result == 0
        output = capsys.readouterr().out
        assert "created worktree" in output.lower()

    def test_add_create_new_branch(self, tmp_path, monkeypatch, capsys) -> None:
        bare_repo = tmp_path / ".bare"
        bare_repo.mkdir()

        def fake_run_git(args, cwd=None):
            if args[:2] == ["branch", "-r"]:
                return _ok(stdout="")
            if args[:2] == ["worktree", "add"]:
                Path(args[-1]).mkdir(parents=True, exist_ok=True)
                return _ok()
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_add(bare_repo, "feat/new", None, create=True, base=None)

        assert result == 0
        output = capsys.readouterr().out
        assert "New branch created" in output

    def test_add_create_from_base(self, tmp_path, monkeypatch, capsys) -> None:
        bare_repo = tmp_path / ".bare"
        bare_repo.mkdir()

        worktree_add_args = []

        def fake_run_git(args, cwd=None):
            if args[:2] == ["branch", "-r"]:
                if "main" in str(args):
                    return _ok(stdout="  origin/main\n")
                return _ok(stdout="")
            if args[:2] == ["worktree", "add"]:
                worktree_add_args.extend(args)
                wt_path = args[3] if "-b" in args else args[2]
                Path(wt_path).mkdir(parents=True, exist_ok=True)
                return _ok()
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_add(bare_repo, "feat/from-main", None, create=True, base="main")

        assert result == 0
        assert "origin/main" in worktree_add_args

    def test_add_base_without_create_fails(self, tmp_path, capsys) -> None:
        bare_repo = tmp_path / ".bare"
        bare_repo.mkdir()
        cli.Color.init()

        result = cli.cmd_add(bare_repo, "feat/x", None, create=False, base="main")

        assert result == 1
        assert "--base requires --create" in capsys.readouterr().out

    def test_add_path_already_exists(self, tmp_path, monkeypatch, capsys) -> None:
        bare_repo = tmp_path / ".bare"
        bare_repo.mkdir()
        existing = bare_repo.parent / "feat-x"
        existing.mkdir()
        cli.Color.init()

        result = cli.cmd_add(bare_repo, "feat/x", None, create=False, base=None)

        assert result == 1
        assert "already exists" in capsys.readouterr().out

    def test_add_upstream_failure_warns(self, tmp_path, monkeypatch, capsys) -> None:
        bare_repo = tmp_path / ".bare"
        bare_repo.mkdir()

        def fake_run_git(args, cwd=None):
            if args[:2] == ["branch", "-r"]:
                return _ok(stdout="  origin/main\n")
            if args[:2] == ["branch", "--list"]:
                return _ok(stdout="* main\n")
            if args[:2] == ["worktree", "add"]:
                Path(args[2]).mkdir(parents=True, exist_ok=True)
                return _ok()
            if args[:2] == ["branch", "--set-upstream-to"]:
                return _fail(stderr="error: upstream failed")
            return _ok()

        monkeypatch.setattr(cli, "run_git", fake_run_git)
        cli.Color.init()

        result = cli.cmd_add(bare_repo, "main", None, create=False, base=None)

        assert result == 0
        output = capsys.readouterr().out
        assert "WARN" in output


# ──────────────────────────────── cmd_list ────────────────────────────────


class TestCmdList:
    def test_list_normal(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}, {"branch": "dev"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        cli.Color.init()

        result = cli.cmd_list(tmp_path)

        assert result == 0
        output = capsys.readouterr().out
        assert "main" in output
        assert "dev" in output

    def test_list_json(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)

        result = cli.cmd_list(tmp_path, json_output=True)

        assert result == 0
        items = json.loads(capsys.readouterr().out)
        assert len(items) == 1
        assert items[0]["branch"] == "main"
        assert items[0]["detached"] is False

    def test_list_empty(self, tmp_path, monkeypatch, capsys) -> None:
        monkeypatch.setattr(cli, "get_worktrees", lambda _: [])

        result = cli.cmd_list(tmp_path)

        assert result == 1
        assert "No worktrees found" in capsys.readouterr().out


# ──────────────────────────────── cmd_prune ────────────────────────────────


class TestCmdPrune:
    def test_prune_success(self, tmp_path, monkeypatch, capsys) -> None:
        monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok())
        cli.Color.init()

        result = cli.cmd_prune(tmp_path)

        assert result == 0
        assert "pruned" in capsys.readouterr().out

    def test_prune_dry_run_with_stale(self, tmp_path, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            cli,
            "run_git",
            lambda args, cwd=None: _ok(stdout="Removing worktrees/stale\n"),
        )
        cli.Color.init()

        result = cli.cmd_prune(tmp_path, dry_run=True)

        assert result == 0
        output = capsys.readouterr().out
        assert "Removing" in output

    def test_prune_dry_run_clean(self, tmp_path, monkeypatch, capsys) -> None:
        monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok(stdout=""))
        cli.Color.init()

        result = cli.cmd_prune(tmp_path, dry_run=True)

        assert result == 0
        assert "no stale references" in capsys.readouterr().out

    def test_prune_failure(self, tmp_path, monkeypatch, capsys) -> None:
        monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _fail(stderr="prune error"))
        cli.Color.init()

        result = cli.cmd_prune(tmp_path)

        assert result == 1
        assert "FAIL" in capsys.readouterr().out


# ──────────────────────────────── cmd_remove ────────────────────────────────


class TestCmdRemove:
    def test_remove_with_yes_flag(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "feat/old"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr(cli, "is_dirty", lambda wt: False)
        monkeypatch.setattr(cli, "run_git", lambda args, cwd=None: _ok())
        cli.Color.init()

        result = cli.cmd_remove(tmp_path, identifiers=["feat/old"], force=False, yes=True)

        assert result == 0
        output = capsys.readouterr().out
        assert "removed worktree" in output.lower()

    def test_remove_confirmation_abort(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "feat/old"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        monkeypatch.setattr("builtins.input", lambda _: "n")
        cli.Color.init()

        result = cli.cmd_remove(tmp_path, identifiers=["feat/old"], force=False, yes=False)

        assert result == 1
        assert "Aborted" in capsys.readouterr().out

    def test_remove_no_match(self, tmp_path, monkeypatch, capsys) -> None:
        wts = _make_worktrees(tmp_path, [{"branch": "main"}])
        monkeypatch.setattr(cli, "get_worktrees", lambda _: wts)
        cli.Color.init()

        result = cli.cmd_remove(tmp_path, identifiers=["nonexistent"], force=False, yes=True)

        assert result == 1
        assert "No matching worktrees" in capsys.readouterr().out


# ────────────────────────── Caching behavior ──────────────────────────


class TestCaching:
    def test_is_dirty_caches_result(self, monkeypatch) -> None:
        call_count = 0

        def counting_run_git(args, cwd=None):
            nonlocal call_count
            call_count += 1
            return _ok(stdout=" M file.py\n")

        monkeypatch.setattr(cli, "run_git", counting_run_git)

        wt = Worktree(path=Path("/repo/main"), branch="main", commit="abc")
        cli.is_dirty(wt)
        cli.is_dirty(wt)
        cli.is_dirty(wt)

        assert call_count == 1

    def test_has_upstream_caches_result(self, monkeypatch) -> None:
        call_count = 0

        def counting_run_git(args, cwd=None):
            nonlocal call_count
            call_count += 1
            return _ok(stdout="origin/main\n")

        monkeypatch.setattr(cli, "run_git", counting_run_git)

        wt = Worktree(path=Path("/repo/main"), branch="main", commit="abc")
        cli.has_upstream(wt)
        cli.has_upstream(wt)

        assert call_count == 1
