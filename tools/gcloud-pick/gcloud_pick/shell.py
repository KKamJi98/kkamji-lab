"""Generate shell export/unset commands and manage the shared profile file."""

import logging
import os
import subprocess
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
