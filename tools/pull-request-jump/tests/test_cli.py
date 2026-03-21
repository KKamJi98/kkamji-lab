"""pull_request_jump.cli 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pull_request_jump.cli import (
    PrOpenError,
    RemoteInfo,
    get_default_branch,
    parse_remote_url,
    resolve_provider,
)

# ---------------------------------------------------------------------------
# parse_remote_url
# ---------------------------------------------------------------------------


def test_parse_remote_url_ssh_format():
    """SSH 형식 URL(git@host:owner/repo.git)을 파싱해야 한다."""
    remote = parse_remote_url("git@github.com:octocat/Hello-World.git")

    assert remote.host == "github.com"
    assert remote.owner == "octocat"
    assert remote.repo == "Hello-World"


def test_parse_remote_url_https_format():
    """HTTPS 형식 URL을 파싱해야 한다."""
    remote = parse_remote_url("https://github.com/octocat/Hello-World.git")

    assert remote.host == "github.com"
    assert remote.owner == "octocat"
    assert remote.repo == "Hello-World"
    assert remote.scheme == "https"


def test_parse_remote_url_http_scheme_preserved():
    """http:// 스킴이 있으면 scheme 필드에 http가 저장돼야 한다."""
    remote = parse_remote_url("http://github.example.com/org/repo")

    assert remote.scheme == "http"


def test_parse_remote_url_git_protocol():
    """git:// 형식 URL을 파싱해야 한다."""
    remote = parse_remote_url("git://github.com/octocat/repo.git")

    assert remote.host == "github.com"
    assert remote.repo == "repo"


def test_parse_remote_url_removes_dot_git_suffix():
    """.git suffix가 제거돼야 한다."""
    remote = parse_remote_url("https://github.com/org/myrepo.git")

    assert remote.repo == "myrepo"


def test_parse_remote_url_no_owner_raises():
    """owner/repo 구분이 없는 URL은 PrOpenError를 발생시켜야 한다."""
    with pytest.raises(PrOpenError, match="does not look like a hosted git repository"):
        parse_remote_url("https://github.com/single-segment")


def test_parse_remote_url_ssh_no_colon_raises():
    """콜론 없는 SSH 형식 URL은 PrOpenError를 발생시켜야 한다."""
    with pytest.raises(PrOpenError):
        parse_remote_url("git@github.com/no-colon/repo.git")


def test_parse_remote_url_bitbucket_ssh():
    """Bitbucket SSH URL도 올바르게 파싱돼야 한다."""
    remote = parse_remote_url("git@bitbucket.org:atlassian/stash.git")

    assert remote.host == "bitbucket.org"
    assert remote.owner == "atlassian"
    assert remote.repo == "stash"


# ---------------------------------------------------------------------------
# get_default_branch
# ---------------------------------------------------------------------------


def test_get_default_branch_via_symbolic_ref():
    """symbolic-ref 조회 성공 시 브랜치 이름을 반환해야 한다."""
    with patch("pull_request_jump.cli.run_git") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="refs/remotes/origin/HEAD\n",
        )
        branch = get_default_branch("origin")

    assert branch == "HEAD"


def test_get_default_branch_symbolic_ref_returns_main():
    """symbolic-ref가 refs/remotes/origin/main을 반환하면 'main'이 추출돼야 한다."""
    with patch("pull_request_jump.cli.run_git") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="refs/remotes/origin/main\n",
        )
        branch = get_default_branch("origin")

    assert branch == "main"


def test_get_default_branch_fallback_to_remote_show():
    """symbolic-ref 실패 시 'git remote show'로 fallback해야 한다."""

    def side_effect(args):
        if args[0] == "symbolic-ref":
            return MagicMock(returncode=128, stdout="", stderr="error")
        if args[0] == "remote" and args[1] == "show":
            return MagicMock(
                returncode=0,
                stdout="* remote origin\n  HEAD branch: develop\n",
            )
        return MagicMock(returncode=1, stdout="")

    with patch("pull_request_jump.cli.run_git", side_effect=side_effect):
        branch = get_default_branch("origin")

    assert branch == "develop"


def test_get_default_branch_fallback_to_known_branches():
    """symbolic-ref와 remote show 모두 실패 시 알려진 브랜치를 탐색해야 한다."""

    def side_effect(args):
        if args[0] == "symbolic-ref":
            return MagicMock(returncode=128, stdout="", stderr="error")
        if args[0] == "remote" and args[1] == "show":
            return MagicMock(returncode=128, stdout="", stderr="error")
        if args[0] == "branch" and "-r" in args:
            # 'main' 브랜치가 존재하는 것으로 모킹
            if "origin/main" in args:
                return MagicMock(returncode=0, stdout="  origin/main\n")
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=1, stdout="")

    with patch("pull_request_jump.cli.run_git", side_effect=side_effect):
        branch = get_default_branch("origin")

    assert branch == "main"


def test_get_default_branch_raises_when_all_fallbacks_fail():
    """모든 방법이 실패하면 PrOpenError가 발생해야 한다."""

    def side_effect(args):
        return MagicMock(returncode=128, stdout="", stderr="error")

    with patch("pull_request_jump.cli.run_git", side_effect=side_effect):
        with pytest.raises(PrOpenError, match="Unable to determine default branch"):
            get_default_branch("origin")


# ---------------------------------------------------------------------------
# resolve_provider
# ---------------------------------------------------------------------------


def test_resolve_provider_github_com():
    """github.com 호스트는 GitHub provider를 반환해야 한다."""
    remote = RemoteInfo(host="github.com", owner="org", repo="repo")
    provider = resolve_provider(remote, override=None)

    assert provider.name == "github"


def test_resolve_provider_bitbucket_org():
    """bitbucket.org 호스트는 Bitbucket provider를 반환해야 한다."""
    remote = RemoteInfo(host="bitbucket.org", owner="org", repo="repo")
    provider = resolve_provider(remote, override=None)

    assert provider.name == "bitbucket"


def test_resolve_provider_override_forces_provider():
    """override 파라미터가 있으면 호스트를 무시하고 지정된 provider를 반환해야 한다."""
    remote = RemoteInfo(host="github.example.internal", owner="org", repo="repo")
    provider = resolve_provider(remote, override="github")

    assert provider.name == "github"


def test_resolve_provider_unknown_host_raises():
    """지원하지 않는 호스트이고 override가 없으면 PrOpenError가 발생해야 한다."""
    remote = RemoteInfo(host="gitlab.com", owner="org", repo="repo")

    with pytest.raises(PrOpenError, match="Unsupported host"):
        resolve_provider(remote, override=None)


def test_resolve_provider_invalid_override_raises():
    """지원하지 않는 provider 이름으로 override하면 PrOpenError가 발생해야 한다."""
    remote = RemoteInfo(host="github.com", owner="org", repo="repo")

    with pytest.raises(PrOpenError, match="Unsupported provider"):
        resolve_provider(remote, override="gitlab")


def test_resolve_provider_subdomain_github_enterprise():
    """github.com으로 끝나는 서브도메인(GHE)도 GitHub provider를 반환해야 한다."""
    remote = RemoteInfo(host="github.mycompany.github.com", owner="org", repo="repo")
    provider = resolve_provider(remote, override=None)

    assert provider.name == "github"
