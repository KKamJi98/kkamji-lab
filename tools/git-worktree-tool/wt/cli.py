#!/usr/bin/env python3
"""Git worktree management CLI - fetch, pull, and status across all worktrees."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

try:
    import argcomplete
except ImportError:  # pragma: no cover - optional dependency fallback
    argcomplete = None


# ANSI Colors - disabled when NO_COLOR is set or stdout is not a TTY
def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


class Color:
    RED = ""
    GREEN = ""
    YELLOW = ""
    BLUE = ""
    BOLD = ""
    RESET = ""

    @classmethod
    def init(cls) -> None:
        """Initialize color codes based on terminal capabilities."""
        if _colors_enabled():
            cls.RED = "\033[0;31m"
            cls.GREEN = "\033[0;32m"
            cls.YELLOW = "\033[0;33m"
            cls.BLUE = "\033[0;34m"
            cls.BOLD = "\033[1m"
            cls.RESET = "\033[0m"


@dataclass
class Worktree:
    path: Path
    branch: str
    commit: str
    is_bare: bool = False
    is_detached: bool = False
    _dirty: bool | None = field(default=None, repr=False, compare=False)
    _has_upstream: bool | None = field(default=None, repr=False, compare=False)
    _upstream_ref: str | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class BranchDeleteAssessment:
    status: str
    reason: str
    detail: str = ""
    hint: str = ""


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result.

    Sets LC_ALL=C to ensure consistent English output regardless of user locale.
    """
    env = {**os.environ, "LC_ALL": "C"}
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
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
            # Verify it's a valid git directory. Use --resolve-git-dir rather
            # than --is-bare-repository because the latter returns false when
            # core.bare has been explicitly set to false (e.g. to work around
            # starship's git_status bare-detection bug). The structure is still
            # a valid bare layout regardless of the config flag.
            verify = run_git(["rev-parse", "--resolve-git-dir", str(bare_path)])
            if verify.returncode == 0:
                return bare_path
        current = current.parent

    return None


def _parse_worktree_record(record: dict[str, str]) -> Worktree | None:
    """Parse a single worktree porcelain record into a Worktree, or None if bare/invalid."""
    if "bare" in record:
        return None
    path = Path(record.get("worktree", ""))
    branch = record.get("branch", "").replace("refs/heads/", "")
    commit = record.get("HEAD", "")[:8]

    detached = False
    if not branch and commit:
        branch = f"(detached {commit})"
        detached = True

    if not path.exists():
        return None
    return Worktree(path=path, branch=branch, commit=commit, is_detached=detached)


def get_worktrees(bare_repo: Path) -> list[Worktree]:
    """Get list of all worktrees from the bare repository.

    The bare repo itself is filtered out explicitly. When core.bare is false
    (either historically, or set by cmd_init to work around starship's
    git_status bug), git porcelain no longer tags the bare entry with ``bare``
    — it looks like a regular worktree. Without this filter a ``wt remove``
    run could match the bare dir and destroy the repo.
    """
    result = run_git(["worktree", "list", "--porcelain"], cwd=bare_repo)
    if result.returncode != 0:
        if result.stderr:
            print(f"{Color.RED}FAIL{Color.RESET} worktree list failed: {result.stderr.strip()}")
        return []

    bare_resolved = bare_repo.resolve()
    worktrees: list[Worktree] = []
    current_wt: dict[str, str] = {}

    def _maybe_append(record: dict[str, str]) -> None:
        wt = _parse_worktree_record(record)
        if wt is None:
            return
        if wt.path.resolve() == bare_resolved:
            return
        worktrees.append(wt)

    for line in result.stdout.strip().split("\n"):
        if not line:
            if current_wt:
                _maybe_append(current_wt)
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

    # Handle last worktree (porcelain output may not end with blank line)
    if current_wt:
        _maybe_append(current_wt)

    return worktrees


def is_dirty(wt: Worktree) -> bool:
    """Check if worktree has uncommitted changes. Result is cached on the Worktree."""
    if wt._dirty is not None:
        return wt._dirty
    result = run_git(["status", "--porcelain"], cwd=wt.path)
    if result.returncode != 0:
        wt._dirty = True
        return wt._dirty
    wt._dirty = bool(result.stdout.strip())
    return wt._dirty


def get_upstream_ref(wt: Worktree) -> str | None:
    """Return the configured upstream ref for a worktree branch, if any."""
    if wt._upstream_ref is not None:
        return wt._upstream_ref
    result = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=wt.path)
    if result.returncode != 0:
        return None
    upstream_ref = result.stdout.strip()
    if not upstream_ref:
        return None
    wt._upstream_ref = upstream_ref
    return wt._upstream_ref


