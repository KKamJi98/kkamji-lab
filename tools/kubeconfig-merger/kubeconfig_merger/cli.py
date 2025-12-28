"""Command-line interface for kubeconfig-merger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kubeconfig_merger.kubeconfig import (
    DEFAULT_KUBE_DIR,
    DEFAULT_KUBECONFIG,
    backup_file,
    dedupe_paths,
    ensure_parent_dir,
    list_kubeconfig_files,
    load_yaml,
    merge_kubeconfigs,
    prompt_for_selection,
    write_yaml,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kubeconfig-merger",
        description="Merge multiple kubeconfig files into a single output",
    )
    parser.add_argument(
        "--kubeconfig",
        default=str(DEFAULT_KUBECONFIG),
        help="Path to output kubeconfig file (default: ~/.kube/config)",
    )
    parser.add_argument(
        "--merge",
        nargs="+",
        help="One or more kubeconfig files to merge",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Interactively select kubeconfig files from --kube-dir",
    )
    parser.add_argument(
        "--kube-dir",
        default=str(DEFAULT_KUBE_DIR),
        help="Directory to scan for kubeconfig files when using --select",
    )
    parser.add_argument(
        "--current-context",
        help="Override current-context in the output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing the file",
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

        if args.select and args.merge:
            print("error: --select and --merge cannot be used together.", file=sys.stderr)
            return 2
        if not args.select and not args.merge:
            print("error: specify --merge or --select.", file=sys.stderr)
            return 2

        output_path = Path(args.kubeconfig).expanduser()
        kube_dir = Path(args.kube_dir).expanduser()

        if args.select:
            configs = list_kubeconfig_files(kube_dir)
            if not configs:
                print(f"No kubeconfig files found in {kube_dir}", file=sys.stderr)
                return 1
            selected = prompt_for_selection(configs)
            if not selected:
                print("No selection made.", file=sys.stderr)
                return 1
            input_paths = selected
        else:
            input_paths = [Path(path).expanduser() for path in args.merge]

        input_paths = dedupe_paths(input_paths)
        missing = [path for path in input_paths if not path.is_file()]
        if missing:
            print("Missing kubeconfig file(s):", file=sys.stderr)
            for path in missing:
                print(f"  - {path}", file=sys.stderr)
            return 1

        configs = [load_yaml(path) for path in input_paths]
        merge_result = merge_kubeconfigs(configs)
        merged_config = merge_result.config

        if args.current_context:
            merged_config["current-context"] = args.current_context

        print(f"Output kubeconfig: {output_path}")
        print(f"Input configs: {', '.join(str(path) for path in input_paths)}")
        print(
            "Contexts: {contexts} | Clusters: {clusters} | Users: {users}".format(
                contexts=count_items(merged_config.get("contexts")),
                clusters=count_items(merged_config.get("clusters")),
                users=count_items(merged_config.get("users")),
            )
        )

        if merge_result.duplicate_clusters:
            print(
                f"Duplicate clusters (last wins): {format_names(merge_result.duplicate_clusters)}"
            )
        if merge_result.duplicate_users:
            print(f"Duplicate users (last wins): {format_names(merge_result.duplicate_users)}")
        if merge_result.duplicate_contexts:
            print(
                f"Duplicate contexts (last wins): {format_names(merge_result.duplicate_contexts)}"
            )

        if args.dry_run:
            print("dry-run enabled: no changes made.")
            return 0

        if output_path.exists():
            backup_path = backup_file(output_path)
            print(f"Backup saved: {backup_path}")
        else:
            ensure_parent_dir(output_path)

        write_yaml(output_path, merged_config)
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
