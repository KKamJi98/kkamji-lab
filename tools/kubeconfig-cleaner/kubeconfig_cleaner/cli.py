"""Command-line interface for kubeconfig-cleaner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kubeconfig_cleaner.kubeconfig import (
    DEFAULT_KUBECONFIG,
    backup_file,
    ensure_parent_dir,
    load_yaml,
    prune_unused,
    write_yaml,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kubeconfig-cleaner",
        description=(
            "Clean unused clusters/users from kubeconfig files and optionally merge configs"
        ),
    )
    parser.add_argument(
        "--kubeconfig",
        default=str(DEFAULT_KUBECONFIG),
        help="Path to output kubeconfig file (default: ~/.kube/config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing the file",
    )
    parser.add_argument(
        "--force-empty",
        action="store_true",
        help="Allow pruning when no contexts remain",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    return parser.parse_args(argv)


def format_names(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


def count_items(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)

        output_path = Path(args.kubeconfig).expanduser()

        if not output_path.is_file():
            print(f"Missing kubeconfig file: {output_path}", file=sys.stderr)
            return 1

        config = load_yaml(output_path)
        prune_result = prune_unused(config, allow_empty=args.force_empty)

        print(f"Output kubeconfig: {output_path}")
        print(
            "Contexts: {contexts} | Clusters: {clusters} | Users: {users}".format(
                contexts=count_items(config.get("contexts")),
                clusters=count_items(config.get("clusters")),
                users=count_items(config.get("users")),
            )
        )

        if prune_result.skipped:
            print(
                "No referenced clusters/users found; skipping prune. "
                "Use --force-empty to prune anyway."
            )
        else:
            print(f"Unused clusters removed: {format_names(prune_result.removed_clusters)}")
            print(f"Unused users removed: {format_names(prune_result.removed_users)}")

        if prune_result.missing_clusters or prune_result.missing_users:
            print("Warning: contexts reference missing clusters/users.")
            if prune_result.missing_clusters:
                print(f"  Missing clusters: {format_names(prune_result.missing_clusters)}")
            if prune_result.missing_users:
                print(f"  Missing users: {format_names(prune_result.missing_users)}")

        if args.dry_run:
            print("dry-run enabled: no changes made.")
            return 0

        if output_path.exists():
            backup_path = backup_file(output_path)
            print(f"Backup saved: {backup_path}")
        else:
            ensure_parent_dir(output_path)

        write_yaml(output_path, prune_result.config)
        print("done.")
        return 0

    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