def has_upstream(wt: Worktree) -> bool:
    """Check if branch has upstream configured. Result is cached on the Worktree."""
    if wt._has_upstream is not None:
        return wt._has_upstream
    wt._has_upstream = get_upstream_ref(wt) is not None
    return wt._has_upstream


def has_git_ref(repo: Path, ref: str) -> bool:
    """Check if a git ref exists in the given repository/worktree."""
    result = run_git(["rev-parse", "--verify", "--quiet", ref], cwd=repo)
    return result.returncode == 0


def get_sync_status(wt: Worktree) -> str:
    """Get sync status with upstream (ahead/behind)."""
    if wt.is_detached:
        return ""
    upstream_ref = get_upstream_ref(wt)
    if upstream_ref is None:
        return ""
    result = run_git(
        ["rev-list", "--left-right", "--count", f"{wt.branch}...{upstream_ref}"], cwd=wt.path
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


def cmd_status(bare_repo: Path, json_output: bool = False) -> int:
    """Show status of all worktrees."""
    worktrees = get_worktrees(bare_repo)

    if not worktrees:
        if json_output:
            print(json.dumps({"worktrees": [], "summary": {"total": 0, "clean": 0, "dirty": 0}}))
        else:
            print("No worktrees found.")
        return 1

    if json_output:
        items = []
        for wt in worktrees:
            dirty = is_dirty(wt)
            if wt.is_detached:
                sync_status = "detached"
            elif has_upstream(wt):
                sync_status = get_sync_status(wt)
            else:
                sync_status = "no upstream"
            items.append(
                {
                    "branch": wt.branch,
                    "path": str(wt.path),
                    "commit": wt.commit,
                    "status": "dirty" if dirty else "clean",
                    "sync": sync_status,
                    "detached": wt.is_detached,
                }
            )
        dirty_count = sum(1 for i in items if i["status"] == "dirty")
        output = {
            "worktrees": items,
            "summary": {
                "total": len(items),
                "clean": len(items) - dirty_count,
                "dirty": dirty_count,
            },
        }
        print(json.dumps(output, indent=2))
        return 2 if dirty_count > 0 else 0

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

        if wt.is_detached:
            sync_raw = "detached"
        elif has_upstream(wt):
            sync_raw = get_sync_status(wt)
        else:
            sync_raw = "no upstream"
        if sync_raw.startswith("↓"):
            sync = colorize(sync_raw.ljust(14), Color.YELLOW)
        elif sync_raw == "detached":
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


def cmd_prune(bare_repo: Path, dry_run: bool = False) -> int:
    """Prune stale worktree references."""
    args = ["worktree", "prune"]
    if dry_run:
        args.append("--dry-run")

    print(f"{Color.BLUE}Pruning worktree references...{Color.RESET}")
    result = run_git(args, cwd=bare_repo)

    if result.returncode != 0:
        print(f"{Color.RED}FAIL{Color.RESET} prune failed")
        if result.stderr:
            print(result.stderr.strip())
        return 1

    if dry_run:
        if result.stdout.strip():
            print(result.stdout.strip())
        else:
            print(f"{Color.GREEN}OK{Color.RESET} no stale references found")
    else:
        print(f"{Color.GREEN}OK{Color.RESET} pruned stale worktree references")

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

        if wt.is_detached:
            print(f"  {Color.YELLOW}SKIP{Color.RESET} detached HEAD")
            skip_count += 1
            continue

        if is_dirty(wt):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} dirty working tree")
            skip_count += 1
            continue

        upstream_ref = get_upstream_ref(wt)
        if upstream_ref is None:
            print(f"  {Color.YELLOW}SKIP{Color.RESET} no upstream configured")
            skip_count += 1
            continue

        if not has_git_ref(wt.path, upstream_ref):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} upstream ref not found {upstream_ref}")
            skip_count += 1
            continue

        # Snapshot HEAD before sync to detect actual changes
        head_before = run_git(["rev-parse", "HEAD"], cwd=wt.path).stdout.strip()

        if rebase:
            # Try rebase onto remote branch
            result = run_git(["rebase", upstream_ref], cwd=wt.path)
            if result.returncode == 0:
                head_after = run_git(["rev-parse", "HEAD"], cwd=wt.path).stdout.strip()
                if head_before == head_after:
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
            result = run_git(["merge", "--ff-only", upstream_ref], cwd=wt.path)
            if result.returncode == 0:
                head_after = run_git(["rev-parse", "HEAD"], cwd=wt.path).stdout.strip()
                if head_before == head_after:
                    print(f"  {Color.GREEN}OK{Color.RESET} already up to date")
                else:
                    print(f"  {Color.GREEN}OK{Color.RESET} fast-forwarded")
                ok_count += 1
            else:
                print(f"  {Color.RED}FAIL{Color.RESET} cannot fast-forward (diverged?)")
                fail_count += 1

    print()
    print(f"Summary: ok={ok_count} skip={skip_count} fail={fail_count}")

    return 2 if fail_count > 0 or skip_count > 0 else 0


