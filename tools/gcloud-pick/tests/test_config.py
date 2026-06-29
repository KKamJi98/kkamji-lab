from gcloud_pick.config import (
    GcloudConfig,
    adc_exists,
    adc_path_for,
    current_config,
    gcloud_dir,
    list_configurations,
)
from tests.conftest import set_active, write_config


def test_gcloud_dir_respects_cloudsdk_config(fake_gcloud_home):
    assert gcloud_dir() == fake_gcloud_home


def test_list_configurations_parses_account_project(fake_gcloud_home):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr", project="my-proj")
    configs = list_configurations()
    assert configs == [
        GcloudConfig(name="default", account="ethan.kim@bunjang.co.kr", project=""),
        GcloudConfig(name="infra", account="infra@bunjang.co.kr", project="my-proj"),
    ]


def test_list_configurations_empty_when_none(fake_gcloud_home):
    assert list_configurations() == []


def test_current_config_prefers_env(fake_gcloud_home, monkeypatch):
    set_active(fake_gcloud_home, "infra")
    monkeypatch.setenv("CLOUDSDK_ACTIVE_CONFIG_NAME", "default")
    assert current_config() == "default"


def test_current_config_falls_back_to_active_file(fake_gcloud_home):
    set_active(fake_gcloud_home, "infra")
    assert current_config() == "infra"


def test_adc_path_and_exists(fake_gcloud_home):
    acct = "infra@bunjang.co.kr"
    assert adc_exists(acct) is False
    p = adc_path_for(acct)
    assert p == fake_gcloud_home / "adc" / f"{acct}.json"
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    assert adc_exists(acct) is True
