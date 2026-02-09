#!/usr/bin/env python3
"""Open GitHub/Bitbucket Cloud pull request pages."""

from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from urllib.parse import quote, urlparse

from pull_request_jump import __version__


class PrOpenError(Exception):
    """Raised for CLI errors that should be shown to users."""


@dataclass(frozen=True)
class RemoteInfo:
    host: str
    owner: str
    repo: str
    scheme: str = "https"


class Provider:
    name: str

    def build_pr_url(self, remote: RemoteInfo, base: str | None, head: str) -> str:
        raise NotImplementedError


class GitHubProvider(Provider):
    name = "github"

    def build_pr_url(self, remote: RemoteInfo, base: str | None, head: str) -> str:
        if not base:
            raise PrOpenError("GitHub requires a base branch. Use --base to specify one.")
        base_enc = quote(base, safe="")
        head_enc = quote(head, safe="")
        return (
            f"{remote.scheme}://{remote.host}/{remote.owner}/{remote.repo}"
            f"/compare/{base_enc}...{head_enc}"
        )


class BitbucketCloudProvider(Provider):
    name = "bitbucket"

    def build_pr_url(self, remote: RemoteInfo, base: str | None, head: str) -> str:
        head_enc = quote(head, safe="")
        query = f"source={head_enc}"
        if base:
            base_enc = quote(base, safe="")
            query += f"&dest={base_enc}"
        query += "&t=1"
        return (
            f"{remote.scheme}://{remote.host}/{remote.owner}/{remote.repo}"
            f"/pull-requests/new?{query}"
        )


PROVIDERS = {
    "github": GitHubProvider(),
    "bitbucket": BitbucketCloudProvider(),
}


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def get_remote_url(remote: str) -> str:
    result = run_git(["remote", "get-url", remote])
    if result.returncode != 0:
        raise PrOpenError(f"Failed to read remote URL for '{remote}'.")
    url = result.stdout.strip()
    if not url:
        raise PrOpenError(f"Remote '{remote}' has no URL configured.")
    return url


def parse_remote_url(url: str) -> RemoteInfo:
    url = url.strip()
    scheme = "https"

    if "://" in url:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        path = parsed.path
        if parsed.scheme in {"http", "https"}:
            scheme = parsed.scheme
    else:
        if ":" not in url:
            raise PrOpenError("Unsupported remote URL format.")
        user_host, path = url.split(":", 1)
        host = user_host.split("@", 1)[-1]

    if not host:
        raise PrOpenError("Could not parse host from remote URL.")

    path = path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]

    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise PrOpenError("Remote URL does not look like a hosted git repository.")

    owner = "/".join(parts[:-1])
    repo = parts[-1]

    return RemoteInfo(host=host, owner=owner, repo=repo, scheme=scheme)


def get_current_branch() -> str:
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        raise PrOpenError("Failed to detect current branch.")
    branch = result.stdout.strip()
    if branch == "HEAD":
        raise PrOpenError("Detached HEAD. Use --head to specify a branch.")
    return branch


def remote_branch_exists(remote: str, branch: str) -> bool:
    result = run_git(["branch", "-r", "--list", f"{remote}/{branch}"])
    return bool(result.stdout.strip())


def get_default_branch(remote: str) -> str:
    result = run_git(["symbolic-ref", f"refs/remotes/{remote}/HEAD"])
    if result.returncode == 0:
        return result.stdout.strip().split("/")[-1]

    result = run_git(["remote", "show", remote])
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("HEAD branch:"):
                return line.split(":", 1)[1].strip()

    for branch in ("main", "master"):
        if remote_branch_exists(remote, branch):
            return branch

    raise PrOpenError("Unable to determine default branch. Use --base to specify one.")


def resolve_provider(remote: RemoteInfo, override: str | None) -> Provider:
    if override:
        key = override.lower()
    else:
        host = remote.host.lower()
        if host.endswith("github.com"):
            key = "github"
        elif host.endswith("bitbucket.org"):
            key = "bitbucket"
        else:
            raise PrOpenError("Unsupported host. Use --provider github|bitbucket to override.")

    provider = PROVIDERS.get(key)
    if not provider:
        raise PrOpenError("Unsupported provider. Use github or bitbucket.")
    return provider


def cmd_open(args: argparse.Namespace) -> int:
    remote_url = get_remote_url(args.remote)
    remote = parse_remote_url(remote_url)
    provider = resolve_provider(remote, args.provider)

    head = args.head or get_current_branch()

    base: str | None = None
    if provider.name == "github":
        base = args.base or get_default_branch(args.remote)
    else:
        base = args.base

    url = provider.build_pr_url(remote, base, head)

    if args.print:
        print(url)
        return 0

    if not webbrowser.open(url, new=2):
        print(f"Failed to open browser. URL: {url}", file=sys.stderr)
        return 1

    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pr",
        description="Open GitHub/Bitbucket Cloud pull request pages.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    open_parser = subparsers.add_parser("open", help="Open a pull request page")
    open_parser.add_argument("--remote", default="origin", help="Git remote name")
    open_parser.add_argument("--base", help="Base branch (target branch)")
    open_parser.add_argument("--head", help="Head branch (source branch)")
    open_parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS.keys()),
        help="Override provider detection",
    )
    open_parser.add_argument(
        "--print",
        action="store_true",
        help="Print the URL instead of opening the browser",
    )
    open_parser.set_defaults(func=cmd_open)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        parser.exit(1)

    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        return args.func(args)
    except PrOpenError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected errors
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