def cmd_list(bare_repo: Path, json_output: bool = False) -> int:
    """List all worktrees."""
    worktrees = get_worktrees(bare_repo)

    if not worktrees:
        if json_output:
            print(json.dumps([]))
        else:
            print("No worktrees found.")
        return 1

    if json_output:
        items = [
            {
                "branch": wt.branch,
                "path": str(wt.path),
                "commit": wt.commit,
                "detached": wt.is_detached,
            }
            for wt in worktrees
        ]
        print(json.dumps(items, indent=2))
        return 0

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


def _is_squash_merged(branch: str, target: str, bare_repo: Path) -> bool:
    """Detect if branch was squash/rebase-merged into target.

    Uses ``git merge-tree --write-tree`` (Git 2.38+) to simulate merging
    *branch* into *target*.  If the resulting tree is identical to *target*'s
    current tree, every change from *branch* is already incorporated — which
    is exactly what happens after a squash or rebase merge on GitHub.
    """
    result = run_git(
        ["merge-tree", "--write-tree", target, branch],
        cwd=bare_repo,
    )
    if result.returncode != 0:
        return False
    merge_tree = result.stdout.strip().split("\n")[0]
    target_tree = run_git(["rev-parse", f"{target}^{{tree}}"], cwd=bare_repo)
    if target_tree.returncode != 0:
        return False
    return merge_tree == target_tree.stdout.strip()


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

        if wt.is_detached:
            print(f"  {Color.YELLOW}SKIP{Color.RESET} detached HEAD")
            skip_count += 1
            continue

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

    return 2 if fail_count > 0 or skip_count > 0 else 0


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


