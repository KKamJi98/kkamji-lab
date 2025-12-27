"""Configuration management for kubeconfig files."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console(stderr=True)


def get_kube_dir() -> Path:
    """Get the ~/.kube directory path."""
    return Path.home() / ".kube"


def list_kubeconfig_files() -> list[Path]:
    """
    List all kubeconfig files in ~/.kube directory.

    Returns files containing "config" in the filename (excluding backups).
    """
    kube_dir = get_kube_dir()
    if not kube_dir.exists():
        logger.warning(f"Kube directory not found: {kube_dir}")
        return []

    configs: list[Path] = []

    for item in kube_dir.iterdir():
        if not item.is_file():
            continue
        name = item.name
        # Match: any filename containing "config"
        if "config" in name:
            # Exclude backup files
            if not any(name.endswith(ext) for ext in [".bak", ".backup", ".old", ".tmp"]):
                configs.append(item)

    return sorted(configs, key=lambda p: p.name)


def display_kubeconfig_files(
    configs: list[Path], current_configs: Optional[list[Path]] = None
) -> None:
    """
    Display available kubeconfig files in a table format.

    Args:
        configs: List of kubeconfig file paths
        current_configs: Currently active kubeconfig paths (for highlighting)
    """
    if not configs:
        console.print("[yellow]No kubeconfig files found in ~/.kube[/yellow]")
        return

    current_set = {p.resolve() for p in (current_configs or [])}

    table = Table(title="Available Kubeconfig Files", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="green")
    table.add_column("Status", justify="center", width=10)

    for idx, config in enumerate(configs, 1):
        is_active = config.resolve() in current_set
        status = "[bold green]*[/bold green]" if is_active else ""
        name_style = "bold green" if is_active else "white"
        table.add_row(str(idx), f"[{name_style}]{config.name}[/{name_style}]", status)

    console.print(table)
    if current_set:
        console.print("\n[dim]* = currently active[/dim]")


def validate_selection(selection: str, configs: list[Path]) -> Optional[Path]:
    """
    Validate user selection and return the selected config path.

    Args:
        selection: User input (number or filename)
        configs: List of available configs

    Returns:
        Selected config Path or None if invalid
    """
    selection = selection.strip()

    # Try as number
    try:
        idx = int(selection)
        if 1 <= idx <= len(configs):
            return configs[idx - 1]
    except ValueError:
        pass

    # Try as filename (exact match or partial)
    for config in configs:
        if config.name == selection:
            return config
        if config.name.lower() == selection.lower():
            return config

    # Try partial match
    matches = [c for c in configs if selection.lower() in c.name.lower()]
    if len(matches) == 1:
        return matches[0]

    return None


def get_user_selection(configs: list[Path]) -> Optional[list[Path]]:
    """
    Prompt user to select kubeconfig files.

    Allows multiple selection via comma or space separated values.

    Returns:
        List of selected config paths or None if cancelled
    """
    while True:
        try:
            console.print(
                "\n[cyan]Enter config numbers/names (comma or space separated)[/cyan]",
                highlight=False,
            )
            console.print(
                "[dim]Example: [/dim]"
                "[bold green]1,2,3[/bold green]"
                "[dim] or [/dim]"
                "[bold green]all[/bold green]"
                "[dim] or config config_local[/dim]"
            )
            console.print("[dim]Enter [/dim][bold green]'q'[/bold green][dim] to quit[/dim]\n")

            print("Selection: ", end="", file=sys.stderr, flush=True)
            raw_input = input().strip()

            if not raw_input:
                console.print("[yellow]No selection made.[/yellow]")
                return None

            if raw_input.lower() in ("q", "quit", "exit"):
                logger.info("User cancelled selection")
                return None

            # Parse multiple selections
            # Support both comma and space as separators
            parts = []
            for part in raw_input.replace(",", " ").split():
                part = part.strip()
                if part:
                    parts.append(part)

            if not parts:
                console.print("[yellow]No selection made.[/yellow]")
                return None

            if any(part.lower() == "all" for part in parts):
                return configs

            selected: list[Path] = []
            invalid_selections: list[str] = []

            for part in parts:
                config = validate_selection(part, configs)
                if config:
                    if config not in selected:
                        selected.append(config)
                else:
                    invalid_selections.append(part)

            if invalid_selections:
                console.print(f"[red]Invalid selection(s): {', '.join(invalid_selections)}[/red]")
                continue

            if selected:
                return selected

            console.print("[yellow]No valid selections.[/yellow]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled.[/yellow]")
            return None
        except EOFError:
            return None
