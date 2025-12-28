from __future__ import annotations

import datetime as dt
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # PyYAML
except ImportError as exc:  # pragma: no cover - handled in CLI
    raise RuntimeError("PyYAML is required. Install with: pip install PyYAML") from exc

DEFAULT_KUBE_DIR = Path.home() / ".kube"
DEFAULT_BACKUP_DIR = DEFAULT_KUBE_DIR / "config_backup"
DEFAULT_KUBECONFIG = DEFAULT_KUBE_DIR / "config"

BACKUP_SUFFIXES = (".bak", ".backup", ".old", ".tmp", ".swp")


@dataclass
class MergeResult:
    config: dict[str, Any]
    duplicate_clusters: list[str]
    duplicate_users: list[str]
    duplicate_contexts: list[str]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"kubeconfig root must be a mapping (dict): {path}")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def backup_file(path: Path, backup_dir: Path = DEFAULT_BACKUP_DIR) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = backup_dir / f"{path.name}.bak.{timestamp}"
    shutil.copy2(path, backup_path)
    return backup_path


def is_backup_name(name: str) -> bool:
    lower = name.lower()
    if ".bak." in lower or ".backup." in lower:
        return True
    return lower.endswith(BACKUP_SUFFIXES)


def list_kubeconfig_files(kube_dir: Path = DEFAULT_KUBE_DIR) -> list[Path]:
    if not kube_dir.exists():
        return []

    configs: list[Path] = []
    for item in kube_dir.iterdir():
        if not item.is_file():
            continue
        name = item.name
        if "config" not in name.lower():
            continue
        if is_backup_name(name):
            continue
        configs.append(item)

    return sorted(configs, key=lambda p: p.name)


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        expanded = path.expanduser()
        resolved = expanded.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(expanded)
    return result


def dedupe_names(names: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def parse_selection_token(token: str, configs: list[Path]) -> Path | None:
    token = token.strip()
    if not token:
        return None

    if token.isdigit():
        idx = int(token)
        if 1 <= idx <= len(configs):
            return configs[idx - 1]

    for config in configs:
        if token == str(config):
            return config
        if token == config.name or token.lower() == config.name.lower():
            return config

    matches = [c for c in configs if token.lower() in c.name.lower()]
    if len(matches) == 1:
        return matches[0]

    return None


def prompt_for_selection(configs: list[Path]) -> list[Path] | None:
    if not configs:
        return None

    print("Available kubeconfig files:")
    for idx, config in enumerate(configs, 1):
        print(f"  {idx}. {config}")

    while True:
        print("")
        print("Enter numbers or names (comma/space separated), 'all', or 'q' to quit.")
        try:
            selection = input("Selection: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return None

        if not selection:
            print("No selection made.")
            return None
        if selection.lower() in ("q", "quit", "exit"):
            return None

        parts = [part for part in selection.replace(",", " ").split() if part.strip()]
        if not parts:
            print("No selection made.")
            return None

        if any(part.lower() == "all" for part in parts):
            return configs

        selected: list[Path] = []
        invalid: list[str] = []

        for part in parts:
            match = parse_selection_token(part, configs)
            if match:
                selected.append(match)
            else:
                invalid.append(part)

        if invalid:
            print(f"Invalid selection(s): {', '.join(invalid)}")
            continue

        selected = dedupe_paths(selected)
        if selected:
            return selected

        print("No valid selections.")


def merge_named_list(
    items: Any,
    merged: dict[str, dict[str, Any]],
    unnamed: list[dict[str, Any]],
    duplicates: list[str],
) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            if name in merged:
                duplicates.append(name)
                merged.pop(name, None)
            merged[name] = item
        else:
            unnamed.append(item)


def merge_kubeconfigs(configs: Iterable[dict[str, Any]]) -> MergeResult:
    merged_config: dict[str, Any] = {}
    cluster_map: dict[str, dict[str, Any]] = {}
    user_map: dict[str, dict[str, Any]] = {}
    context_map: dict[str, dict[str, Any]] = {}
    unnamed_clusters: list[dict[str, Any]] = []
    unnamed_users: list[dict[str, Any]] = []
    unnamed_contexts: list[dict[str, Any]] = []

    duplicate_clusters: list[str] = []
    duplicate_users: list[str] = []
    duplicate_contexts: list[str] = []

    saw_clusters = False
    saw_users = False
    saw_contexts = False

    for cfg in configs:
        if not isinstance(cfg, dict):
            raise ValueError("kubeconfig root must be a mapping (dict).")

        if "clusters" in cfg:
            saw_clusters = True
        if "users" in cfg:
            saw_users = True
        if "contexts" in cfg:
            saw_contexts = True

        for key, value in cfg.items():
            if key in ("clusters", "users", "contexts"):
                continue
            merged_config[key] = value

        merge_named_list(cfg.get("clusters", []), cluster_map, unnamed_clusters, duplicate_clusters)
        merge_named_list(cfg.get("users", []), user_map, unnamed_users, duplicate_users)
        merge_named_list(cfg.get("contexts", []), context_map, unnamed_contexts, duplicate_contexts)

    if saw_clusters or cluster_map or unnamed_clusters:
        merged_config["clusters"] = list(cluster_map.values()) + unnamed_clusters
    if saw_users or user_map or unnamed_users:
        merged_config["users"] = list(user_map.values()) + unnamed_users
    if saw_contexts or context_map or unnamed_contexts:
        merged_config["contexts"] = list(context_map.values()) + unnamed_contexts

    return MergeResult(
        config=merged_config,
        duplicate_clusters=dedupe_names(duplicate_clusters),
        duplicate_users=dedupe_names(duplicate_users),
        duplicate_contexts=dedupe_names(duplicate_contexts),
    )