def get_default_remote_ref(bare_repo: Path) -> str | None:
    """Resolve the remote default ref (e.g. ``origin/main``).

    Tries ``git symbolic-ref refs/remotes/origin/HEAD`` first.  When that ref
    is missing — common in bare worktree setups created without
    ``git remote set-head`` — falls back to :func:`get_default_branch` and
    verifies the candidate (``origin/<branch>``) actually exists via
    ``git rev-parse --verify``.

    Returns ``None`` if no default remote ref can be resolved, so callers can
    surface an actionable error instead of crashing on ``origin/HEAD``.
    """
    sym = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=bare_repo)
    if sym.returncode == 0:
        ref = sym.stdout.strip()
        if ref.startswith("refs/remotes/"):
            return ref.removeprefix("refs/remotes/")

    candidate = f"origin/{get_default_branch(bare_repo)}"
    verify = run_git(["rev-parse", "--verify", candidate], cwd=bare_repo)
    if verify.returncode == 0:
        return candidate
    return None


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
    up_result = run_git(
        ["branch", "--set-upstream-to", f"origin/{default_branch}", default_branch],
        cwd=default_wt_path,
    )
    if up_result.returncode != 0:
        print(f"  {Color.YELLOW}WARN{Color.RESET} failed to set upstream for {default_branch}")
    else:
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
            up_result = run_git(
                ["branch", "--set-upstream-to", f"origin/{branch}", branch],
                cwd=wt_path,
            )
            if up_result.returncode != 0:
                print(f"  {Color.YELLOW}WARN{Color.RESET} failed to set upstream for {branch}")
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
                up_result = run_git(
                    ["branch", "--set-upstream-to", f"origin/{branch}", branch],
                    cwd=wt_path,
                )
                if up_result.returncode != 0:
                    print(f"  {Color.YELLOW}WARN{Color.RESET} failed to set upstream for {branch}")
                else:
                    print(f"  {Color.GREEN}OK{Color.RESET} set upstream to origin/{branch}")
                created_branches.add(branch)

    # Work around starship's git_status module treating any repo with
    # core.bare=true as non-renderable, even when operating from a linked
    # worktree. Apply this only after initial worktrees are created; otherwise
    # git treats the .bare directory as using the default branch worktree.
    bare_cfg = run_git(["config", "core.bare", "false"], cwd=bare_path)
    if bare_cfg.returncode != 0:
        print(f"  {Color.YELLOW}WARN{Color.RESET} failed to set core.bare=false")
    else:
        print(f"  {Color.GREEN}OK{Color.RESET} set core.bare=false")

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
    """Add a new worktree for a branch.

    When neither local nor remote branch exists, the branch is created
    automatically (as if ``-c`` were given).  The ``--base`` flag can be
    used with or without ``-c`` to specify the starting point.
    """
    # Determine worktree path
    if path is None:
        # Use branch name, replacing / with -
        wt_name = branch.replace("/", "-")
        wt_path = bare_repo.parent / wt_name
    else:
        wt_path = Path(path).resolve()

    # Check if worktree path already exists
    if wt_path.exists():
        print(f"{Color.RED}Error:{Color.RESET} Path '{wt_path}' already exists.")
        return 1

    # Check if remote/local branch exists
    remote_exists = has_remote_branch(bare_repo, branch)
    local_exists = has_local_branch(bare_repo, branch)

    # Auto-create: if branch doesn't exist anywhere and -c not given, enable create mode
    if not create and not remote_exists and not local_exists:
        create = True
        print(
            f"{Color.YELLOW}Note:{Color.RESET} Branch '{branch}' does not exist."
            " Creating new branch."
        )

    print(f"Adding worktree for branch: {branch}")
    print(f"  Path: {wt_path}")
    if base:
        print(f"  Base: {base}")
    print()

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
        up_result = run_git(
            ["branch", "--set-upstream-to", f"origin/{branch}", branch],
            cwd=wt_path,
        )
        if up_result.returncode != 0:
            print(f"{Color.YELLOW}WARN{Color.RESET} failed to set upstream for {branch}")
        else:
            print(f"{Color.GREEN}OK{Color.RESET} set upstream to origin/{branch}")
    elif create:
        # New branch created, no remote yet
        print()
        print(f"{Color.YELLOW}Note:{Color.RESET} New branch created. To push and set upstream:")
        print(f"  cd {wt_path}")
        print(f"  git push -u origin {branch}")

    return 0


def find_worktrees_by_identifier(worktrees: list[Worktree], identifier: str) -> list[Worktree]:
    """Find matching worktrees by branch/path identifier.

    Priority:
    1. exact branch name
    2. exact path
    3. exact directory name
    4. path suffix
    """
    # Resolve identifier to path if it looks like a path
    identifier_path = None
    if "/" in identifier or identifier.startswith("."):
        identifier_path = Path(identifier).resolve()

    exact_matches: list[Worktree] = []
    dirname_matches: list[Worktree] = []
    suffix_matches: list[Worktree] = []

    for wt in worktrees:
        if wt.branch == identifier:
            exact_matches.append(wt)
            continue

        if identifier_path and wt.path == identifier_path:
            exact_matches.append(wt)
            continue

        if wt.path.name == identifier:
            dirname_matches.append(wt)
            continue

        if str(wt.path).endswith(identifier):
            suffix_matches.append(wt)

    if exact_matches:
        return exact_matches
    if dirname_matches:
        return dirname_matches
    return suffix_matches


def find_worktrees_by_pattern(worktrees: list[Worktree], pattern: str) -> list[Worktree]:
    """Find worktrees by glob pattern on branch, dirname, or full path."""
    matches = []
    for wt in worktrees:
        if (
            fnmatch(wt.branch, pattern)
            or fnmatch(wt.path.name, pattern)
            or fnmatch(str(wt.path), pattern)
        ):
            matches.append(wt)
    return matches


def _force_delete_branch(bare_repo: Path, branch: str, reason: str) -> str:
    """Run ``git branch -D`` for an already-merged branch and report.

    Returns ``"deleted"`` on success, ``"error"`` if git refuses.
    """
    br_result = run_git(["branch", "-D", branch], cwd=bare_repo)
    if br_result.returncode == 0:
        print(f"  {Color.GREEN}OK{Color.RESET} deleted local branch {branch} ({reason})")
        return "deleted"
    print(f"  {Color.RED}FAIL{Color.RESET} branch delete: {br_result.stderr.strip()}")
    return "error"


