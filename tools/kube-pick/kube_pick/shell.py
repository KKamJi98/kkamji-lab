"""Shell configuration module for updating KUBECONFIG in rc files."""

import datetime
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SYNC_BLOCK_START = "# Added by kube-pick"
SYNC_BLOCK_END = "# End kube-pick"


def get_state_file() -> Path:
    """Get the shared kubeconfig state file path."""
    return Path.home() / ".config" / "kubepick" / "kubeconfig"


def parse_kubeconfig_value(path_str: str) -> list[Path]:
    """Parse colon-separated kubeconfig paths into Path objects."""
    paths: list[Path] = []
    for p in path_str.split(":"):
        p = p.strip()
        if p:
            expanded = Path(os.path.expanduser(p))
            paths.append(expanded)
    return paths


def write_state_file(selected_configs: list[Path]) -> Path:
    """Write the selected kubeconfig paths to the shared state file."""
    state_path = get_state_file()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(":".join(str(p) for p in selected_configs))
    return state_path


class ShellConfig:
    """Shell configuration class to handle different shell types."""

    def __init__(self, name: str, rc_path: Path, export_format: str, comment_prefix: str = "#"):
        self.name = name
        self.rc_path = rc_path
        self.export_format = export_format
        self.comment_prefix = comment_prefix

    def get_kubeconfig_line(self, paths: list[Path]) -> str:
        """
        Generate the KUBECONFIG export line.

        Args:
            paths: List of kubeconfig file paths

        Returns:
            Formatted export line for the shell
        """
        # Join paths with colon separator
        path_str = ":".join(str(p) for p in paths)
        return self.export_format.format(kubeconfig=path_str)

    def get_kubeconfig_pattern(self) -> re.Pattern:
        """Get regex pattern to match KUBECONFIG export line."""
        if self.name == "fish":
            return re.compile(r"^set -[gx] KUBECONFIG\s+.+$", re.MULTILINE)
        else:
            return re.compile(r"^export\s+KUBECONFIG=.+$", re.MULTILINE)

    def get_sync_block(self) -> str:
        """Generate a shell-specific sync block for shared kubeconfig state."""
        state_file = "$HOME/.config/kubepick/kubeconfig"

        if self.name == "fish":
            return "\n".join(
                [
                    SYNC_BLOCK_START,
                    "function kubepick_sync --on-event fish_prompt",
                    f'    set -l f "{state_file}"',
                    "    if test -f $f",
                    "        set -gx KUBECONFIG (cat $f)",
                    "    end",
                    "end",
                    "kubepick_sync",
                    SYNC_BLOCK_END,
                ]
            )

        if self.name == "bash":
            return "\n".join(
                [
                    SYNC_BLOCK_START,
                    "kubepick_sync() {",
                    f'  local f="{state_file}"',
                    '  if [ -f "$f" ]; then',
                    '    export KUBECONFIG="$(cat "$f")"',
                    "  fi",
                    "}",
                    "kubepick_sync",
                    'case ";${PROMPT_COMMAND:-};" in',
                    '  *";kubepick_sync;"*) ;;',
                    '  *) if [[ -n "${PROMPT_COMMAND:-}" ]]; then',
                    '       PROMPT_COMMAND="kubepick_sync;${PROMPT_COMMAND}"',
                    "     else",
                    '       PROMPT_COMMAND="kubepick_sync"',
                    "     fi;;",
                    "esac",
                    SYNC_BLOCK_END,
                ]
            )

        return "\n".join(
            [
                SYNC_BLOCK_START,
                "kubepick_sync() {",
                f'  local f="{state_file}"',
                '  if [ -f "$f" ]; then',
                '    export KUBECONFIG="$(cat "$f")"',
                "  fi",
                "}",
                "kubepick_sync",
                'if [[ -z "${precmd_functions[(r)kubepick_sync]}" ]]; then',
                "  precmd_functions+=(kubepick_sync)",
                "fi",
                SYNC_BLOCK_END,
            ]
        )

    def get_sync_block_pattern(self) -> re.Pattern:
        """Get regex pattern to match kube-pick sync block."""
        start = re.escape(SYNC_BLOCK_START)
        end = re.escape(SYNC_BLOCK_END)
        return re.compile(rf"{start}.*?{end}", re.DOTALL)


def detect_shell() -> str:
    """Detect the current shell."""
    shell_path = os.environ.get("SHELL", "")
    if shell_path:
        shell_name = os.path.basename(shell_path)
        logger.info(f"Detected shell: {shell_name}")
        return shell_name

    try:
        result = subprocess.run(
            ["ps", "-p", str(os.getppid()), "-o", "comm="],
            capture_output=True,
            text=True,
            check=True,
        )
        shell_name = result.stdout.strip()
        if "/" in shell_name:
            shell_name = os.path.basename(shell_name)
        return shell_name
    except Exception as e:
        logger.warning(f"Failed to detect shell: {e}")
        return "zsh"  # Default to zsh on macOS


