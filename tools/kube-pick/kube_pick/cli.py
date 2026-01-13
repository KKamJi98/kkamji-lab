"""Command-line interface for Kube Pick."""

import argparse
import logging
import sys
from typing import Optional

from rich.console import Console

from kube_pick.config import (
    display_kubeconfig_files,
    get_user_selection,
    list_kubeconfig_files,
)
from kube_pick.shell import (
    detect_shell,
    generate_export_command,
    get_rc_path,
    get_state_file,
    parse_current_kubeconfig,
    update_kubeconfig,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

console = Console(stderr=True)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="kubepick",
        description="Kube Pick - Switch kubeconfig files easily",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available kubeconfig files and exit",
    )
    parser.add_argument(
        "-c",
        "--current",
        action="store_true",
        help="Show current KUBECONFIG setting and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    return parser.parse_args(argv)


def show_current_config() -> int:
    """Show current KUBECONFIG setting."""
    current = parse_current_kubeconfig()
    if current:
        console.print("\n[bold cyan]Current KUBECONFIG:[/bold cyan]")
        for path in current:
            exists = path.exists()
            status = "[green]exists[/green]" if exists else "[red]not found[/red]"
            console.print(f"  {path} ({status})")
    else:
        console.print(f"[yellow]No kube-pick state file found at {get_state_file()}[/yellow]")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    try:
        args = parse_args(argv)

        if args.verbose:
            logging.getLogger().setLevel(logging.INFO)

        # List mode
        if args.list:
            configs = list_kubeconfig_files()
            current = parse_current_kubeconfig()
            display_kubeconfig_files(configs, current)
            return 0

        # Current mode
        if args.current:
            return show_current_config()

        # Interactive mode
        configs = list_kubeconfig_files()
        if not configs:
            console.print("[red]No kubeconfig files found in ~/.kube[/red]")
            console.print("[dim]Expected files: *config*[/dim]")
            return 1

        current = parse_current_kubeconfig()
        display_kubeconfig_files(configs, current)

        # Get user selection
        selected = get_user_selection(configs)
        if not selected:
            logger.info("No selection made, exiting")
            return 1

        console.print(f"\n[green]Selected:[/green] {', '.join(c.name for c in selected)}")

        # Detect shell and update rc file
        shell_name = detect_shell()
        rc_path, _ = get_rc_path(shell_name)

        success, backup_path = update_kubeconfig(selected, shell_name)
        if not success:
            console.print("[red]Failed to update KUBECONFIG[/red]")
            return 1

        if backup_path:
            console.print(f"[dim]Backup created: {backup_path}[/dim]")

        console.print(f"[green]Updated {rc_path}[/green]")
        console.print(f"[dim]Synced state: {get_state_file()}[/dim]")

        # Print export command for eval
        export_cmd = generate_export_command(selected, shell_name)
        print(export_cmd)

        console.print(
            "\n[cyan]Run the following to apply in current shell:[/cyan]",
            highlight=False,
        )
        console.print('[bold]eval "$(kubepick)"[/bold]')
        console.print("[dim]Other terminals sync on next prompt[/dim]")
        console.print("[dim]Or: source your rc file[/dim]")

        return 0

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