def _keep_branch(bare_repo: Path, branch: str, reason: str) -> str:
    """Report a branch preserved because it is not merged.

    This is an intentional git safety behaviour, not a failure — the worktree
    is already gone and only the (unmerged) branch is kept. Returns ``"kept"``.
    """
    print(f"  {Color.YELLOW}WARN{Color.RESET} branch kept: {reason}")
    print(
        "    hint: not deleted to avoid losing commits — force with"
        f" `git -C {bare_repo} branch -D {branch}` or `wt rm -f -b {branch}`"
    )
    return "kept"


def _remote_branches_containing(branch: str, bare_repo: Path) -> set[str]:
    """Remote-tracking branches whose history already includes ``branch``'s tip.

    Returns the set of ``origin/*`` refs (excluding ``origin/<branch>`` itself
    and the ``origin/HEAD`` pointer line) that contain the branch tip. A
    non-empty set means the commits are preserved on the remote — e.g. merged
    into ``origin/staging`` in a repo that promotes staging -> prod, so the tip
    is not yet an ancestor of the default branch. Returns an empty set on probe
    failure, so callers fall back to the conservative keep behaviour.
    """
    result = run_git(["branch", "-r", "--contains", branch], cwd=bare_repo)
    if result.returncode != 0:
        return set()
    self_ref = f"origin/{branch}"
    return {
        ref
        for line in result.stdout.splitlines()
        if (ref := line.strip().removeprefix("* ").strip()) and ref != self_ref and "->" not in ref
    }


def _assess_local_branch_delete(
    bare_repo: Path,
    branch: str,
    default_remote_ref: str | None,
) -> BranchDeleteAssessment:
    """Classify whether an unmerged branch can be safely force-deleted."""
    if default_remote_ref is None:
        return BranchDeleteAssessment(
            status="error",
            reason="unable to resolve remote default ref (origin/HEAD)",
            hint=(
                f"run `git -C {bare_repo} remote set-head origin --auto` to initialise origin/HEAD"
            ),
        )

    ref = default_remote_ref
    merged = run_git(["branch", "-r", "--merged", ref], cwd=bare_repo)
    remote_ref = f"origin/{branch}"
    merged_refs: set[str] = set()
    if merged.returncode == 0:
        merged_refs = {
            line.strip().removeprefix("* ").strip()
            for line in merged.stdout.splitlines()
            if line.strip()
        }
    remote_merged = remote_ref in merged_refs

    # Force delete is allowed only when the local tip is already part of <ref>.
    local_ancestor = run_git(["merge-base", "--is-ancestor", branch, ref], cwd=bare_repo)
    if local_ancestor.returncode not in (0, 1):
        return BranchDeleteAssessment(
            status="error",
            reason=f"unable to verify ancestry against {ref}",
            detail=local_ancestor.stderr.strip(),
        )

    if remote_merged and local_ancestor.returncode == 0:
        return BranchDeleteAssessment(status="delete", reason="merged on remote")
    if remote_merged:
        return BranchDeleteAssessment(
            status="keep",
            reason=f"local branch has commits not in {ref}",
        )

    # Remote branch not in merged list — check whether it still exists, but
    # only trust ls-remote on success.
    remote_exists = run_git(["ls-remote", "--heads", "origin", branch], cwd=bare_repo)
    if remote_exists.returncode != 0:
        return BranchDeleteAssessment(
            status="error",
            reason="unable to verify remote branch state",
            detail=remote_exists.stderr.strip(),
        )

    remote_gone = not remote_exists.stdout.strip()
    if remote_gone and local_ancestor.returncode == 0:
        return BranchDeleteAssessment(status="delete", reason="remote branch gone, local merged")
    if remote_gone:
        # The remote feature branch is gone, but the commits may still be
        # preserved on another remote branch — e.g. merged into origin/staging
        # in a repo that promotes staging -> prod, so the tip is not yet an
        # ancestor of the default branch. If so, deleting loses nothing.
        preserved_on = _remote_branches_containing(branch, bare_repo)
        if preserved_on:
            return BranchDeleteAssessment(
                status="delete",
                reason=f"remote branch gone, commits preserved on {', '.join(sorted(preserved_on))}",
            )
        # Common with squash/rebase merge — try merge-tree detection.
        if _is_squash_merged(branch, ref, bare_repo):
            return BranchDeleteAssessment(status="delete", reason="squash-merged")
        return BranchDeleteAssessment(
            status="keep",
            reason=f"remote branch gone, local commits not in {ref}",
        )
    return BranchDeleteAssessment(
        status="keep",
        reason=f"branch exists on origin and not merged into {ref}",
    )


