from kubeconfig_merger.kubeconfig import merge_kubeconfigs


def test_merge_last_wins_on_duplicates():
    config_a = {
        "clusters": [{"name": "c1", "cluster": {"server": "https://a"}}],
        "users": [{"name": "u1", "user": {"token": "a"}}],
        "contexts": [{"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}}],
    }
    config_b = {
        "clusters": [{"name": "c1", "cluster": {"server": "https://b"}}],
        "users": [{"name": "u1", "user": {"token": "b"}}],
        "contexts": [{"name": "ctx1", "context": {"cluster": "c1", "user": "u1"}}],
    }

    result = merge_kubeconfigs([config_a, config_b])
    merged = result.config

    assert result.duplicate_clusters == ["c1"]
    assert result.duplicate_users == ["u1"]
    assert result.duplicate_contexts == ["ctx1"]
    assert merged["clusters"][0]["cluster"]["server"] == "https://b"
    assert merged["users"][0]["user"]["token"] == "b"
