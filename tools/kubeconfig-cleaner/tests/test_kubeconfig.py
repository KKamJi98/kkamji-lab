from kubeconfig_cleaner.kubeconfig import prune_unused


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
