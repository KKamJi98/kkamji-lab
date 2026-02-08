"""Tests for shell backup behavior."""

from pathlib import Path
from unittest.mock import patch

from kube_pick.shell import BACKUP_RETENTION_COUNT, backup_rc_file


@patch("kube_pick.shell.shutil.copy2")
@patch("kube_pick.shell.datetime")
def test_backup_rc_file_rotates_old_backups(mock_datetime, mock_copy, tmp_path):
    """Keep only the latest BACKUP_RETENTION_COUNT backups."""
    mock_datetime.datetime.now.return_value.strftime.return_value = "20250605060000"

    def _copy_side_effect(_src: Path, dst: Path) -> None:
        Path(dst).write_text("new")

    mock_copy.side_effect = _copy_side_effect

    rc_path = tmp_path / ".zshrc"
    rc_path.write_text('export KUBECONFIG="/tmp/kubeconfig"\n')

    for ts in ["20250605055958", "20250605055959", "20250605055960"]:
        (tmp_path / f".zshrc.kubeconfig-bak-{ts}").write_text("old")

    backup_path = backup_rc_file(rc_path)

    backups = sorted(tmp_path.glob(".zshrc.kubeconfig-bak-*"))
    assert backup_path.name == ".zshrc.kubeconfig-bak-20250605060000"
    assert len(backups) == BACKUP_RETENTION_COUNT
    assert backups[0].name == ".zshrc.kubeconfig-bak-20250605055960"
    assert backups[1].name == ".zshrc.kubeconfig-bak-20250605060000"
    mock_copy.assert_called_once_with(rc_path, backup_path)