def _print_branch_delete_error(assessment: BranchDeleteAssessment) -> None:
    print(f"  {Color.RED}FAIL{Color.RESET} branch delete: {assessment.reason}")
    if assessment.detail:
        print(f"    {assessment.detail}")
    if assessment.hint:
        print(f"    hint: {assessment.hint}")


def _delete_local_branch(
    bare_repo: Path,
    branch: str,
    force: bool,
    default_remote_ref: str | None,
) -> str:
    """Delete the local branch whose worktree was just removed.

    Returns one of:
    - ``"deleted"``: branch was removed
    - ``"kept"``:    branch safely preserved because it is not merged into the
      default ref (intentional safety, NOT an error)
    - ``"error"``:   deletion failed, or merge state could not be verified
    """
    delete_flag = "-D" if force else "-d"
    br_result = run_git(["branch", delete_flag, branch], cwd=bare_repo)
    if br_result.returncode == 0:
        print(f"  {Color.GREEN}OK{Color.RESET} deleted local branch {branch}")
        return "deleted"

    if force:
        # -D was requested explicitly and still failed → genuine error.
        print(f"  {Color.RED}FAIL{Color.RESET} branch delete: {br_result.stderr.strip()}")
        return "error"

    # Safe delete (-d) refused. Investigate whether the branch is actually
    # merged before deciding between force-delete, keep, or error.
    assessment = _assess_local_branch_delete(bare_repo, branch, default_remote_ref)
    if assessment.status == "delete":
        return _force_delete_branch(bare_repo, branch, assessment.reason)
    if assessment.status == "keep":
        return _keep_branch(bare_repo, branch, assessment.reason)
    _print_branch_delete_error(assessment)
    return "error"


def _describe_remove_dry_run(
    bare_repo: Path,
    wt: Worktree,
    force: bool,
    delete_branch: bool,
    delete_remote: bool,
    default_remote_ref: str | None,
) -> str:
    """Describe what cmd_remove would do without mutating worktrees or branches."""
    message = f"  {wt.branch}: worktree will be removed"
    if not delete_branch or not wt.branch or wt.branch.startswith("(detached"):
        return message

    if force:
        message += " + local branch will be force-deleted"
        if delete_remote:
            message += " + remote branch will be deleted"
        return message

    assessment = _assess_local_branch_delete(bare_repo, wt.branch, default_remote_ref)
    if assessment.status == "delete":
        message += f" + local branch will be deleted ({assessment.reason})"
        if delete_remote:
            message += " + remote branch will be deleted"
    elif assessment.status == "keep":
        message += f" + local branch will be kept ({assessment.reason})"
        if delete_remote:
            message += " + remote branch will be skipped"
    else:
        message += f" + local branch delete cannot be verified ({assessment.reason})"
        if delete_remote:
            message += " + remote branch will be skipped"
    return message


