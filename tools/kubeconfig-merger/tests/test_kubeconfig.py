from pathlib import Path

import pytest
import yaml

from kubeconfig_merger.kubeconfig import (
    DuplicateEntryError,
    load_yaml,
    merge_kubeconfigs,
    write_yaml,
)

_CONFIG_A = {
    "clusters": [{"name": "c1", "cluster": {"server": "https://a"}}],
    "users": [{"name": "u1", "user": {"token": "a"}}],
    "contexts": [{"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}}],
}
_CONFIG_B = {
    "clusters": [{"name": "c1", "cluster": {"server": "https://b"}}],
    "users": [{"name": "u1", "user": {"token": "b"}}],
    "contexts": [{"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}}],
}


def test_merge_last_wins_on_duplicates(capsys):
    result = merge_kubeconfigs([_CONFIG_A, _CONFIG_B], strategy="last-wins")
    merged = result.config

    assert result.duplicate_clusters == ["c1"]
    assert result.duplicate_users == ["u1"]
    assert result.duplicate_contexts == ["ctx1"]
    assert merged["clusters"][0]["cluster"]["server"] == "https://b"
    assert merged["users"][0]["user"]["token"] == "b"

    # last-wins must print a WARNING for each overwritten entry
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "c1" in captured.out


def test_merge_skip_keeps_first():
    result = merge_kubeconfigs([_CONFIG_A, _CONFIG_B], strategy="skip")
    merged = result.config

    # First entry must be retained
    assert merged["clusters"][0]["cluster"]["server"] == "https://a"
    assert merged["users"][0]["user"]["token"] == "a"

    # Duplicates are still recorded
    assert result.duplicate_clusters == ["c1"]
    assert result.duplicate_users == ["u1"]
    assert result.duplicate_contexts == ["ctx1"]


def test_merge_error_raises_on_duplicate():
    with pytest.raises(DuplicateEntryError, match="c1"):
        merge_kubeconfigs([_CONFIG_A, _CONFIG_B], strategy="error")


def test_merge_no_duplicates_no_warning(capsys):
    config_x = {
        "clusters": [{"name": "x", "cluster": {"server": "https://x"}}],
        "users": [{"name": "ux", "user": {"token": "x"}}],
        "contexts": [{"name": "ctx-x", "context": {"cluster": "x", "user": "ux"}}],
    }
    config_y = {
        "clusters": [{"name": "y", "cluster": {"server": "https://y"}}],
        "users": [{"name": "uy", "user": {"token": "y"}}],
        "contexts": [{"name": "ctx-y", "context": {"cluster": "y", "user": "uy"}}],
    }
    result = merge_kubeconfigs([config_x, config_y])

    assert result.duplicate_clusters == []
    assert result.duplicate_users == []
    assert result.duplicate_contexts == []

    captured = capsys.readouterr()
    assert "WARNING" not in captured.out


def test_merge_invalid_strategy():
    with pytest.raises(ValueError, match="Invalid strategy"):
        merge_kubeconfigs([_CONFIG_A], strategy="unknown")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 빈 kubeconfig merge
# ---------------------------------------------------------------------------


def test_merge_empty_configs_produces_no_sections():
    """빈 dict 두 개를 merge하면 clusters/users/contexts 키가 존재하지 않아야 한다."""
    result = merge_kubeconfigs([{}, {}])

    assert result.config.get("clusters") is None
    assert result.config.get("users") is None
    assert result.config.get("contexts") is None
    assert result.duplicate_clusters == []
    assert result.duplicate_users == []
    assert result.duplicate_contexts == []


def test_merge_empty_list_sections_produces_empty_lists():
    """clusters/users/contexts 키는 있지만 값이 빈 리스트인 경우 결과도 빈 리스트여야 한다."""
    config = {"clusters": [], "users": [], "contexts": []}
    result = merge_kubeconfigs([config])

    assert result.config["clusters"] == []
    assert result.config["users"] == []
    assert result.config["contexts"] == []


# ---------------------------------------------------------------------------
# current-context 병합 확인
# ---------------------------------------------------------------------------


def test_merge_current_context_last_wins():
    """current-context는 일반 scalar 키이므로 나중 config 값이 이긴다."""
    config_first = {
        "current-context": "ctx-first",
        "clusters": [],
        "users": [],
        "contexts": [],
    }
    config_last = {
        "current-context": "ctx-last",
        "clusters": [],
        "users": [],
        "contexts": [],
    }

    result = merge_kubeconfigs([config_first, config_last])

    assert result.config["current-context"] == "ctx-last"


def test_merge_current_context_preserved_if_only_one():
    """current-context를 가진 config가 하나뿐이면 그 값이 그대로 유지된다."""
    config = {
        "current-context": "my-ctx",
        "clusters": [],
        "users": [],
        "contexts": [],
    }

    result = merge_kubeconfigs([config])

    assert result.config["current-context"] == "my-ctx"


# ---------------------------------------------------------------------------
# 파일 수준 merge_kubeconfigs E2E 테스트
# ---------------------------------------------------------------------------


def _write_kubeconfig(path: Path, data: dict) -> None:
    """헬퍼: dict를 YAML 파일로 기록한다."""
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


def test_e2e_merge_two_kubeconfig_files(tmp_path):
    """두 YAML 파일을 읽고 merge한 뒤 결과를 파일로 저장하면 올바른 내용이 기록된다."""
    file_a = tmp_path / "config-a"
    file_b = tmp_path / "config-b"
    output = tmp_path / "config-merged"

    _write_kubeconfig(
        file_a,
        {
            "apiVersion": "v1",
            "kind": "Config",
            "current-context": "ctx-a",
            "clusters": [{"name": "cluster-a", "cluster": {"server": "https://a"}}],
            "users": [{"name": "user-a", "user": {"token": "tok-a"}}],
            "contexts": [{"name": "ctx-a", "context": {"cluster": "cluster-a", "user": "user-a"}}],
        },
    )
    _write_kubeconfig(
        file_b,
        {
            "apiVersion": "v1",
            "kind": "Config",
            "current-context": "ctx-b",
            "clusters": [{"name": "cluster-b", "cluster": {"server": "https://b"}}],
            "users": [{"name": "user-b", "user": {"token": "tok-b"}}],
            "contexts": [{"name": "ctx-b", "context": {"cluster": "cluster-b", "user": "user-b"}}],
        },
    )

    data_a = load_yaml(file_a)
    data_b = load_yaml(file_b)
    result = merge_kubeconfigs([data_a, data_b])
    write_yaml(output, result.config)

    loaded = load_yaml(output)
    cluster_names = {c["name"] for c in loaded["clusters"]}
    user_names = {u["name"] for u in loaded["users"]}
    context_names = {ctx["name"] for ctx in loaded["contexts"]}

    assert cluster_names == {"cluster-a", "cluster-b"}
    assert user_names == {"user-a", "user-b"}
    assert context_names == {"ctx-a", "ctx-b"}
    # 나중 config(b)의 current-context가 최종값
    assert loaded["current-context"] == "ctx-b"
    assert result.duplicate_clusters == []
