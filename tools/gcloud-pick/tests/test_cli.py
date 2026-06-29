import json as _json

import pytest

from gcloud_pick import cli as climod
from gcloud_pick.cli import get_user_selection, parse_args, validate_selection
from gcloud_pick.config import GcloudConfig
from tests.conftest import write_config


def test_parse_args_positional_config():
    args = parse_args(["infra"])
    assert args.config == "infra"
    assert args.login is None


def test_parse_args_login_without_value():
    args = parse_args(["--login"])
    assert args.login == ""


def test_parse_args_login_with_config():
    args = parse_args(["--login", "infra"])
    assert args.login == "infra"


def test_version_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "1.0.0" in out


CONFIGS = [
    GcloudConfig("default", "ethan.kim@bunjang.co.kr", ""),
    GcloudConfig("infra", "infra@bunjang.co.kr", ""),
]


def test_validate_selection_by_number():
    assert validate_selection("2", CONFIGS) == CONFIGS[1]


def test_validate_selection_out_of_range():
    assert validate_selection("9", CONFIGS) is None


def test_validate_selection_exact_name():
    assert validate_selection("infra", CONFIGS) == CONFIGS[1]


def test_validate_selection_unique_partial():
    assert validate_selection("inf", CONFIGS) == CONFIGS[1]


def test_validate_selection_invalid():
    assert validate_selection("zzz", CONFIGS) is None


def test_get_user_selection_valid_number(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "2")
    assert get_user_selection(CONFIGS) == CONFIGS[1]


def test_get_user_selection_quit_cancels(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "q")
    assert get_user_selection(CONFIGS) is None


def test_get_user_selection_empty_cancels(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "")
    assert get_user_selection(CONFIGS) is None


def test_get_user_selection_reprompts_on_invalid(monkeypatch):
    answers = iter(["zzz", "infra"])
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    assert get_user_selection(CONFIGS) == CONFIGS[1]


def test_get_user_selection_eof_cancels(monkeypatch):
    def _raise():
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise)
    assert get_user_selection(CONFIGS) is None


def test_main_direct_switch_with_adc(fake_gcloud_home, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    adc = fake_gcloud_home / "adc" / "infra@bunjang.co.kr.json"
    adc.parent.mkdir(parents=True)
    adc.write_text("{}")

    rc = climod.main(["infra"])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="infra"' in out
    assert f'export GOOGLE_APPLICATION_CREDENTIALS="{adc}"' in out


def test_main_direct_switch_without_adc_unsets(fake_gcloud_home, capsys):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")
    rc = climod.main(["default"])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="default"' in out
    assert "unset GOOGLE_APPLICATION_CREDENTIALS" in out


def test_main_unknown_config_errors(fake_gcloud_home, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    rc = climod.main(["nope"])
    assert rc == 1
    assert capsys.readouterr().out == ""  # nothing on stdout


def test_main_no_configs_errors(fake_gcloud_home):
    assert climod.main([]) == 1


def test_main_interactive_uses_selection(fake_gcloud_home, capsys, monkeypatch):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    monkeypatch.setattr(climod, "get_user_selection", lambda configs: configs[0])
    rc = climod.main([])
    assert rc == 0
    assert 'CLOUDSDK_ACTIVE_CONFIG_NAME="infra"' in capsys.readouterr().out


def test_do_login_saves_per_account_adc(fake_gcloud_home, monkeypatch):
    default_adc = fake_gcloud_home / "application_default_credentials.json"
    default_adc.write_text(_json.dumps({"type": "authorized_user", "refresh_token": "r"}))

    monkeypatch.setattr(climod, "_run_adc_login", lambda: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: "ethan.kim@bunjang.co.kr")

    rc = climod.main(["--login"])
    assert rc == 0
    saved = fake_gcloud_home / "adc" / "ethan.kim@bunjang.co.kr.json"
    assert saved.is_file()
    assert _json.loads(saved.read_text())["type"] == "authorized_user"
    assert (saved.stat().st_mode & 0o777) == 0o600


def test_do_login_warns_on_account_mismatch(fake_gcloud_home, monkeypatch, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    default_adc = fake_gcloud_home / "application_default_credentials.json"
    default_adc.write_text(_json.dumps({"type": "authorized_user"}))
    monkeypatch.setattr(climod, "_run_adc_login", lambda: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: "ethan.kim@bunjang.co.kr")

    rc = climod.main(["--login", "infra"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "mismatch" in err.lower() or "infra@bunjang.co.kr" in err


def test_do_login_fails_when_login_aborts(fake_gcloud_home, monkeypatch):
    monkeypatch.setattr(climod, "_run_adc_login", lambda: 1)
    assert climod.main(["--login"]) == 1


def test_do_login_fails_when_account_unresolved(fake_gcloud_home, monkeypatch):
    (fake_gcloud_home / "application_default_credentials.json").write_text("{}")
    monkeypatch.setattr(climod, "_run_adc_login", lambda: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: None)
    assert climod.main(["--login"]) == 1