def get_shell_configs() -> dict[str, ShellConfig]:
    """Get configurations for supported shells."""
    home = Path.home()
    return {
        "bash": ShellConfig("bash", home / ".bashrc", 'export KUBECONFIG="{kubeconfig}"'),
        "zsh": ShellConfig("zsh", home / ".zshrc", 'export KUBECONFIG="{kubeconfig}"'),
        "fish": ShellConfig(
            "fish",
            home / ".config" / "fish" / "config.fish",
            'set -gx KUBECONFIG "{kubeconfig}"',
        ),
    }


def get_rc_path(shell_name: Optional[str] = None) -> tuple[Path, ShellConfig]:
    """
    Get the path to the shell's rc file.

    Returns:
        Tuple of (rc_path, ShellConfig)
    """
    if shell_name is None:
        shell_name = detect_shell()

    shell_configs = get_shell_configs()
    normalized = shell_name.lower()

    for name in shell_configs:
        if normalized.startswith(name):
            shell_config = shell_configs[name]
            logger.info(f"Using {name} configuration at {shell_config.rc_path}")
            return shell_config.rc_path, shell_config

    # Fallback to zsh
    logger.warning(f"Shell '{shell_name}' not recognized, falling back to zsh")
    return shell_configs["zsh"].rc_path, shell_configs["zsh"]


def backup_rc_file(rc_path: Path) -> Path:
    """
    Create a backup of the rc file.

    Returns:
        Path to backup file
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = Path(f"{rc_path}.kubeconfig-bak-{timestamp}")

    shutil.copy2(rc_path, backup_path)
    logger.info(f"Backup created at {backup_path}")

    # Rotate old backups, keep only 5
    backups = sorted(rc_path.parent.glob(f"{rc_path.name}.kubeconfig-bak-*"))
    if len(backups) > 5:
        for old_backup in backups[:-5]:
            try:
                old_backup.unlink()
                logger.info(f"Removed old backup {old_backup}")
            except OSError as e:
                logger.warning(f"Failed to remove old backup {old_backup}: {e}")

    return backup_path


def parse_current_kubeconfig(shell_name: Optional[str] = None) -> list[Path]:
    """
    Parse current KUBECONFIG setting from rc file.

    Returns:
        List of currently configured kubeconfig paths
    """
    state_path = get_state_file()
    if state_path.exists():
        try:
            content = state_path.read_text().strip()
            if not content:
                return []
            return parse_kubeconfig_value(content)
        except Exception as e:
            logger.error(f"Failed to read kube-pick state file: {e}")

    rc_path, shell_config = get_rc_path(shell_name)

    if not rc_path.exists():
        return []

    try:
        content = rc_path.read_text()
        pattern = shell_config.get_kubeconfig_pattern()
        match = pattern.search(content)

        if not match:
            return []

        line = match.group(0)

        # Extract the path value
        if shell_config.name == "fish":
            # set -gx KUBECONFIG "path1:path2"
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                path_str = parts[3].strip("\"'")
            else:
                return []
        else:
            # export KUBECONFIG="path1:path2" or export KUBECONFIG=path1:path2
            eq_pos = line.find("=")
            if eq_pos == -1:
                return []
            path_str = line[eq_pos + 1 :].strip("\"'")

        return parse_kubeconfig_value(path_str)

    except Exception as e:
        logger.error(f"Failed to parse current KUBECONFIG: {e}")
        return []


def update_kubeconfig(
    selected_configs: list[Path], shell_name: Optional[str] = None
) -> tuple[bool, Optional[Path]]:
    """
    Update KUBECONFIG in the shell rc file.

    Args:
        selected_configs: List of kubeconfig paths to set
        shell_name: Shell name (auto-detect if None)

    Returns:
        Tuple of (success, backup_path)
    """
    rc_path, shell_config = get_rc_path(shell_name)

    if not rc_path.exists():
        if shell_config.name == "fish":
            rc_path.parent.mkdir(parents=True, exist_ok=True)
            rc_path.write_text("# Created by kube-pick\n\n")
        else:
            logger.error(f"RC file not found: {rc_path}")
            return False, None

    try:
        write_state_file(selected_configs)
    except Exception as e:
        logger.error(f"Failed to write kube-pick state file: {e}")
        return False, None

    try:
        content = rc_path.read_text()
        pattern = shell_config.get_sync_block_pattern()
        new_block = shell_config.get_sync_block()

        # Check if already set to same value
        match = pattern.search(content)
        if match and match.group(0) == new_block:
            logger.info("kube-pick sync block already up to date, no changes needed")
            return True, None

        # Create backup
        backup_path = backup_rc_file(rc_path)

        if match:
            # Replace existing block
            new_content = pattern.sub(new_block, content)
            logger.info("Replacing existing kube-pick sync block")
        else:
            new_content = content.rstrip() + f"\n\n{new_block}\n"
            logger.info("Adding kube-pick sync block at end of file")

        rc_path.write_text(new_content)
        logger.info(f"Updated {rc_path}")
        return True, backup_path

    except Exception as e:
        logger.error(f"Failed to update KUBECONFIG: {e}")
        return False, None


def generate_export_command(configs: list[Path], shell_name: Optional[str] = None) -> str:
    """Generate the export command for the current shell."""
    _, shell_config = get_rc_path(shell_name)
    return shell_config.get_kubeconfig_line(configs)
