"""Generate shell export/unset commands and manage the shared profile file."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUPPORTED = ("bash", "zsh", "fish")


def detect_shell() -> str:
    """Detect the current shell name."""
    shell_path = os.environ.get("SHELL", "")
    if shell_path:
        return os.path.basename(shell_path)
    try:
        result = subprocess.run(
            ["ps", "-p", str(os.getppid()), "-o", "comm="],
            capture_output=True,
            text=True,
            check=True,
        )
        name = result.stdout.strip()
        return os.path.basename(name) if "/" in name else name
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to detect shell: %s", e)
        return "zsh"


def normalize_shell(name: str) -> str:
    """Map a detected shell name to a supported one (default zsh)."""
    base = os.path.basename(name).lower()
    for supported in _SUPPORTED:
        if base.startswith(supported):
            return supported
    return "zsh"


def _export_line(shell: str, var: str, value: str) -> str:
    if shell == "fish":
        return f'set -gx {var} "{value}"'
    return f'export {var}="{value}"'


def _unset_line(shell: str, var: str) -> str:
    if shell == "fish":
        return f"set -e {var}"
    return f"unset {var}"


def generate_export_commands(
    config_name: str, adc_path: Optional[Path], shell_name: Optional[str] = None
) -> str:
    """Return the export/unset lines to switch CLI config and ADC."""
    shell = normalize_shell(shell_name or detect_shell())
    lines = [_export_line(shell, "CLOUDSDK_ACTIVE_CONFIG_NAME", config_name)]
    if adc_path is not None:
        lines.append(_export_line(shell, "GOOGLE_APPLICATION_CREDENTIALS", str(adc_path)))
    else:
        lines.append(_unset_line(shell, "GOOGLE_APPLICATION_CREDENTIALS"))
    return "\n".join(lines)


def shared_profile_path() -> Path:
    """Path to the cross-shell profile file read by the precmd sync hook."""
    return Path.home() / ".config" / "gcloudpick" / "profile"


def _atomic_write_text(target: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_shared_profile(config_name: str, adc_path: Optional[Path]) -> Path:
    """Write '<config>\n<adc-path-or-empty>\n' atomically for cross-shell sync."""
    path = shared_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    second = str(adc_path) if adc_path is not None else ""
    _atomic_write_text(path, f"{config_name}\n{second}\n")
    return path


def read_shared_profile() -> tuple[Optional[str], Optional[str]]:
    """Read (config_name, adc_path) from the shared profile file."""
    path = shared_profile_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, None
    config_name = lines[0].strip() if lines else ""
    adc = lines[1].strip() if len(lines) > 1 else ""
    return (config_name or None), adc
