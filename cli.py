#!/usr/bin/env python3

import asyncio

import click
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from main import (
    HOUR_SECONDS,
    MAX_PER_DAY,
    MAX_PER_HOUR,
    analyze_plan,
    generate,
    list_emails,
    suggested_duration_hours,
)
import licensing

console = Console()

ACCENT = "green"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def run_async(coro) -> None:
    """Run an async entry point on its own event loop."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        pass


def print_banner() -> None:
    title = Text(justify="center")
    title.append("📧  iCloud HideMyEmail\n", style=f"bold {ACCENT}")
    title.append("Generate & manage your email aliases", style="dim")
    console.print(
        Panel(
            Align.center(title),
            box=box.ROUNDED,
            border_style=ACCENT,
            padding=(1, 4),
        )
    )


def summary_panel(title: str, rows: list[tuple[str, str]]) -> None:
    grid = Table(box=None, show_header=False, padding=(0, 2))
    grid.add_column(justify="right", style="dim")
    grid.add_column(style="bold")
    for label, value in rows:
        grid.add_row(label, value)
    console.print(
        Panel(grid, title=f"[bold {ACCENT}]{title}", border_style=ACCENT, box=box.ROUNDED)
    )


# --------------------------------------------------------------------------- #
# Main menu
# --------------------------------------------------------------------------- #
MENU_ITEMS = [
    ("1", "Generate", "Create new HideMyEmail aliases"),
    ("2", "List", "Browse & export existing aliases"),
    ("0", "Quit", "Exit the program"),
]


def main_menu() -> str:
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(justify="center", style=f"bold {ACCENT}")
    table.add_column(style="bold")
    table.add_column(style="dim")
    for key, name, desc in MENU_ITEMS:
        table.add_row(f"[{key}]", name, desc)

    console.print(
        Panel(table, title="[bold]Menu", border_style="cyan", box=box.ROUNDED)
    )

    return Prompt.ask(
        "[bold cyan]Select an option",
        choices=[key for key, _, _ in MENU_ITEMS],
        default="1",
        console=console,
        show_choices=True,
    )


# --------------------------------------------------------------------------- #
# Interactive flows
# --------------------------------------------------------------------------- #
def interactive_generate() -> None:
    console.rule(f"[bold {ACCENT}]Generate aliases")
    console.print(
        f"[dim]Aliases are generated at a safe, human pace "
        f"(max {MAX_PER_HOUR}/hour, {MAX_PER_DAY}/day) spread over the run.[/]\n"
    )

    count = IntPrompt.ask(
        "How many aliases do you want to generate?", default=5, console=console
    )
    daily_limit = IntPrompt.ask(
        "Maximum aliases per calendar day?", default=MAX_PER_DAY, console=console
    )
    suggested = suggested_duration_hours(count, daily_limit)
    duration_hours = FloatPrompt.ask(
        "Spread the run over how many hours?", default=suggested, console=console
    )

    accounts_file = None
    if Confirm.ask(
        "Use a multi-account JSON file?", default=False, console=console
    ):
        accounts_file = Prompt.ask(
            "Path to accounts file", default="accounts.json", console=console
        )

    duration_seconds = duration_hours * HOUR_SECONDS
    pace = count / duration_hours if duration_hours > 0 else float("inf")
    warnings = analyze_plan(count, duration_seconds, daily_limit)

    summary_panel(
        "Review",
        [
            ("Aliases", str(count)),
            ("Daily limit", f"{daily_limit}/day"),
            ("Duration", f"{duration_hours:g} h"),
            ("Pace", "instant" if pace == float("inf") else f"~{pace:.1f}/hour"),
            ("Accounts file", accounts_file or "—"),
        ],
    )

    for warning in warnings:
        console.print(f"[bold yellow]⚠ {warning}[/]")

    if not Confirm.ask("Proceed?", default=not warnings, console=console):
        console.print("[yellow]Cancelled.[/]")
        return

    run_async(generate(count, daily_limit, duration_hours, accounts_file))


def interactive_list() -> None:
    console.rule(f"[bold {ACCENT}]List emails")

    active = (
        Prompt.ask(
            "Which emails to show?",
            choices=["active", "inactive"],
            default="active",
            console=console,
        )
        == "active"
    )
    search = (
        Prompt.ask(
            "Search filter (regex, leave empty for none)",
            default="",
            console=console,
            show_default=False,
        )
        or None
    )

    export = None
    if Confirm.ask("Export results to a CSV file?", default=False, console=console):
        export = Prompt.ask(
            "CSV file path", default="emails_list.csv", console=console
        )

    accounts_file = None
    if Confirm.ask(
        "Use a multi-account JSON file?", default=False, console=console
    ):
        accounts_file = Prompt.ask(
            "Path to accounts file", default="accounts.json", console=console
        )

    summary_panel(
        "Review",
        [
            ("Filter", "active" if active else "inactive"),
            ("Search", search or "—"),
            ("Export", export or "—"),
            ("Accounts file", accounts_file or "—"),
        ],
    )

    run_async(list_emails(active, search, export, accounts_file))


def run_interactive_menu() -> None:
    console.clear()
    licensing.require_license(console)
    while True:
        print_banner()
        choice = main_menu()

        if choice == "0":
            console.print(f"\n[dim]Goodbye 👋[/]\n")
            return

        try:
            if choice == "1":
                interactive_generate()
            elif choice == "2":
                interactive_list()
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled — returning to menu.[/]")

        console.print()
        if not Confirm.ask(
            "Return to the menu?", default=True, console=console
        ):
            console.print(f"\n[dim]Goodbye 👋[/]\n")
            return
        console.rule(style="dim")


# --------------------------------------------------------------------------- #
# Click commands (direct, non-interactive usage)
# --------------------------------------------------------------------------- #
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """iCloud HideMyEmail generator. Run without a command for the menu."""
    if ctx.invoked_subcommand is None:
        run_interactive_menu()


@click.command(name="generate")
@click.option(
    "--count", default=5, type=int, help="How many aliases to generate"
)
@click.option(
    "--daily-limit",
    default=MAX_PER_DAY,
    type=int,
    show_default=True,
    help=f"Maximum aliases per calendar day (recommended <= {MAX_PER_DAY}).",
)
@click.option(
    "--duration",
    "duration_hours",
    default=None,
    type=float,
    help=(
        "Hours to spread the run over. Defaults to a safe, human pace "
        f"(max {MAX_PER_HOUR}/hour)."
    ),
)
@click.option(
    "--accounts-file",
    default=None,
    help=(
        "Path to a JSON file that defines multiple iCloud accounts. Each "
        "account can override its own cookie_file, count, daily_limit, and "
        "duration_hours."
    ),
)
def generatecommand(count, daily_limit, duration_hours, accounts_file):
    "Generate aliases at a safe, human pace"
    licensing.require_license(console)
    run_async(generate(count, daily_limit, duration_hours, accounts_file))


@click.command(name="list")
@click.option(
    "--active/--inactive", default=True, help="Filter Active / Inactive emails"
)
@click.option("--search", default=None, help="Search emails")
@click.option(
    "--export",
    default=None,
    help="Export emails to a CSV file (e.g. --export emails_list.csv)",
)
@click.option(
    "--accounts-file",
    default=None,
    help="Path to a JSON file that defines multiple iCloud accounts.",
)
def listcommand(active, search, export, accounts_file):
    "List emails"
    licensing.require_license(console)
    run_async(list_emails(active, search, export, accounts_file))


@click.command(name="activate")
@click.argument("key")
def activatecommand(key):
    "Activate your access key"
    if not licensing.verify(key):
        console.print("[red]✗ Invalid or expired access key.[/]")
        raise SystemExit(1)

    licensing.save_key(key)
    info = licensing.key_info(key)
    console.print(
        f"[green]✓ Access key activated[/] for [bold]{info.get('sub', '?')}[/] "
        f"(expires: {info.get('exp', 'never')})."
    )


cli.add_command(generatecommand)
cli.add_command(listcommand)
cli.add_command(activatecommand)


if __name__ == "__main__":
    cli()
