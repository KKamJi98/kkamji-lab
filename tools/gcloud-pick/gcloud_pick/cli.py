"""Command-line interface for gcloud-pick."""

import argparse
import logging
import sys
from typing import Optional

from rich.console import Console

from gcloud_pick import __version__

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


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    try:
        parse_args(argv)
        console.print("[yellow]gcloud-pick: not implemented yet[/yellow]")
        return 0
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