def cmd_remove(
    bare_repo: Path,
    identifiers: list[str],
    force: bool,
    patterns: list[str] | None = None,
    dry_run: bool = False,
    delete_branch: bool = False,
    delete_remote: bool = False,
    yes: bool = False,
) -> int:
    """Remove worktrees by identifier(s) or glob pattern(s)."""
    worktrees = get_worktrees(bare_repo)
    if not worktrees:
        print("No worktrees found.")
        return 1

    patterns = patterns or []
    if not identifiers and not patterns:
        print(f"{Color.RED}Error:{Color.RESET} Please provide identifier(s) or --match pattern(s).")
        return 1

    targets: dict[Path, Worktree] = {}
    missing_identifiers: list[str] = []
    missing_patterns: list[str] = []

    for identifier in identifiers:
        matches = find_worktrees_by_identifier(worktrees, identifier)
        if not matches:
            missing_identifiers.append(identifier)
            continue
        for wt in matches:
            targets[wt.path] = wt

    for pattern in patterns:
        matches = find_worktrees_by_pattern(worktrees, pattern)
        if not matches:
            missing_patterns.append(pattern)
            continue
        for wt in matches:
            targets[wt.path] = wt

    if not targets:
        print(f"{Color.RED}Error:{Color.RESET} No matching worktrees found.")
        if missing_identifiers:
            print(f"  identifiers: {', '.join(missing_identifiers)}")
        if missing_patterns:
            print(f"  patterns: {', '.join(missing_patterns)}")
        print("\nAvailable worktrees:")
        for wt in worktrees:
            print(f"  {wt.branch:<30}  {wt.path}")
        return 1

    target_list = sorted(targets.values(), key=lambda wt: (wt.branch, str(wt.path)))

    print(f"Matched worktrees: {len(target_list)}")
    for wt in target_list:
        print(f"  {wt.branch:<30}  {wt.path}")

    if missing_identifiers:
        print(
            f"{Color.YELLOW}WARN{Color.RESET} no match for identifier(s): {', '.join(missing_identifiers)}"
        )
    if missing_patterns:
        print(
            f"{Color.YELLOW}WARN{Color.RESET} no match for pattern(s): {', '.join(missing_patterns)}"
        )

    if dry_run:
        default_remote_ref: str | None = None
        if delete_branch and not force:
            default_remote_ref = get_default_remote_ref(bare_repo)
        if delete_branch:
            print()
            for wt in target_list:
                print(
                    _describe_remove_dry_run(
                        bare_repo,
                        wt,
                        force,
                        delete_branch,
                        delete_remote,
                        default_remote_ref,
                    )
                )
        print()
        print(f"{Color.GREEN}OK{Color.RESET} dry run complete (no changes made)")
        return 2 if missing_identifiers or missing_patterns else 0

    # Confirmation prompt unless --yes is passed
    if not yes:
        try:
            answer = input(f"\nProceed with removal of {len(target_list)} worktree(s)? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 1
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 1

    # Fetch before branch deletion so local knows about remote merges
    default_remote_ref: str | None = None
    if delete_branch:
        run_git(["fetch", "--all", "--prune"], cwd=bare_repo)
        default_remote_ref = get_default_remote_ref(bare_repo)

    print()

    ok_count = 0
    skip_count = 0
    kept_count = 0
    fail_count = 0

    for wt in target_list:
        print(f"Removing worktree: {wt.branch}")
        print(f"  Path: {wt.path}")

        # Check if dirty
        if not force and is_dirty(wt):
            print(f"  {Color.YELLOW}SKIP{Color.RESET} uncommitted changes (use --force)")
            skip_count += 1
            print()
            continue

        # Remove worktree
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(wt.path))

        result = run_git(args, cwd=bare_repo)
        if result.returncode != 0:
            print(f"  {Color.RED}FAIL{Color.RESET} worktree 제거 실패: {result.stderr.strip()}")
            if delete_branch and wt.branch and not wt.branch.startswith("(detached"):
                print(
                    f"  {Color.YELLOW}SKIP{Color.RESET} worktree 제거 실패로 branch 삭제를 건너뜁니다"
                    f" ({wt.branch})"
                )
            fail_count += 1
            print()
            continue

        print(f"  {Color.GREEN}OK{Color.RESET} removed worktree")
        ok_count += 1

        # Delete local branch if requested
        if delete_branch and wt.branch and not wt.branch.startswith("(detached"):
            branch_status = _delete_local_branch(bare_repo, wt.branch, force, default_remote_ref)
            if branch_status == "error":
                fail_count += 1
            elif branch_status == "kept":
                kept_count += 1

            # Delete remote branch if requested — but never when the local
            # branch was preserved or its deletion failed, otherwise we'd drop
            # the only remaining copy of unmerged commits.
            if delete_remote:
                if branch_status == "deleted":
                    rr = run_git(["push", "origin", "--delete", wt.branch], cwd=bare_repo)
                    if rr.returncode != 0:
                        print(f"  {Color.RED}FAIL{Color.RESET} remote delete: {rr.stderr.strip()}")
                        fail_count += 1
                    else:
                        print(
                            f"  {Color.GREEN}OK{Color.RESET} deleted remote branch origin/{wt.branch}"
                        )
                else:
                    print(
                        f"  {Color.YELLOW}WARN{Color.RESET} skipping remote delete:"
                        f" local branch {wt.branch} was not deleted"
                    )

        print()

    print(f"Summary: ok={ok_count} skip={skip_count} kept={kept_count} fail={fail_count}")
    if (
        fail_count > 0
        or skip_count > 0
        or kept_count > 0
        or missing_identifiers
        or missing_patterns
    ):
        return 2
    return 0


# Argument completers for shell tab-completion


def _substring_validator(completion: str, prefix: str) -> bool:
    """Validate completion by substring match (case-insensitive)."""
    return prefix.lower() in completion.lower()


