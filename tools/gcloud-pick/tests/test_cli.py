import pytest

from gcloud_pick.cli import parse_args, validate_selection
from gcloud_pick.config import GcloudConfig


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
