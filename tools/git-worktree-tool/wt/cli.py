#!/usr/bin/env python3
"""Git worktree management CLI - fetch, pull, and status across all worktrees."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import argcomplete


# ANSI Colors
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[0;34m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


@dataclass
class Worktree:
    path: Path
    branch: str
    commit: str
    is_bare: bool = False


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def find_bare_repo(start_path: Path | None = None) -> Path | None:
    """Find the bare repository from current location.

    Detection strategy:
    1. If inside a worktree, use `git rev-parse --git-common-dir`
    2. Walk up directories looking for `.bare` directory
    """
    if start_path is None:
        start_path = Path.cwd()

    # Try git command first (works if we're inside a worktree)
    result = run_git(["rev-parse", "--git-common-dir"], cwd=start_path)
    if result.returncode == 0:
        git_common_dir = Path(result.stdout.strip())
        if git_common_dir.is_absolute():
            return git_common_dir
        return (start_path / git_common_dir).resolve()

    # Walk up looking for .bare directory
    current = start_path.resolve()
    while current != current.parent:
        bare_path = current / ".bare"
        if bare_path.is_dir():
            return bare_path
        current = current.parent

    return None


def get_worktrees(bare_repo: Path) -> list[Worktree]:
    """Get list of all worktrees from the bare repository."""
    result = run_git(["worktree", "list", "--porcelain"], cwd=bare_repo)
    if result.returncode != 0:
        return []

    worktrees: list[Worktree] = []
    current_wt: dict[str, str] = {}

    for line in result.stdout.strip().split("\n"):
        if not line:
            if current_wt:
                path = Path(current_wt.get("worktree", ""))
                is_bare = "bare" in current_wt
                branch = current_wt.get("branch", "").replace("refs/heads/", "")
                commit = current_wt.get("HEAD", "")[:8]

                # Mark detached HEAD state
                if not branch and commit:
                    branch = f"(detached {commit})"

                if not is_bare and path.exists():
                    worktrees.append(Worktree(path=path, branch=branch, commit=commit))
                current_wt = {}
            continue

        if line.startswith("worktree "):
            current_wt["worktree"] = line[9:]
        elif line.startswith("HEAD "):
            current_wt["HEAD"] = line[5:]
        elif line.startswith("branch "):
            current_wt["branch"] = line[7:]
        elif line == "bare":
            current_wt["bare"] = "true"

    # Handle last worktree
    if current_wt and "bare" not in current_wt:
        path = Path(current_wt.get("worktree", ""))
        branch = current_wt.get("branch", "").replace("refs/heads/", "")
        commit = current_wt.get("HEAD", "")[:8]

        # Mark detached HEAD state
        if not branch and commit:
            branch = f"(detached {commit})"

        if path.exists():
            worktrees.append(Worktree(path=path, branch=branch, commit=commit))

    return worktrees


def is_dirty(wt: Worktree) -> bool:
    """Check if worktree has uncommitted changes."""
    result = run_git(["status", "--porcelain"], cwd=wt.path)
    return bool(result.stdout.strip())


def has_upstream(wt: Worktree) -> bool:
    """Check if branch has upstream configured."""
    result = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=wt.path)
    return result.returncode == 0


def get_sync_status(wt: Worktree) -> str:
    """Get sync status with upstream (ahead/behind)."""
    result = run_git(
        ["rev-list", "--left-right", "--count", f"{wt.branch}...origin/{wt.branch}"], cwd=wt.path
    )
    if result.returncode != 0:
        return ""
    parts = result.stdout.strip().split()
    if len(parts) == 2:
        ahead, behind = int(parts[0]), int(parts[1])
        if ahead > 0 and behind > 0:
            return f"↑{ahead} ↓{behind}"
        if ahead > 0:
            return f"↑{ahead}"
        if behind > 0:
            return f"↓{behind}"
    return "="


def colorize(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{Color.RESET}"


def cmd_status(bare_repo: Path) -> int:
    """Show status of all worktrees."""
    worktrees = get_worktrees(bare_repo)

    if not worktrees:
        print("No worktrees found.")
        return 1

    # Calculate max branch length for alignment
    max_branch_len = max(len(wt.branch) for wt in worktrees)
    max_branch_len = max(max_branch_len, 10)  # minimum 10

    print()
    print(f"{Color.BOLD}{'STATUS':<8} {'BRANCH':<{max_branch_len}} {'SYNC':<14} PATH{Color.RESET}")
    print(f"{'-' * 8} {'-' * max_branch_len} {'-' * 14} {'-' * 30}")

    dirty_count = 0
    for wt in worktrees:
        dirty = is_dirty(wt)
        if dirty:
            dirty_count += 1
            status = colorize("DIRTY".ljust(8), Color.RED)
        else:
            status = colorize("CLEAN".ljust(8), Color.GREEN)

        sync_raw = get_sync_status(wt) if has_upstream(wt) else "no upstream"
        if sync_raw.startswith("↓"):
            sync = colorize(sync_raw.ljust(14), Color.YELLOW)
        else:
            sync = sync_raw.ljust(14)

        print(f"{status} {wt.branch:<{max_branch_len}} {sync} {wt.path}")

    print()
    clean_count = len(worktrees) - dirty_count
    print(
        f"Summary: total={len(worktrees)} {Color.GREEN}clean={clean_count}{Color.RESET} {Color.RED}dirty={dirty_count}{Color.RESET}"
    )

    return 2 if dirty_count > 0 else 0


def cmd_fetch(bare_repo: Path) -> int:
    """Fetch all remotes in bare repository."""
    print(f"{Color.BLUE}Fetching from bare repo: {bare_repo}{Color.RESET}")
    result = run_git(["fetch", "--all", "--prune"], cwd=bare_repo)

    if result.returncode != 0:
        print(f"{Color.RED}FAIL{Color.RESET} fetch failed")
        if result.stderr:
            print(result.stderr)
        return 1

    print(f"{Color.GREEN}OK{Color.RESET} fetch --all --prune completed")
    if result.stderr:  # git fetch outputs to stderr
        print(result.stderr.strip())

    return 0


def cmd_pull(bare_repo: Path, rebase: bool = False) -> int:
    """Pull all worktrees (ff-only by default, rebase with --rebase)."""
    # First fetch
    print(f"{Color.BOLD}Step 1: Fetch{Color.RESET}")
    fetch_result = cmd_fetch(bare_repo)
    if fetch_result != 0:
        return fetch_result

    mode = "Rebase" if rebase else "Sync"
    print()
    print(f"{Color.BOLD}Step 2: {mode} worktrees{Color.RESET}")

    worktrees = get_worktrees(bare_repo)
    if not worktrees:
        print("No worktrees found.")
        return 1

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for wt in worktrees:
        print(f"\n==> {wt.branch} ({wt.path.name})")

        if is_dirty(wt):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} dirty working tree")
            skip_count += 1
            continue

        if not has_upstream(wt):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} no upstream configured")
            skip_count += 1
            continue

        if not has_remote_branch(bare_repo, wt.branch):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} no remote branch origin/{wt.branch}")
            skip_count += 1
            continue

        if rebase:
            # Try rebase onto remote branch
            result = run_git(["rebase", f"origin/{wt.branch}"], cwd=wt.path)
            if result.returncode == 0:
                if "is up to date" in result.stdout or "Current branch" in result.stdout:
                    print(f"  {Color.GREEN}OK{Color.RESET} already up to date")
                else:
                    print(f"  {Color.GREEN}OK{Color.RESET} rebased")
                ok_count += 1
            else:
                # Abort failed rebase
                run_git(["rebase", "--abort"], cwd=wt.path)
                print(f"  {Color.RED}FAIL{Color.RESET} rebase failed (conflict?), aborted")
                fail_count += 1
        else:
            # Try fast-forward merge (default, safe)
            result = run_git(["merge", "--ff-only", f"origin/{wt.branch}"], cwd=wt.path)
            if result.returncode == 0:
                if "Already up to date" in result.stdout:
                    print(f"  {Color.GREEN}OK{Color.RESET} already up to date")
                else:
                    print(f"  {Color.GREEN}OK{Color.RESET} fast-forwarded")
                ok_count += 1
            else:
                print(f"  {Color.RED}FAIL{Color.RESET} cannot fast-forward (diverged?)")
                fail_count += 1

    print()
    print(f"Summary: ok={ok_count} skip={skip_count} fail={fail_count}")

    return 2 if fail_count > 0 else 0


def cmd_list(bare_repo: Path) -> int:
    """List all worktrees."""
    worktrees = get_worktrees(bare_repo)

    if not worktrees:
        print("No worktrees found.")
        return 1

    max_branch_len = max(len(wt.branch) for wt in worktrees)
    for wt in worktrees:
        # Highlight detached HEAD state in yellow
        if wt.branch.startswith("(detached"):
            branch_display = colorize(wt.branch.ljust(max_branch_len), Color.YELLOW)
        else:
            branch_display = wt.branch.ljust(max_branch_len)
        print(f"  {branch_display}  {wt.commit}  {wt.path}")

    return 0


def has_remote_branch(bare_repo: Path, branch: str) -> bool:
    """Check if remote branch exists."""
    result = run_git(["branch", "-r", "--list", f"origin/{branch}"], cwd=bare_repo)
    return bool(result.stdout.strip())


def has_local_branch(bare_repo: Path, branch: str) -> bool:
    """Check if local branch exists."""
    result = run_git(["branch", "--list", branch], cwd=bare_repo)
    return bool(result.stdout.strip())


def cmd_upstream(bare_repo: Path) -> int:
    """Set upstream to origin/<branch> for all worktrees missing upstream."""
    worktrees = get_worktrees(bare_repo)

    if not worktrees:
        print("No worktrees found.")
        return 1

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for wt in worktrees:
        print(f"==> {wt.branch}")

        if has_upstream(wt):
            print(f"  {Color.BLUE}SKIP{Color.RESET} upstream already set")
            skip_count += 1
            continue

        if not has_remote_branch(bare_repo, wt.branch):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} no remote branch origin/{wt.branch}")
            skip_count += 1
            continue

        result = run_git(
            ["branch", "--set-upstream-to", f"origin/{wt.branch}", wt.branch],
            cwd=wt.path,
        )
        if result.returncode == 0:
            print(f"  {Color.GREEN}OK{Color.RESET} set upstream to origin/{wt.branch}")
            ok_count += 1
        else:
            print(f"  {Color.RED}FAIL{Color.RESET} {result.stderr.strip()}")
            fail_count += 1

    print()
    print(f"Summary: ok={ok_count} skip={skip_count} fail={fail_count}")

    return 2 if fail_count > 0 else 0


def get_default_branch(bare_repo: Path) -> str:
    """Get the default branch name from the remote."""
    # Try to get from remote HEAD
    result = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=bare_repo)
    if result.returncode == 0:
        # refs/remotes/origin/main -> main
        return result.stdout.strip().split("/")[-1]

    # Fallback: check if main or master exists
    for branch in ["main", "master"]:
        result = run_git(["branch", "-r", "--list", f"origin/{branch}"], cwd=bare_repo)
        if result.stdout.strip():
            return branch

    return "main"  # default fallback


def cmd_init(repo_url: str, path: str | None, worktrees: list[str] | None) -> int:
    """Initialize a bare repository with worktree structure.

    Creates:
    <path>/
    ├── .bare/           # bare repository
    └── <default-branch>/  # main worktree
    """
    # Determine target path
    if path is None:
        # Extract repo name from URL
        # git@github.com:org/repo.git -> repo
        # https://github.com/org/repo.git -> repo
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        path = repo_name

    target_path = Path(path).resolve()
    bare_path = target_path / ".bare"

    # Check if already exists
    if target_path.exists() and any(target_path.iterdir()):
        print(
            f"{Color.RED}Error:{Color.RESET} Directory '{target_path}' already exists and is not empty."
        )
        return 1

    print(f"{Color.BOLD}Initializing worktree repository{Color.RESET}")
    print(f"  URL:    {repo_url}")
    print(f"  Path:   {target_path}")
    print()

    # Step 1: Clone bare repository
    print(f"{Color.BOLD}Step 1:{Color.RESET} Clone bare repository")
    target_path.mkdir(parents=True, exist_ok=True)

    result = run_git(["clone", "--bare", repo_url, str(bare_path)])
    if result.returncode != 0:
        print(f"  {Color.RED}FAIL{Color.RESET} git clone --bare failed")
        if result.stderr:
            print(f"  {result.stderr.strip()}")
        return 1
    print(f"  {Color.GREEN}OK{Color.RESET} cloned to {bare_path}")

    # Step 2: Configure fetch refspec for all branches
    print()
    print(f"{Color.BOLD}Step 2:{Color.RESET} Configure fetch refspec")
    result = run_git(
        ["config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"],
        cwd=bare_path,
    )
    if result.returncode != 0:
        print(f"  {Color.YELLOW}WARN{Color.RESET} failed to configure fetch refspec")
    else:
        print(f"  {Color.GREEN}OK{Color.RESET} configured fetch refspec")

    # Fetch to get all branches
    result = run_git(["fetch", "--all"], cwd=bare_path)
    if result.returncode == 0:
        print(f"  {Color.GREEN}OK{Color.RESET} fetched all branches")

    # Create .git file pointing to .bare directory
    git_file = target_path / ".git"
    try:
        git_file.write_text("gitdir: ./.bare\n")
        print(f"  {Color.GREEN}OK{Color.RESET} created .git file")
    except OSError as e:
        print(f"  {Color.YELLOW}WARN{Color.RESET} failed to create .git file: {e}")

    # Step 3: Create main worktree
    print()
    print(f"{Color.BOLD}Step 3:{Color.RESET} Create worktrees")

    default_branch = get_default_branch(bare_path)
    print(f"  Default branch: {default_branch}")

    # Create default branch worktree
    default_wt_path = target_path / default_branch
    result = run_git(
        ["worktree", "add", str(default_wt_path), default_branch],
        cwd=bare_path,
    )
    if result.returncode != 0:
        print(f"  {Color.RED}FAIL{Color.RESET} failed to create worktree for {default_branch}")
        if result.stderr:
            print(f"  {result.stderr.strip()}")
        return 1
    print(f"  {Color.GREEN}OK{Color.RESET} created worktree: {default_branch}/")

    # Set upstream for default branch
    run_git(
        ["branch", "--set-upstream-to", f"origin/{default_branch}", default_branch],
        cwd=default_wt_path,
    )
    print(f"  {Color.GREEN}OK{Color.RESET} set upstream to origin/{default_branch}")

    # Step 4: Create common branch worktrees (main, master, staging)
    common_branches = ["main", "master", "staging"]
    created_branches = {default_branch}  # Track created branches to avoid duplicates

    print()
    print(f"{Color.BOLD}Step 4:{Color.RESET} Create common branch worktrees")

    for branch in common_branches:
        if branch in created_branches:
            continue

        if not has_remote_branch(bare_path, branch):
            continue

        wt_path = target_path / branch
        result = run_git(
            ["worktree", "add", str(wt_path), branch],
            cwd=bare_path,
        )
        if result.returncode != 0:
            print(f"  {Color.YELLOW}WARN{Color.RESET} {branch} - {result.stderr.strip()}")
        else:
            print(f"  {Color.GREEN}OK{Color.RESET} created worktree: {branch}/")
            # Set upstream
            run_git(
                ["branch", "--set-upstream-to", f"origin/{branch}", branch],
                cwd=wt_path,
            )
            created_branches.add(branch)

    if len(created_branches) == 1:
        print(f"  {Color.BLUE}INFO{Color.RESET} no additional common branches found on remote")

    # Step 5: Create additional worktrees if specified
    if worktrees:
        print()
        print(f"{Color.BOLD}Step 5:{Color.RESET} Create additional worktrees")
        for branch in worktrees:
            branch = branch.strip()
            if not branch or branch in created_branches:
                continue

            # Determine worktree path (handle nested branches like feat/foo)
            wt_path = target_path / branch.replace("/", "-")

            # Check if remote branch exists
            if not has_remote_branch(bare_path, branch):
                print(f"  {Color.YELLOW}SKIP{Color.RESET} {branch} (no remote branch)")
                continue

            result = run_git(
                ["worktree", "add", str(wt_path), branch],
                cwd=bare_path,
            )
            if result.returncode != 0:
                print(f"  {Color.YELLOW}WARN{Color.RESET} {branch} - {result.stderr.strip()}")
            else:
                print(f"  {Color.GREEN}OK{Color.RESET} created worktree: {wt_path.name}/")
                # Set upstream
                run_git(
                    ["branch", "--set-upstream-to", f"origin/{branch}", branch],
                    cwd=wt_path,
                )
                print(f"  {Color.GREEN}OK{Color.RESET} set upstream to origin/{branch}")
                created_branches.add(branch)

    # Summary
    print()
    print(f"{Color.GREEN}✓ Initialization complete!{Color.RESET}")
    print()
    print("Next steps:")
    print(f"  cd {target_path}/{default_branch}")
    print("  wt status")
    print()
    print("To add more worktrees:")
    print(f"  cd {bare_path}")
    print("  git worktree add ../<branch-name> <branch-name>")

    return 0


def cmd_add(bare_repo: Path, branch: str, path: str | None, create: bool, base: str | None) -> int:
    """Add a new worktree for a branch."""
    # Validate: --base requires --create
    if base and not create:
        print(f"{Color.RED}Error:{Color.RESET} --base requires --create (-c) flag")
        return 1

    # Determine worktree path
    if path is None:
        # Use branch name, replacing / with -
        wt_name = branch.replace("/", "-")
        wt_path = bare_repo.parent / wt_name
    else:
        wt_path = Path(path).resolve()

    print(f"Adding worktree for branch: {branch}")
    print(f"  Path: {wt_path}")
    if base:
        print(f"  Base: {base}")
    print()

    # Check if worktree path already exists
    if wt_path.exists():
        print(f"{Color.RED}Error:{Color.RESET} Path '{wt_path}' already exists.")
        return 1

    # Check if remote branch exists (for tracking)
    remote_exists = has_remote_branch(bare_repo, branch)

    if create:
        # Create new branch and worktree
        if base:
            # Create new branch from specified base branch
            # First check if base branch exists (local or remote)
            base_ref = base
            if has_remote_branch(bare_repo, base):
                base_ref = f"origin/{base}"
            result = run_git(
                ["worktree", "add", "-b", branch, str(wt_path), base_ref],
                cwd=bare_repo,
            )
        elif remote_exists:
            # Branch exists on remote, create tracking branch
            result = run_git(
                ["worktree", "add", "--track", "-b", branch, str(wt_path), f"origin/{branch}"],
                cwd=bare_repo,
            )
        else:
            # Create new branch from current HEAD
            result = run_git(
                ["worktree", "add", "-b", branch, str(wt_path)],
                cwd=bare_repo,
            )
    else:
        # Checkout existing branch
        local_exists = has_local_branch(bare_repo, branch)

        if remote_exists and not local_exists:
            # Remote exists but local doesn't - create tracking branch
            result = run_git(
                ["worktree", "add", "--track", "-b", branch, str(wt_path), f"origin/{branch}"],
                cwd=bare_repo,
            )
        else:
            # Checkout existing local branch
            result = run_git(
                ["worktree", "add", str(wt_path), branch],
                cwd=bare_repo,
            )

    if result.returncode != 0:
        print(f"{Color.RED}FAIL{Color.RESET} {result.stderr.strip()}")
        return 1

    print(f"{Color.GREEN}OK{Color.RESET} created worktree at {wt_path}")

    # Set upstream if remote exists
    if remote_exists:
        run_git(
            ["branch", "--set-upstream-to", f"origin/{branch}", branch],
            cwd=wt_path,
        )
        print(f"{Color.GREEN}OK{Color.RESET} set upstream to origin/{branch}")
    elif create:
        # New branch created, no remote yet
        print()
        print(f"{Color.YELLOW}Note:{Color.RESET} New branch created. To push and set upstream:")
        print(f"  cd {wt_path}")
        print(f"  git push -u origin {branch}")

    return 0


def cmd_remove(bare_repo: Path, identifier: str, force: bool) -> int:
    """Remove a worktree by branch name or path."""
    worktrees = get_worktrees(bare_repo)

    # Resolve identifier to path if it looks like a path
    identifier_path = None
    if "/" in identifier or identifier.startswith("."):
        identifier_path = Path(identifier).resolve()

    # Find worktree by branch name or path
    target_wt = None
    for wt in worktrees:
        # Match by branch name
        if wt.branch == identifier:
            target_wt = wt
            break
        # Match by exact path
        if identifier_path and wt.path == identifier_path:
            target_wt = wt
            break
        # Match by directory name or path suffix
        if wt.path.name == identifier or str(wt.path).endswith(identifier):
            target_wt = wt
            break

    if target_wt is None:
        print(f"{Color.RED}Error:{Color.RESET} No worktree found for '{identifier}'")
        print("\nAvailable worktrees:")
        for wt in worktrees:
            print(f"  {wt.branch:<30}  {wt.path}")
        return 1

    print(f"Removing worktree: {target_wt.branch}")
    print(f"  Path: {target_wt.path}")
    print()

    # Check if dirty
    if not force and is_dirty(target_wt):
        print(f"{Color.RED}Error:{Color.RESET} Worktree has uncommitted changes.")
        print("Use --force to remove anyway.")
        return 1

    # Remove worktree
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(target_wt.path))

    result = run_git(args, cwd=bare_repo)
    if result.returncode != 0:
        print(f"{Color.RED}FAIL{Color.RESET} {result.stderr.strip()}")
        return 1

    print(f"{Color.GREEN}OK{Color.RESET} removed worktree")
    return 0


# Argument completers for shell tab-completion
def _worktree_branch_completer(prefix: str, **kwargs) -> list[str]:
    """Complete branch names from existing worktrees."""
    bare_repo = find_bare_repo()
    if bare_repo is None:
        return []
    worktrees = get_worktrees(bare_repo)
    return [wt.branch for wt in worktrees if wt.branch.startswith(prefix)]


def _remote_branch_completer(prefix: str, **kwargs) -> list[str]:
    """Complete branch names from remote."""
    bare_repo = find_bare_repo()
    if bare_repo is None:
        return []
    result = run_git(["branch", "-r", "--format=%(refname:short)"], cwd=bare_repo)
    if result.returncode != 0:
        return []
    branches = []
    for line in result.stdout.strip().split("\n"):
        if line.startswith("origin/"):
            branch = line[7:]  # Remove "origin/" prefix
            if branch != "HEAD" and branch.startswith(prefix):
                branches.append(branch)
    return branches


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wt",
        description="Git worktree management CLI - manage multiple worktrees from anywhere",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command - does not require existing bare repo
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new bare repository with worktree structure",
    )
    init_parser.add_argument("repo_url", help="Git repository URL to clone")
    init_parser.add_argument("path", nargs="?", help="Target directory (default: repo name)")
    init_parser.add_argument(
        "-w",
        "--worktrees",
        help="Additional branches to create worktrees for (comma-separated)",
    )

    # add command
    add_parser = subparsers.add_parser("add", aliases=["a"], help="Add a new worktree")
    add_parser.add_argument("branch", help="Branch name").completer = _remote_branch_completer
    add_parser.add_argument("path", nargs="?", help="Worktree path (default: ../<branch>)")
    add_parser.add_argument(
        "-c",
        "--create",
        action="store_true",
        help="Create new branch if it doesn't exist",
    )
    add_parser.add_argument(
        "-b",
        "--base",
        help="Base branch to create new branch from (requires -c)",
    ).completer = _remote_branch_completer

    # remove command
    rm_parser = subparsers.add_parser("remove", aliases=["rm"], help="Remove a worktree")
    rm_parser.add_argument(
        "identifier", help="Branch name or path of the worktree to remove"
    ).completer = _worktree_branch_completer
    rm_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force removal even if dirty",
    )

    # Existing commands
    subparsers.add_parser("status", aliases=["st"], help="Show status of all worktrees")
    subparsers.add_parser(
        "fetch", aliases=["f"], help="Fetch all remotes (git fetch --all --prune)"
    )
    pull_parser = subparsers.add_parser("pull", aliases=["p"], help="Fetch and sync all worktrees")
    pull_parser.add_argument(
        "-r",
        "--rebase",
        action="store_true",
        help="Use rebase instead of fast-forward merge",
    )
    subparsers.add_parser("list", aliases=["ls"], help="List all worktrees")
    subparsers.add_parser(
        "upstream", aliases=["up"], help="Set upstream to origin/<branch> for all worktrees"
    )

    # Enable shell tab-completion
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Handle init command separately (doesn't need existing bare repo)
    if args.command == "init":
        worktrees_list = None
        if args.worktrees:
            worktrees_list = [b.strip() for b in args.worktrees.split(",")]
        return cmd_init(args.repo_url, args.path, worktrees_list)

    # Find bare repository for other commands
    bare_repo = find_bare_repo()
    if bare_repo is None:
        print(f"{Color.RED}Error:{Color.RESET} Not inside a git worktree repository.")
        print()
        print("To initialize a new repository:")
        print("  wt init <repo-url> [path]")
        print()
        print("Or run this command from within an existing worktree directory.")
        return 1

    print(f"{Color.BOLD}Bare repo:{Color.RESET} {bare_repo}")
    print()

    if args.command in ("status", "st"):
        return cmd_status(bare_repo)
    elif args.command in ("fetch", "f"):
        return cmd_fetch(bare_repo)
    elif args.command in ("pull", "p"):
        return cmd_pull(bare_repo, args.rebase)
    elif args.command in ("list", "ls"):
        return cmd_list(bare_repo)
    elif args.command in ("upstream", "up"):
        return cmd_upstream(bare_repo)
    elif args.command in ("add", "a"):
        return cmd_add(bare_repo, args.branch, args.path, args.create, args.base)
    elif args.command in ("remove", "rm"):
        return cmd_remove(bare_repo, args.identifier, args.force)

    return 0


if __name__ == "__main__":
    sys.exit(main())
