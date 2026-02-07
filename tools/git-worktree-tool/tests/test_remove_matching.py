from pathlib import Path

from wt.cli import Worktree, find_worktrees_by_identifier, find_worktrees_by_pattern


def _wt(branch: str, path: str) -> Worktree:
    return Worktree(path=Path(path), branch=branch, commit="deadbeef")


def test_find_worktrees_by_identifier_prefers_exact_branch_match() -> None:
    worktrees = [
        _wt("provider", "/repo/provider"),
        _wt("fix/provider", "/repo/fix-provider"),
    ]

    matches = find_worktrees_by_identifier(worktrees, "provider")

    assert [wt.branch for wt in matches] == ["provider"]


def test_find_worktrees_by_identifier_path_suffix_supports_multiple_matches() -> None:
    worktrees = [
        _wt("fix/istio-metrics-provider", "/repo/fix-istio-metrics-provider"),
        _wt("fix/tempo-disable-provider", "/repo/fix-tempo-disable-provider"),
        _wt("main", "/repo/main"),
    ]

    matches = find_worktrees_by_identifier(worktrees, "provider")

    assert [wt.branch for wt in matches] == [
        "fix/istio-metrics-provider",
        "fix/tempo-disable-provider",
    ]


def test_find_worktrees_by_pattern_matches_branch_and_path_name() -> None:
    worktrees = [
        _wt("fix/istio-metrics-provider", "/repo/fix-istio-metrics-provider"),
        _wt("feat/new-ui", "/repo/feat-new-ui"),
        _wt("main", "/repo/main"),
    ]

    branch_matches = find_worktrees_by_pattern(worktrees, "fix/*")
    path_matches = find_worktrees_by_pattern(worktrees, "feat-new-*")

    assert [wt.branch for wt in branch_matches] == ["fix/istio-metrics-provider"]
    assert [wt.branch for wt in path_matches] == ["feat/new-ui"]
