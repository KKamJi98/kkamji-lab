from __future__ import annotations

import datetime as dt
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # PyYAML
except ImportError as exc:  # pragma: no cover - handled in CLI
    raise RuntimeError("PyYAML is required. Install with: pip install PyYAML") from exc

DEFAULT_BACKUP_DIR = Path.home() / ".kube" / "config_backup"
DEFAULT_KUBECONFIG = Path.home() / ".kube" / "config"


@dataclass
class PruneResult:
    config: dict[str, Any]
    removed_clusters: list[str]
    removed_users: list[str]
    missing_clusters: list[str]
    missing_users: list[str]
    skipped: bool


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


def collect_references(config: dict[str, Any]) -> tuple[set[str], set[str]]:
    referenced_clusters: set[str] = set()
    referenced_users: set[str] = set()

    contexts = config.get("contexts", [])
    if not isinstance(contexts, list):
        return referenced_clusters, referenced_users

    for item in contexts:
        if not isinstance(item, dict):
            continue
        ctx = item.get("context", {})
        if not isinstance(ctx, dict):
            continue

        cluster_name = ctx.get("cluster")
        user_name = ctx.get("user")

        if isinstance(cluster_name, str) and cluster_name.strip():
            referenced_clusters.add(cluster_name)
        if isinstance(user_name, str) and user_name.strip():
            referenced_users.add(user_name)

    return referenced_clusters, referenced_users


def extract_named_set(items: Any) -> set[str]:
    names: set[str] = set()
    if not isinstance(items, list):
        return names
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            names.add(name)
    return names


def filter_named_list(
    items: list[dict[str, Any]],
    keep_names: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    kept: list[dict[str, Any]] = []
    removed: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            if name in keep_names:
                kept.append(item)
            else:
                removed.append(name)
        else:
            kept.append(item)

    return kept, removed


def prune_unused(config: dict[str, Any], allow_empty: bool = False) -> PruneResult:
    referenced_clusters, referenced_users = collect_references(config)

    if not allow_empty and not referenced_clusters and not referenced_users:
        return PruneResult(
            config=dict(config),
            removed_clusters=[],
            removed_users=[],
            missing_clusters=[],
            missing_users=[],
            skipped=True,
        )

    clusters = config.get("clusters")
    users = config.get("users")

    removed_clusters: list[str] = []
    removed_users: list[str] = []

    cleaned = dict(config)

    if isinstance(clusters, list):
        kept_clusters, removed_clusters = filter_named_list(clusters, referenced_clusters)
        cleaned["clusters"] = kept_clusters

    if isinstance(users, list):
        kept_users, removed_users = filter_named_list(users, referenced_users)
        cleaned["users"] = kept_users

    existing_clusters = extract_named_set(clusters)
    existing_users = extract_named_set(users)
    missing_clusters = sorted(referenced_clusters - existing_clusters)
    missing_users = sorted(referenced_users - existing_users)

    return PruneResult(
        config=cleaned,
        removed_clusters=removed_clusters,
        removed_users=removed_users,
        missing_clusters=missing_clusters,
        missing_users=missing_users,
        skipped=False,
    )
