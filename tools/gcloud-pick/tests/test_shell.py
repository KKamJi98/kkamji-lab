from pathlib import Path

from gcloud_pick.shell import (
    generate_export_commands,
    normalize_shell,
    read_shared_profile,
    shared_profile_path,
    write_shared_profile,
)


def test_normalize_shell():
    assert normalize_shell("/bin/zsh") == "zsh"
    assert normalize_shell("bash") == "bash"
    assert normalize_shell("fish") == "fish"
    assert normalize_shell("dash") == "zsh"  # fallback


def test_export_with_adc_zsh():
    out = generate_export_commands("infra", Path("/h/.config/gcloud/adc/infra@x.json"), "zsh")
    assert out == (
        'export CLOUDSDK_ACTIVE_CONFIG_NAME="infra"\n'
        'export GOOGLE_APPLICATION_CREDENTIALS="/h/.config/gcloud/adc/infra@x.json"'
    )


def test_export_without_adc_unsets_zsh():
    out = generate_export_commands("default", None, "zsh")
    assert out == (
        'export CLOUDSDK_ACTIVE_CONFIG_NAME="default"\nunset GOOGLE_APPLICATION_CREDENTIALS'
    )


def test_export_fish_syntax():
    out = generate_export_commands("infra", None, "fish")
    assert out == (
        'set -gx CLOUDSDK_ACTIVE_CONFIG_NAME "infra"\nset -e GOOGLE_APPLICATION_CREDENTIALS'
    )


def test_shared_profile_roundtrip_with_adc(fake_gcloud_home):
    path = write_shared_profile("infra", Path("/h/adc/infra@x.json"))
    assert path == shared_profile_path()
    assert read_shared_profile() == ("infra", "/h/adc/infra@x.json")


def test_shared_profile_roundtrip_without_adc(fake_gcloud_home):
    write_shared_profile("default", None)
    assert read_shared_profile() == ("default", "")


def test_read_shared_profile_missing_returns_none(fake_gcloud_home):
    assert read_shared_profile() == (None, None)
