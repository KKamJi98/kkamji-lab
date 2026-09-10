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
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = ["--help" if arg == "-help" else arg for arg in argv]
    # The wrapper prepends this internal transport flag before user arguments.
    user_start = 1 if argv[:1] == ["--shell-state"] else 0
    if argv[user_start : user_start + 1] == ["login"]:
        argv[user_start] = "--login"
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
        help="Log in to gcloud CLI and ADC for CONFIG (default: current configuration)",
    )
    parser.add_argument("--shell-state", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)
    if args.login is not None and args.config is not None:
        parser.error("use login [CONFIG] or --login [CONFIG], without another configuration")
    return args


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


def _run_adc_login(cfg: GcloudConfig) -> int:
    """Log in to the selected CLI account and update ADC in the same flow.

    GOOGLE_APPLICATION_CREDENTIALS is dropped for the login: gcloud writes to the
    default ADC location regardless, and leaving the variable set only makes it
    warn that the file it is writing is not the one in the environment and ask
    for a confirmation.
    """
    env = os.environ.copy()
    env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    env.pop("CLOUDSDK_CORE_ACCOUNT", None)
    try:
        result = subprocess.run(
            ["gcloud", "auth", "login", cfg.account, "--configuration", cfg.name, "--update-adc"],
            check=False,
            env=env,
            stdout=sys.stderr,
        )
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"[red]Failed to run gcloud: {e}[/red]")
        return 1
    return result.returncode


def _do_login(config_name: str) -> int:
    """Log in to CLI and ADC, then save only a matching per-account ADC file."""
    cfg = next((c for c in list_configurations() if c.name == config_name), None)
    if cfg is None or not cfg.account:
        console.print("[red]Login requires an existing configuration with a core/account.[/red]")
        return 1
    if _run_adc_login(cfg) != 0:
        console.print("[red]CLI/ADC login failed or was cancelled.[/red]")
        return 1

    default_adc = gcloud_dir() / "application_default_credentials.json"
    account = resolve_adc_account(default_adc)
    if not account:
        console.print("[red]Could not resolve the ADC account after login.[/red]")
        return 1

    if cfg.account != account:
        console.print("[red]Account mismatch: ADC does not match the selected configuration.[/red]")
        return 1

    dest = adc_path_for(account)
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(dest.parent, 0o700)
    shutil.copy2(default_adc, dest)
    os.chmod(dest, 0o600)
    console.print(f"[green]Saved ADC for {account}[/green] [dim]-> {dest}[/dim]")
    return 0


def _switch(cfg: GcloudConfig, shell_state: bool = False) -> int:
    """Write the shared profile and print export commands for a configuration."""
    if cfg.account and adc_exists(cfg.account):
        adc_path = adc_path_for(cfg.account)
    elif cfg.account and _prompt_yes_no(f"Set up ADC for {cfg.account} now? (opens gcloud login)"):
        if _do_login(cfg.name) != 0:
            return 1
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
    if shell_state:
        print(f"gcloud-pick-state-v1\n{cfg.name}\n{adc_path if adc_path is not None else '-'}")
    else:
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
            config_name = args.login or current_config() or ""
            if _do_login(config_name) != 0:
                return 1
            cfg = next(c for c in list_configurations() if c.name == config_name)
            return _switch(cfg, args.shell_state)

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
            return _switch(cfg, args.shell_state)

        display_configurations(configs, current_config())
        cfg = get_user_selection(configs)
        if cfg is None:
            logger.info("No selection made")
            return 1
        return _switch(cfg, args.shell_state)

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
