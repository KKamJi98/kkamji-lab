"""Command-line interface for gcloud-pick."""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from gcloud_pick import __version__
from gcloud_pick.config import (
    GcloudConfig,
    adc_exists,
    adc_path_for,
    current_config,
    gcloud_dir,
    list_configurations,
    resolve_adc_account,
)
from gcloud_pick.shell import generate_export_commands, write_shared_profile

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

console = Console(stderr=True)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gcloud-pick",
        description="gcloud-pick - switch gcloud CLI auth and ADC together",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help="Configuration to switch to (skips the interactive picker)",
    )
    parser.add_argument(
        "--login",
        nargs="?",
        const="",
        default=None,
        metavar="CONFIG",
        help="Run ADC login and save a per-account ADC file (optionally verify against CONFIG)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def display_configurations(configs: list[GcloudConfig], current: Optional[str]) -> None:
    """Render the available gcloud configurations as a table to stderr."""
    table = Table(title="gcloud configurations", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Config", style="green")
    table.add_column("Account", style="white")
    table.add_column("Project", style="dim")
    table.add_column("ADC", justify="center", width=5)

    for idx, cfg in enumerate(configs, 1):
        active = cfg.name == current
        marker = "[bold green]*[/bold green]" if active else ""
        name_style = "bold green" if active else "green"
        adc_mark = "[green]ok[/green]" if adc_exists(cfg.account) else "[red]-[/red]"
        table.add_row(
            f"{idx}{marker}",
            f"[{name_style}]{cfg.name}[/{name_style}]",
            cfg.account or "[dim](none)[/dim]",
            cfg.project or "",
            adc_mark,
        )
    console.print(table)
    console.print("[dim]* = current. ADC ok = saved per-account file exists.[/dim]")


def validate_selection(selection: str, configs: list[GcloudConfig]) -> Optional[GcloudConfig]:
    """Resolve a selection (number, exact name, or unique partial) to a config."""
    selection = selection.strip()
    if not selection:
        return None
    try:
        idx = int(selection)
        if 1 <= idx <= len(configs):
            return configs[idx - 1]
        return None
    except ValueError:
        pass
    for cfg in configs:
        if cfg.name == selection or cfg.name.lower() == selection.lower():
            return cfg
    matches = [c for c in configs if selection.lower() in c.name.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def get_user_selection(configs: list[GcloudConfig]) -> Optional[GcloudConfig]:
    """Prompt for a configuration selection (number or name)."""
    while True:
        try:
            print("Select config (number/name, q to quit): ", end="", file=sys.stderr, flush=True)
            raw = input().strip()
            if not raw or raw.lower() in ("q", "quit", "exit"):
                return None
            cfg = validate_selection(raw, configs)
            if cfg:
                return cfg
            console.print("[red]Invalid selection.[/red]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return None


def _prompt_yes_no(question: str) -> bool:
    """Print question to stderr, return True only if user answers y/yes. Safe in non-interactive contexts."""
    try:
        print(f"{question} [y/N]: ", end="", file=sys.stderr, flush=True)
        answer = input().strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _run_adc_login() -> int:
    """Run the interactive ADC login. Returns the gcloud exit code."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "login"],
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"[red]Failed to run gcloud: {e}[/red]")
        return 1
    return result.returncode


def _do_login(config_name: str) -> int:
    """Run ADC login and save a per-account ADC file."""
    if _run_adc_login() != 0:
        console.print("[red]ADC login failed or was cancelled.[/red]")
        return 1

    default_adc = gcloud_dir() / "application_default_credentials.json"
    account = resolve_adc_account(default_adc)
    if not account:
        console.print("[red]Could not resolve the ADC account after login.[/red]")
        return 1

    if config_name:
        cfg = validate_selection(config_name, list_configurations())
        if cfg and cfg.account and cfg.account != account:
            console.print(
                f"[yellow]Account mismatch: ADC logged in as {account}, "
                f"but config '{config_name}' uses {cfg.account}.[/yellow]"
            )

    dest = adc_path_for(account)
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(dest.parent, 0o700)
    shutil.copy2(default_adc, dest)
    os.chmod(dest, 0o600)
    console.print(f"[green]Saved ADC for {account}[/green] [dim]-> {dest}[/dim]")
    return 0


def _switch(cfg: GcloudConfig) -> int:
    """Write the shared profile and print export commands for a configuration."""
    if cfg.account and adc_exists(cfg.account):
        adc_path = adc_path_for(cfg.account)
    elif cfg.account and _prompt_yes_no(f"Set up ADC for {cfg.account} now? (opens gcloud login)"):
        _do_login(cfg.name)
        if adc_exists(cfg.account):
            adc_path = adc_path_for(cfg.account)
        else:
            adc_path = None
            console.print(
                "[yellow]ADC login did not produce a matching credential. Falling back to default ADC.[/yellow]"
            )
    else:
        adc_path = None
        console.print(
            f"[yellow]No saved ADC file for account '{cfg.account or '(none)'}'. "
            f"ADC will fall back to the default credentials.[/yellow]"
        )
        console.print(f"[dim]Run 'gp --login {cfg.name}' to create one.[/dim]")

    write_shared_profile(cfg.name, adc_path)
    print(generate_export_commands(cfg.name, adc_path))

    account = cfg.account or "(none)"
    console.print(f"[green]Switched to[/green] [bold]{cfg.name}[/bold] [dim]({account})[/dim]")
    console.print("[dim]Other terminals sync on next prompt.[/dim]")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    try:
        args = parse_args(argv)

        if args.login is not None:
            return _do_login(args.login)

        configs = list_configurations()
        if not configs:
            console.print("[red]No gcloud configurations found.[/red]")
            console.print("[dim]Create one with: gcloud config configurations create <name>[/dim]")
            return 1

        if args.config:
            cfg = validate_selection(args.config, configs)
            if cfg is None:
                console.print(f"[red]Unknown configuration: {args.config}[/red]")
                return 1
            return _switch(cfg)

        display_configurations(configs, current_config())
        cfg = get_user_selection(configs)
        if cfg is None:
            logger.info("No selection made")
            return 1
        return _switch(cfg)

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
