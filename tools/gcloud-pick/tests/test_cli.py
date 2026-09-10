import json as _json

import pytest

from gcloud_pick import cli as climod
from gcloud_pick.cli import get_user_selection, parse_args, validate_selection
from gcloud_pick.config import GcloudConfig
from tests.conftest import set_active, write_config


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


def test_main_direct_switch_without_adc_unsets(fake_gcloud_home, capsys, monkeypatch):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")
    monkeypatch.setattr(climod, "_prompt_yes_no", lambda q: False)
    rc = climod.main(["default"])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="default"' in out
    assert "unset GOOGLE_APPLICATION_CREDENTIALS" in out


def test_main_switch_prompts_login_and_matches(fake_gcloud_home, capsys, monkeypatch):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")

    from gcloud_pick.config import adc_path_for

    def _fake_do_login(config_name):
        adc = adc_path_for("ethan.kim@bunjang.co.kr")
        adc.parent.mkdir(parents=True, exist_ok=True)
        adc.write_text("{}")
        return 0

    monkeypatch.setattr(climod, "_prompt_yes_no", lambda q: True)
    monkeypatch.setattr(climod, "_do_login", _fake_do_login)

    rc = climod.main(["default"])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="default"' in out
    adc_path = adc_path_for("ethan.kim@bunjang.co.kr")
    assert f'export GOOGLE_APPLICATION_CREDENTIALS="{adc_path}"' in out


def test_main_switch_login_no_matching_file_unsets(fake_gcloud_home, capsys, monkeypatch):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")

    def _fake_do_login_no_file(config_name):
        return 0

    monkeypatch.setattr(climod, "_prompt_yes_no", lambda q: True)
    monkeypatch.setattr(climod, "_do_login", _fake_do_login_no_file)

    rc = climod.main(["default"])
    assert rc == 0
    out = capsys.readouterr().out
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
    monkeypatch.setattr(climod, "_prompt_yes_no", lambda q: False)
    rc = climod.main([])
    assert rc == 0
    assert 'CLOUDSDK_ACTIVE_CONFIG_NAME="infra"' in capsys.readouterr().out


def test_do_login_saves_per_account_adc(fake_gcloud_home, monkeypatch):
    write_config(fake_gcloud_home, "default", account="ethan.kim@bunjang.co.kr")
    set_active(fake_gcloud_home, "default")
    default_adc = fake_gcloud_home / "application_default_credentials.json"
    default_adc.write_text(_json.dumps({"type": "authorized_user", "refresh_token": "r"}))

    monkeypatch.setattr(climod, "_run_adc_login", lambda cfg: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: "ethan.kim@bunjang.co.kr")

    rc = climod.main(["--login"])
    assert rc == 0
    saved = fake_gcloud_home / "adc" / "ethan.kim@bunjang.co.kr.json"
    assert saved.is_file()
    assert _json.loads(saved.read_text())["type"] == "authorized_user"
    assert (saved.stat().st_mode & 0o777) == 0o600
    assert (saved.parent.stat().st_mode & 0o777) == 0o700


def test_do_login_rejects_account_mismatch(fake_gcloud_home, monkeypatch, capsys):
    write_config(fake_gcloud_home, "infra", account="infra@bunjang.co.kr")
    default_adc = fake_gcloud_home / "application_default_credentials.json"
    default_adc.write_text(_json.dumps({"type": "authorized_user"}))
    monkeypatch.setattr(climod, "_run_adc_login", lambda cfg: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: "ethan.kim@bunjang.co.kr")

    rc = climod.main(["--login", "infra"])
    assert rc == 1
    assert not (fake_gcloud_home / "adc").exists()
    err = capsys.readouterr().err
    assert "mismatch" in err.lower() or "infra@bunjang.co.kr" in err


def test_do_login_fails_when_login_aborts(fake_gcloud_home, monkeypatch):
    write_config(fake_gcloud_home, "default", account="user@example.com")
    set_active(fake_gcloud_home, "default")
    monkeypatch.setattr(climod, "_run_adc_login", lambda cfg: 1)
    assert climod.main(["--login"]) == 1


def test_do_login_fails_when_account_unresolved(fake_gcloud_home, monkeypatch):
    write_config(fake_gcloud_home, "default", account="user@example.com")
    set_active(fake_gcloud_home, "default")
    (fake_gcloud_home / "application_default_credentials.json").write_text("{}")
    monkeypatch.setattr(climod, "_run_adc_login", lambda cfg: 0)
    monkeypatch.setattr(climod, "resolve_adc_account", lambda f: None)
    assert climod.main(["--login"]) == 1


@pytest.mark.parametrize("flag", ["-h", "--help", "-help"])
def test_help_is_human_output(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        climod.main(["--shell-state", flag])
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["login"], ["--shell-state", "login"]])
def test_login_alias(argv):
    assert parse_args(argv).login == ""
    assert parse_args([*argv, "infra"]).login == "infra"


def test_double_dash_allows_config_named_login():
    assert parse_args(["--", "login"]).config == "login"


def test_login_conflicting_arguments_fail():
    with pytest.raises(SystemExit) as exc:
        parse_args(["infra", "--login", "default"])
    assert exc.value.code == 2


def test_unknown_login_config_never_authenticates(fake_gcloud_home, monkeypatch):
    def unexpected(cfg):
        pytest.fail("login must validate the configuration before launching gcloud")

    monkeypatch.setattr(climod, "_run_adc_login", unexpected)
    assert climod.main(["login", "missing"]) == 1


def test_combined_login_command_and_environment(monkeypatch):
    import subprocess

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/old/adc.json")
    monkeypatch.setenv("CLOUDSDK_CORE_ACCOUNT", "other@example.com")
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(climod.subprocess, "run", run)
    assert climod._run_adc_login(GcloudConfig("test", "user@example.com", "")) == 0
    argv, kwargs = calls[0]
    assert argv == [
        "gcloud",
        "auth",
        "login",
        "user@example.com",
        "--configuration",
        "test",
        "--update-adc",
    ]
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in kwargs["env"]
    assert "CLOUDSDK_CORE_ACCOUNT" not in kwargs["env"]
    assert kwargs["stdout"] is climod.sys.stderr


def test_shell_state_is_data(fake_gcloud_home, monkeypatch, capsys):
    write_config(fake_gcloud_home, "test", account="user@example.com")
    monkeypatch.setattr(climod, "_prompt_yes_no", lambda q: False)
    assert climod.main(["--shell-state", "test"]) == 0
    assert capsys.readouterr().out == "gcloud-pick-state-v1\ntest\n-\n"


def test_failed_login_preserves_shared_profile(fake_gcloud_home, monkeypatch, capsys):
    from gcloud_pick.shell import shared_profile_path

    write_config(fake_gcloud_home, "test", account="user@example.com")
    profile = shared_profile_path()
    profile.parent.mkdir(parents=True)
    profile.write_text("previous\n\n")
    monkeypatch.setattr(climod, "_run_adc_login", lambda cfg: 1)
    assert climod.main(["login", "test"]) == 1
    assert profile.read_text() == "previous\n\n"
    assert capsys.readouterr().out == ""