def _worktree_branch_completer(prefix: str, **kwargs) -> list[str]:
    """Complete branch names from existing worktrees."""
    bare_repo = find_bare_repo()
    if bare_repo is None:
        return []
    worktrees = get_worktrees(bare_repo)
    prefix_lower = prefix.lower()
    return [wt.branch for wt in worktrees if prefix_lower in wt.branch.lower()]


def _worktree_identifier_completer(prefix: str, **kwargs) -> list[str]:
    """Complete worktree identifiers (directory names) with substring matching.

    Returns directory names instead of branch names to avoid shell word-break
    issues caused by ``/`` in branch names (e.g. ``feat/topic``).  The rm
    command resolves directory names via ``find_worktrees_by_identifier``, so
    this is functionally equivalent.
    """
    bare_repo = find_bare_repo()
    if bare_repo is None:
        return []
    worktrees = get_worktrees(bare_repo)
    candidates: list[str] = []
    seen: set[str] = set()
    prefix_lower = prefix.lower()
    for wt in worktrees:
        dirname = wt.path.name
        if dirname not in seen and (
            prefix_lower in dirname.lower() or prefix_lower in wt.branch.lower()
        ):
            candidates.append(dirname)
            seen.add(dirname)
    return candidates


def _remote_branch_completer(prefix: str, **kwargs) -> list[str]:
    """Complete branch names from remote."""
    bare_repo = find_bare_repo()
    if bare_repo is None:
        return []
    result = run_git(["branch", "-r", "--format=%(refname:short)"], cwd=bare_repo)
    if result.returncode != 0:
        return []
    branches = []
    prefix_lower = prefix.lower()
    for line in result.stdout.strip().split("\n"):
        if line.startswith("origin/"):
            branch = line[7:]  # Remove "origin/" prefix
            if branch != "HEAD" and prefix_lower in branch.lower():
                branches.append(branch)
    return branches


def main() -> int:
    Color.init()

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
        help="Base branch to create new branch from",
    ).completer = _remote_branch_completer

    # remove command
    rm_parser = subparsers.add_parser(
        "remove",
        aliases=["rm"],
        help="Remove a worktree (keeps local branch unless -b)",
    )
    rm_parser.add_argument(
        "identifier",
        nargs="*",
        help="Branch/path identifiers to remove (supports multiple)",
    ).completer = _worktree_identifier_completer
    rm_parser.add_argument(
        "-m",
        "--match",
        action="append",
        help="Glob pattern to match branch/path for batch removal (repeatable)",
    )
    rm_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matched worktrees without removing them",
    )
    rm_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force removal even if dirty",
    )
    rm_parser.add_argument(
        "-b",
        "--branch",
        action="store_true",
        help="Also delete the local branch after removing the worktree",
    )
    rm_parser.add_argument(
        "--remote",
        action="store_true",
        help="Also delete remote branch (requires -b/--branch)",
    )
    rm_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    # Existing commands
    status_parser = subparsers.add_parser(
        "status", aliases=["st"], help="Show status of all worktrees"
    )
    status_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output in JSON format"
    )
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
    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List all worktrees")
    list_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output in JSON format"
    )
    subparsers.add_parser(
        "upstream", aliases=["up"], help="Set upstream to origin/<branch> for all worktrees"
    )
    prune_parser = subparsers.add_parser("prune", help="Remove stale worktree references")
    prune_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be pruned without removing"
    )

    # Enable shell tab-completion when argcomplete is installed.
    if argcomplete is not None:
        argcomplete.autocomplete(parser, validator=_substring_validator)

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
        return cmd_status(bare_repo, json_output=args.json_output)
    elif args.command in ("fetch", "f"):
        return cmd_fetch(bare_repo)
    elif args.command in ("pull", "p"):
        return cmd_pull(bare_repo, args.rebase)
    elif args.command in ("list", "ls"):
        return cmd_list(bare_repo, json_output=args.json_output)
    elif args.command in ("upstream", "up"):
        return cmd_upstream(bare_repo)
    elif args.command == "prune":
        return cmd_prune(bare_repo, dry_run=args.dry_run)
    elif args.command in ("add", "a"):
        return cmd_add(bare_repo, args.branch, args.path, args.create, args.base)
    elif args.command in ("remove", "rm"):
        if args.remote and not args.branch:
            print(f"{Color.RED}Error:{Color.RESET} --remote requires -b/--branch flag")
            return 1
        return cmd_remove(
            bare_repo,
            args.identifier,
            args.force,
            args.match,
            args.dry_run,
            args.branch,
            args.remote,
            args.yes,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
