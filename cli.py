#!/usr/bin/env python3

import asyncio
import click

from main import OLD_ACCOUNT_MODE, generate, list, normalize_generation_mode


@click.group()
def cli():
    pass


def validate_generate_mode(_ctx, _param, value: str) -> str:
    try:
        return normalize_generation_mode(value)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc


@click.command()
@click.option(
    "--count", default=5, help="How many emails to generate", type=int
)
@click.option(
    "--mode",
    default=OLD_ACCOUNT_MODE,
    callback=validate_generate_mode,
    show_default=True,
    help=(
        "Generation mode: old-account for the current bulk behavior, "
        "or fresh-account for one randomized attempt per 12-minute window."
    ),
)
@click.option(
    "--accounts-file",
    default=None,
    help=(
        "Path to a JSON file that defines multiple iCloud accounts. "
        "Each account can override its own cookie_file, mode, and count."
    ),
)
def generatecommand(count: int, mode: str, accounts_file: str):
    "Generate emails"
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(generate(count, mode, accounts_file))
    except KeyboardInterrupt:
        pass


@click.command()
@click.option(
    "--active/--inactive", default=True, help="Filter Active / Inactive emails"
)
@click.option("--search", default=None, help="Search emails")
@click.option("--export", default=None, help="Export emails to a CSV file (e.g. --export emails_list.csv)")
@click.option(
    "--accounts-file",
    default=None,
    help="Path to a JSON file that defines multiple iCloud accounts.",
)
def listcommand(active, search, export, accounts_file):
    "List emails"
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(list(active, search, export, accounts_file))
    except KeyboardInterrupt:
        pass


cli.add_command(listcommand, name="list")
cli.add_command(generatecommand, name="generate")

if __name__ == "__main__":
    cli()
