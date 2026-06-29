import json

from gcloud_pick import config as cfgmod
from gcloud_pick.config import (
    GcloudConfig,
    adc_exists,
    adc_path_for,
    current_config,
    gcloud_dir,
    list_configurations,
    resolve_adc_account,
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


def test_resolve_service_account_uses_client_email(fake_gcloud_home, tmp_path):
    adc = tmp_path / "sa.json"
    adc.write_text(
        json.dumps({"type": "service_account", "client_email": "svc@p.iam.gserviceaccount.com"})
    )
    assert resolve_adc_account(adc) == "svc@p.iam.gserviceaccount.com"


def test_resolve_user_cred_uses_token_introspection(fake_gcloud_home, tmp_path, monkeypatch):
    adc = tmp_path / "user.json"
    adc.write_text(json.dumps({"type": "authorized_user", "refresh_token": "x"}))
    monkeypatch.setattr(cfgmod, "_print_adc_access_token", lambda: "tok123")
    monkeypatch.setattr(cfgmod, "_tokeninfo_email", lambda token: "ethan.kim@bunjang.co.kr")
    assert resolve_adc_account(adc) == "ethan.kim@bunjang.co.kr"


def test_resolve_returns_none_when_token_fails(fake_gcloud_home, tmp_path, monkeypatch):
    adc = tmp_path / "user.json"
    adc.write_text(json.dumps({"type": "authorized_user"}))
    monkeypatch.setattr(cfgmod, "_print_adc_access_token", lambda: "")
    assert resolve_adc_account(adc) is None


def test_resolve_returns_none_when_file_missing(fake_gcloud_home, tmp_path):
    assert resolve_adc_account(tmp_path / "nope.json") is None
