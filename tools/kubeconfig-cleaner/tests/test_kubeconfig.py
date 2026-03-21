import pytest
import yaml

from kubeconfig_cleaner.kubeconfig import backup_file, load_yaml, prune_unused

# ---------------------------------------------------------------------------
# 기존 테스트
# ---------------------------------------------------------------------------


def test_prune_unused_removes_unreferenced():
    config = {
        "contexts": [
            {"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}},
        ],
        "clusters": [{"name": "c1"}, {"name": "c2"}],
        "users": [{"name": "u1"}, {"name": "u2"}],
    }

    result = prune_unused(config, allow_empty=False)

    assert result.removed_clusters == ["c2"]
    assert result.removed_users == ["u2"]
    assert result.skipped is False


def test_prune_skips_without_references():
    config = {
        "contexts": [],
        "clusters": [{"name": "c1"}],
        "users": [{"name": "u1"}],
    }

    result = prune_unused(config, allow_empty=False)

    assert result.skipped is True
    assert result.removed_clusters == []
    assert result.removed_users == []
    assert result.config["clusters"] == [{"name": "c1"}]
    assert result.config["users"] == [{"name": "u1"}]


# ---------------------------------------------------------------------------
# 파일 I/O 실패 시나리오
# ---------------------------------------------------------------------------


def test_backup_file_raises_when_mkdir_fails(tmp_path):
    """backup_dir 생성에 실패하면 PermissionError가 전파되어야 한다."""
    src = tmp_path / "config"
    src.write_text("content", encoding="utf-8")

    unwritable_parent = tmp_path / "no_perm"
    unwritable_parent.mkdir()
    unwritable_parent.chmod(0o555)  # 쓰기 권한 제거

    backup_dir = unwritable_parent / "backup"

    try:
        with pytest.raises((PermissionError, OSError)):
            backup_file(src, backup_dir=backup_dir)
    finally:
        # 테스트 후 권한 복원 (tmp_path cleanup 보장)
        unwritable_parent.chmod(0o755)


# ---------------------------------------------------------------------------
# malformed YAML 처리 — yaml.safe_load가 None 반환
# ---------------------------------------------------------------------------


def test_load_yaml_returns_empty_dict_for_null_yaml(tmp_path):
    """파일이 빈 내용이거나 'null'인 경우 yaml.safe_load는 None을 반환한다.
    load_yaml은 이를 빈 dict로 변환해야 한다."""
    empty_file = tmp_path / "config"
    empty_file.write_text("", encoding="utf-8")

    result = load_yaml(empty_file)

    assert result == {}


def test_load_yaml_raises_for_non_mapping_yaml(tmp_path):
    """YAML root가 list인 경우 ValueError가 발생해야 한다."""
    list_file = tmp_path / "config"
    list_file.write_text(yaml.safe_dump(["item1", "item2"]), encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        load_yaml(list_file)


# ---------------------------------------------------------------------------
# 중복 context 이름 처리
# ---------------------------------------------------------------------------


def test_prune_handles_duplicate_context_names():
    """중복된 context 이름이 있어도 참조된 cluster/user는 정상적으로 보존한다."""
    config = {
        "contexts": [
            {"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}},
            {"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}},  # 중복
        ],
        "clusters": [{"name": "c1"}, {"name": "c2"}],
        "users": [{"name": "u1"}, {"name": "u2"}],
    }

    result = prune_unused(config, allow_empty=False)

    # c1/u1은 참조됨 → 보존, c2/u2는 미참조 → 제거
    assert result.skipped is False
    assert "c2" in result.removed_clusters
    assert "u2" in result.removed_users
    kept_cluster_names = [item["name"] for item in result.config["clusters"]]
    assert "c1" in kept_cluster_names
    assert "c2" not in kept_cluster_names
