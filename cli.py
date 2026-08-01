#!/usr/bin/env python3

import asyncio
import math
import os
import re

import click
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from main import (
    DAY_SECONDS,
    DEFAULT_COOKIE_FILE,
    HOUR_SECONDS,
    MAX_PER_DAY,
    MAX_PER_HOUR,
    OVERRIDE_RISK_WARNING,
    analyze_plan,
    count_generated_today,
    filter_accounts,
    format_duration,
    generate,
    list_emails,
    load_accounts_config,
    resolve_effective_limits,
    suggested_duration_hours,
)
from banscan import BAN_SIGNAL_KEYS, resolve_export_format, run_ban_check
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


def pick_accounts(default_accounts_file: str = "accounts.json"):
    """Interactively pick which account(s) to run against.

    Returns ``(accounts_file, account_names, cookie_file, account_name)``:

    - several accounts:  ``(accounts_file, [names] or None for all, None, None)``
    - a single account:  ``(None, None, cookie_file, name)``
    - default cookie:    ``(None, None, None, None)`` (``cookies/cookie.txt``)
    """
    accounts_file = default_accounts_file
    try:
        accounts = load_accounts_config(accounts_file)
    except ValueError:
        accounts = None

    if accounts is None:
        # No usable accounts file next to the script: ask for a path, or fall
        # back to the default cookie file.
        if not Confirm.ask(
            "Pick accounts from an accounts JSON file?",
            default=False,
            console=console,
        ):
            console.print(f"[dim]Using the default cookie file ({DEFAULT_COOKIE_FILE}).[/]")
            return None, None, None, None

        accounts_file = Prompt.ask(
            "Path to accounts file", default=default_accounts_file, console=console
        )
        try:
            accounts = load_accounts_config(accounts_file)
        except ValueError as exc:
            console.print(f"[yellow]⚠ {exc}[/]")
            console.print(f"[dim]Falling back to the default cookie file ({DEFAULT_COOKIE_FILE}).[/]")
            return None, None, None, None

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(justify="center", style=f"bold {ACCENT}")
    table.add_column(style="bold")
    table.add_column(style="dim")
    # "[a]" needs escaping, otherwise Rich would parse it as a markup tag.
    table.add_row(r"\[a]", "all accounts", f"run the {len(accounts)} account(s) below in parallel")
    for index, account in enumerate(accounts, start=1):
        table.add_row(f"[{index}]", account.name, account.cookie_file)
    table.add_row("[0]", "default cookie", DEFAULT_COOKIE_FILE)
    console.print(
        Panel(
            table,
            title=f"[bold]Accounts ({accounts_file})",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    while True:
        raw = Prompt.ask(
            'Which account(s)? Numbers or names, comma-separated — e.g. "1,2,4"',
            default="all",
            console=console,
        )
        tokens = [token for token in re.split(r"[\s,]+", raw.strip()) if token]
        if not tokens or raw.strip().lower() in ("a", "all"):
            selected = list(accounts)
        elif tokens == ["0"]:
            console.print(f"[dim]Using the default cookie file ({DEFAULT_COOKIE_FILE}).[/]")
            return None, None, None, None
        else:
            selected = []
            error = None
            for token in tokens:
                if token.isdigit():
                    index = int(token)
                    if not 1 <= index <= len(accounts):
                        error = f'"{token}" is out of range (1-{len(accounts)}).'
                        break
                    account = accounts[index - 1]
                else:
                    matches = [a for a in accounts if a.name == token]
                    if not matches:
                        error = f'No account named "{token}".'
                        break
                    account = matches[0]
                if account not in selected:
                    selected.append(account)
            if error:
                console.print(f"[yellow]⚠ {error} Try again.[/]")
                continue

        names = ", ".join(account.name for account in selected)
        console.print(
            f"[dim]Selected {len(selected)}/{len(accounts)} account(s): {names}[/]"
        )

        if len(selected) == 1:
            account = selected[0]
            return None, None, account.cookie_file, account.name
        if len(selected) == len(accounts):
            return accounts_file, None, None, None
        return accounts_file, [account.name for account in selected], None, None


def resolve_cli_accounts(account_options, accounts_file):
    """Resolve one or more ``--account NAME`` options.

    Returns ``(accounts_file, account_names, cookie_file, account_name)`` with
    the same meaning as :func:`pick_accounts`. Exits with a clear error if a
    named account cannot be found.
    """
    names = [
        name.strip()
        for raw in account_options
        for name in raw.split(",")
        if name.strip()
    ]
    names = list(dict.fromkeys(names))
    if not names:
        return accounts_file, None, None, None

    path = accounts_file or "accounts.json"
    try:
        selected = filter_accounts(load_accounts_config(path), names)
    except ValueError as exc:
        console.print(f"[red]✗ {exc} (accounts file: \"{path}\")[/]")
        raise SystemExit(1)

    if len(selected) == 1:
        return None, None, selected[0].cookie_file, selected[0].name
    return path, names, None, None


def resolve_ban_modes(mode_options):
    """Resolve one or more ``--mode`` options into a list of ban-signal keys.

    Accepts repeated flags or comma-separated values; ``all`` expands to every
    known signal. Defaults to the ``appeal`` signal (the historical behaviour).
    Exits with a clear error on an unknown mode.
    """
    tokens = [
        token.strip().lower()
        for raw in mode_options
        for token in raw.split(",")
        if token.strip()
    ]
    if not tokens:
        return ["appeal"]

    keys: list[str] = []
    for token in tokens:
        if token in ("all", "tous", "*"):
            return list(BAN_SIGNAL_KEYS)
        if token not in BAN_SIGNAL_KEYS:
            console.print(
                f'[red]✗ Mode inconnu : "{token}". '
                f"Modes disponibles : {', '.join(BAN_SIGNAL_KEYS)}, all.[/]"
            )
            raise SystemExit(1)
        if token not in keys:
            keys.append(token)
    return keys


# --------------------------------------------------------------------------- #
# Main menu
# --------------------------------------------------------------------------- #
MENU_ITEMS = [
    ("1", "Generate", "Create new HideMyEmail aliases"),
    ("2", "List", "Browse & export existing aliases"),
    ("3", "Ban check", "Détecter les alias bannis Amazon & les désactiver"),
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

    override_limits = Confirm.ask(
        "Override the safe limits (5/hour, 15/day)? Not recommended.",
        default=False,
        console=console,
    )
    max_per_hour = MAX_PER_HOUR
    if override_limits:
        console.print(f"[bold red]⚠ {OVERRIDE_RISK_WARNING}[/]\n")
        max_per_hour = IntPrompt.ask(
            "Maximum aliases per hour (override)?",
            default=MAX_PER_HOUR,
            console=console,
        )

    count = IntPrompt.ask(
        "How many aliases do you want to generate?", default=5, console=console
    )
    daily_limit = IntPrompt.ask(
        "Maximum aliases per calendar day?", default=MAX_PER_DAY, console=console
    )
    daily_limit, max_per_hour, clamp_warnings = resolve_effective_limits(
        daily_limit, max_per_hour, override_limits
    )

    # In override mode the run plan ignores today's history (mirrors generate()).
    preview_today = 0 if override_limits else count_generated_today(None)
    suggested = suggested_duration_hours(
        count, daily_limit, max_per_hour, preview_today, override_limits
    )
    preview_seconds = suggested * HOUR_SECONDS
    preview_days = max(1, math.ceil(preview_seconds / DAY_SECONDS))
    pace_label = "requested pace" if override_limits else "safe default pace"
    console.print(
        f"[dim]At the {pace_label} ({max_per_hour}/hour, {daily_limit}/day), "
        f"generating {count} alias(es) will take about {preview_days} day(s) "
        f"(~{format_duration(preview_seconds)}). The script keeps running "
        "until they're all generated — it does not stop early.[/]\n"
    )

    duration_hours = FloatPrompt.ask(
        "Spread the run over how many hours?", default=suggested, console=console
    )

    accounts_file, account_names, cookie_file, account_name = pick_accounts()

    duration_seconds = duration_hours * HOUR_SECONDS
    duration_days = max(1, math.ceil(duration_seconds / DAY_SECONDS)) if duration_seconds > 0 else 0
    pace = count / duration_hours if duration_hours > 0 else float("inf")
    warnings = clamp_warnings + analyze_plan(
        count, duration_seconds, daily_limit, max_per_hour, preview_today
    )

    summary_panel(
        "Review",
        [
            ("Aliases", str(count)),
            ("Max per hour", f"{max_per_hour}/hour"),
            ("Daily limit", f"{daily_limit}/day"),
            ("Duration", f"{duration_hours:g} h (~{duration_days} day(s))"),
            ("Pace", "instant" if pace == float("inf") else f"~{pace:.1f}/hour"),
            ("Override", "ON — at your own risk" if override_limits else "off (safe defaults)"),
            ("Accounts file", accounts_file or "—"),
            (
                "Account(s)",
                account_name
                or (
                    (", ".join(account_names) if account_names else "all")
                    if accounts_file
                    else "default"
                ),
            ),
        ],
    )

    for warning in warnings:
        console.print(f"[bold yellow]⚠ {warning}[/]")

    if not Confirm.ask("Proceed?", default=not warnings, console=console):
        console.print("[yellow]Cancelled.[/]")
        return

    run_async(
        generate(
            count,
            daily_limit,
            duration_hours,
            accounts_file,
            max_per_hour=max_per_hour,
            override_limits=override_limits,
            cookie_file=cookie_file,
            account_name=account_name,
            account_names=account_names,
        )
    )


def interactive_list() -> None:
    console.rule(f"[bold {ACCENT}]List emails")

    filter_choice = Prompt.ask(
        "Which emails to show?",
        choices=["active", "inactive", "all"],
        default="all",
        console=console,
    )
    # "all" -> None means no active/inactive filter (everything Apple returns).
    active = {"active": True, "inactive": False, "all": None}[filter_choice]
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

    accounts_file, account_names, cookie_file, account_name = pick_accounts()

    summary_panel(
        "Review",
        [
            ("Filter", filter_choice),
            ("Search", search or "—"),
            ("Export", export or "—"),
            ("Accounts file", accounts_file or "—"),
            (
                "Account(s)",
                account_name
                or (
                    (", ".join(account_names) if account_names else "all")
                    if accounts_file
                    else "default"
                ),
            ),
        ],
    )

    run_async(
        list_emails(
            active,
            search,
            export,
            accounts_file,
            cookie_file=cookie_file,
            account_name=account_name,
            account_names=account_names,
        )
    )


def interactive_ban_check() -> None:
    console.rule(f"[bold {ACCENT}]Détection des bans Amazon")
    console.print(
        "[dim]Cherche dans ta/tes boîte(s) Gmail les mails de ban Amazon, identifie "
        "les alias concernés et le compte iCloud de chacun, puis propose de les "
        "désactiver (et éventuellement supprimer) après vérification des cookies.[/]\n"
    )

    # Which ban signal(s) to scan for.
    mode_table = Table(box=None, show_header=False, padding=(0, 2))
    mode_table.add_column(justify="center", style=f"bold {ACCENT}")
    mode_table.add_column(style="bold")
    mode_table.add_column(style="dim")
    mode_table.add_row("appeal", "Compte banni", "baa-customer-appeal → désactive")
    mode_table.add_row(
        "on-hold",
        "Compte « on hold »",
        "« …temporarily on hold » → désactive + supprime",
    )
    mode_table.add_row("all", "Les deux", "scanne les deux signaux")
    console.print(
        Panel(mode_table, title="[bold]Modes de scan", border_style="cyan", box=box.ROUNDED)
    )
    mode_choice = Prompt.ask(
        "Quels signaux de ban chercher ?",
        choices=["appeal", "on-hold", "all"],
        default="appeal",
        console=console,
    )
    modes = list(BAN_SIGNAL_KEYS) if mode_choice == "all" else [mode_choice]

    dry_run = Confirm.ask(
        "Mode simulation (dry-run — scan & rapport, aucune action) ?",
        default=True,
        console=console,
    )

    # The "appeal" signal only deactivates by default; offer to also delete. The
    # "on-hold" signal always deactivates + deletes, so no need to ask for it.
    force_delete = False
    if "appeal" in modes and Confirm.ask(
        "Pour les alias « compte banni », les supprimer définitivement en plus de "
        "les désactiver ? (irréversible)",
        default=False,
        console=console,
    ):
        force_delete = True

    # In dry-run, offer to export the flagged aliases (those theoretically to
    # deactivate/delete) so they can be reviewed or reused.
    export_path = None
    export_format = "csv"
    if dry_run and Confirm.ask(
        "Exporter la liste des alias signalés (théoriquement à traiter) ?",
        default=False,
        console=console,
    ):
        export_format = Prompt.ask(
            "Format d'export",
            choices=["csv", "txt"],
            default="csv",
            console=console,
        )
        export_path = Prompt.ask(
            "Chemin du fichier",
            default=f"alias_bannis.{export_format}",
            console=console,
        )

    accounts_file, account_names, cookie_file, account_name = pick_accounts()

    def mode_action(key: str) -> str:
        if key == "on-hold" or force_delete:
            return "désactiver + supprimer"
        return "désactiver"

    modes_desc = ", ".join(f"{key} → {mode_action(key)}" for key in modes)
    mode_label = (
        "simulation (dry-run)" if dry_run else "action (avec confirmation par compte)"
    )

    summary_panel(
        "Review",
        [
            ("Mode", mode_label),
            ("Signaux", modes_desc),
            ("Export", f"{export_path} ({export_format})" if export_path else "—"),
            ("Accounts file", accounts_file or "—"),
            (
                "Account(s)",
                account_name
                or (
                    (", ".join(account_names) if account_names else "all")
                    if accounts_file
                    else "default"
                ),
            ),
        ],
    )

    run_async(
        run_ban_check(
            accounts_file=accounts_file,
            account_names=account_names,
            cookie_file=cookie_file,
            account_name=account_name,
            dry_run=dry_run,
            modes=modes,
            force_delete=force_delete,
            export_path=export_path,
            export_format=export_format,
        )
    )


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
            elif choice == "3":
                interactive_ban_check()
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
    help=(
        f"Maximum aliases per calendar day. Values above {MAX_PER_DAY} are "
        "clamped unless --override-limits is also passed."
    ),
)
@click.option(
    "--max-per-hour",
    default=None,
    type=int,
    help=(
        f"Maximum aliases per rolling hour (default {MAX_PER_HOUR}). Values "
        f"above {MAX_PER_HOUR} are clamped unless --override-limits is also "
        "passed."
    ),
)
@click.option(
    "--override-limits",
    is_flag=True,
    default=False,
    help=(
        "Voluntarily exceed the safe default limits "
        f"({MAX_PER_HOUR}/hour, {MAX_PER_DAY}/day), at your own risk. Must be "
        "passed explicitly — a large --daily-limit or --max-per-hour alone is "
        "not enough."
    ),
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
        "Path to a JSON file that lists multiple iCloud accounts, each with "
        'a "name" and a "cookie_file". All accounts share the same '
        "--count/--daily-limit/--max-per-hour/--override-limits."
    ),
)
@click.option(
    "--account",
    multiple=True,
    help=(
        "Run only the named account(s) from the accounts file "
        '(default "accounts.json", or --accounts-file). Repeat the flag or '
        'pass a comma-separated list: --account main --account iCloud2, or '
        '--account "main,iCloud2". Without it, an --accounts-file run uses '
        "all accounts."
    ),
)
def generatecommand(
    count, daily_limit, max_per_hour, override_limits, duration_hours, accounts_file, account
):
    "Generate aliases at a safe, human pace"
    licensing.require_license(console)
    accounts_file, account_names, cookie_file, account_name = resolve_cli_accounts(
        account, accounts_file
    )
    run_async(
        generate(
            count,
            daily_limit,
            duration_hours,
            accounts_file,
            max_per_hour=max_per_hour,
            override_limits=override_limits,
            cookie_file=cookie_file,
            account_name=account_name,
            account_names=account_names,
        )
    )


@click.command(name="list")
@click.option(
    "--active/--inactive", default=True, help="Filter Active / Inactive emails"
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help=(
        "List/export ALL aliases (both active and inactive), matching the full "
        "count you see in Hide My Email. Overrides --active/--inactive."
    ),
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
@click.option(
    "--account",
    multiple=True,
    help=(
        "List only the named account(s) from the accounts file "
        '(default "accounts.json", or --accounts-file). Repeat the flag or '
        "pass a comma-separated list."
    ),
)
def listcommand(active, show_all, search, export, accounts_file, account):
    "List emails"
    licensing.require_license(console)
    accounts_file, account_names, cookie_file, account_name = resolve_cli_accounts(
        account, accounts_file
    )
    if show_all:
        active = None
    run_async(
        list_emails(
            active,
            search,
            export,
            accounts_file,
            cookie_file=cookie_file,
            account_name=account_name,
            account_names=account_names,
        )
    )


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


@click.command(name="bancheck")
@click.option(
    "--accounts-file",
    default=None,
    help="Path to a JSON file that defines multiple iCloud accounts.",
)
@click.option(
    "--account",
    multiple=True,
    help=(
        "Restrict to the named account(s) from the accounts file. Repeat the "
        "flag or pass a comma-separated list. Without it, all accounts are used."
    ),
)
@click.option(
    "--mode",
    "modes",
    multiple=True,
    help=(
        'Which ban signal(s) to scan for: "appeal" (baa-customer-appeal, '
        'deactivate), "on-hold" ("…temporarily on hold" subject, deactivate + '
        'delete), or "all". Repeat the flag or pass a comma-separated list. '
        "Default: appeal."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Scan & report only — never deactivate or delete any alias.",
)
@click.option(
    "--delete",
    "delete_mode",
    is_flag=True,
    default=False,
    help=(
        "Force permanent DELETE (deactivate then delete) for every selected "
        "mode, including appeal. Irreversible. The on-hold mode already deletes "
        "by default."
    ),
)
@click.option(
    "--yes",
    "assume_yes",
    is_flag=True,
    default=False,
    help="Act on banned aliases without the per-account confirmation prompt.",
)
@click.option(
    "--export",
    "export_path",
    default=None,
    help=(
        "Export the flagged aliases (those that would be deactivated/deleted) to "
        "this file. The format is inferred from the extension (.txt → one alias "
        "per line, otherwise CSV) unless --export-format is given."
    ),
)
@click.option(
    "--export-format",
    type=click.Choice(["txt", "csv"]),
    default=None,
    help="Force the export format (default: inferred from the --export extension).",
)
def bancheckcommand(
    accounts_file, account, modes, dry_run, delete_mode, assume_yes, export_path, export_format
):
    "Detect Amazon-ban aliases (appeal / on-hold) and deactivate/delete them"
    licensing.require_license(console)
    ban_modes = resolve_ban_modes(modes)
    # Default to all accounts (accounts.json) so bans map across every phone.
    if not accounts_file and not account and os.path.exists("accounts.json"):
        accounts_file = "accounts.json"
    accounts_file, account_names, cookie_file, account_name = resolve_cli_accounts(
        account, accounts_file
    )
    run_async(
        run_ban_check(
            accounts_file=accounts_file,
            account_names=account_names,
            cookie_file=cookie_file,
            account_name=account_name,
            dry_run=dry_run,
            assume_yes=assume_yes,
            modes=ban_modes,
            force_delete=delete_mode,
            export_path=export_path,
            export_format=(
                resolve_export_format(export_path, export_format)
                if export_path
                else "csv"
            ),
        )
    )


cli.add_command(generatecommand)
cli.add_command(listcommand)
cli.add_command(activatecommand)
cli.add_command(bancheckcommand)


if __name__ == "__main__":
    cli()
