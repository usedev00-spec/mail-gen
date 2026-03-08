import asyncio
import builtins
import csv
import datetime
import json
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from icloud import HideMyEmail


DEFAULT_COOKIE_FILE = "cookie.txt"
DEFAULT_ACCOUNTS_FILE = "accounts.json"
DEFAULT_EMAILS_FILE = "emails.txt"
MAX_CONCURRENT_TASKS = 10
OLD_ACCOUNT_MODE = "old-account"
FRESH_ACCOUNT_MODE = "fresh-account"
FRESH_ACCOUNT_SLOT_SECONDS = 12 * 60
FRESH_ACCOUNT_MIN_DELAY_SECONDS = 5 * 60
FRESH_ACCOUNT_MAX_DELAY_SECONDS = 12 * 60
GENERATION_MODE_ALIASES = {
    "old-account": OLD_ACCOUNT_MODE,
    "old-acc": OLD_ACCOUNT_MODE,
    "old": OLD_ACCOUNT_MODE,
    "fresh-account": FRESH_ACCOUNT_MODE,
    "fresh-acc": FRESH_ACCOUNT_MODE,
    "fresh": FRESH_ACCOUNT_MODE,
}


@dataclass
class AccountConfig:
    name: str
    cookie_file: str
    mode: str = OLD_ACCOUNT_MODE
    count: Optional[int] = None


def normalize_generation_mode(
    mode: Optional[str], default: str = OLD_ACCOUNT_MODE
) -> str:
    if mode is None:
        return default

    normalized = mode.strip().lower()
    if normalized in GENERATION_MODE_ALIASES:
        return GENERATION_MODE_ALIASES[normalized]

    raise ValueError(
        'Invalid generation mode. Use "old-account" or "fresh-account".'
    )


def resolve_config_path(base_dir: str, path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def parse_account_count(value: Any, fallback: Optional[int], index: int) -> Optional[int]:
    if value is None:
        return fallback

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f'Account #{index} has an invalid "count". It must be an integer.'
        )

    if value < 1:
        raise ValueError(
            f'Account #{index} has an invalid "count". It must be greater than 0.'
        )

    return value


def load_accounts_config(
    accounts_file: str,
    default_count: Optional[int] = None,
    default_mode: str = OLD_ACCOUNT_MODE,
) -> list[AccountConfig]:
    try:
        with open(accounts_file, "r", encoding="utf-8") as f:
            raw_config = json.load(f)
    except FileNotFoundError as exc:
        raise ValueError(
            f'Accounts file "{accounts_file}" does not exist.'
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f'Accounts file "{accounts_file}" is not valid JSON: {exc}'
        ) from exc
    except OSError as exc:
        raise ValueError(
            f'Could not read accounts file "{accounts_file}": {exc}'
        ) from exc

    if isinstance(raw_config, dict):
        accounts_data = raw_config.get("accounts")
    else:
        accounts_data = raw_config

    if not isinstance(accounts_data, builtins.list):
        raise ValueError(
            f'Accounts file "{accounts_file}" must contain a JSON array or an '
            'object with an "accounts" array.'
        )

    if not accounts_data:
        raise ValueError(f'Accounts file "{accounts_file}" does not contain any accounts.')

    base_dir = os.path.dirname(os.path.abspath(accounts_file))
    accounts = []
    for index, item in enumerate(accounts_data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Account #{index} must be a JSON object.")

        raw_cookie_file = item.get("cookie_file")
        if not isinstance(raw_cookie_file, str) or not raw_cookie_file.strip():
            raise ValueError(
                f'Account #{index} is missing "cookie_file".'
            )

        cookie_file = resolve_config_path(base_dir, raw_cookie_file.strip())
        account_name = item.get("name")
        if not isinstance(account_name, str) or not account_name.strip():
            inferred_name = os.path.splitext(os.path.basename(cookie_file))[0]
            account_name = inferred_name or f"account-{index}"
        else:
            account_name = account_name.strip()

        account_mode = normalize_generation_mode(
            item.get("mode"), default_mode
        )
        account_count = parse_account_count(
            item.get("count"), default_count, index
        )

        accounts.append(
            AccountConfig(
                name=account_name,
                cookie_file=cookie_file,
                mode=account_mode,
                count=account_count,
            )
        )

    return accounts


def save_emails(emails: list[str], output_file: str = DEFAULT_EMAILS_FILE) -> None:
    if not emails:
        return

    with open(output_file, "a+", encoding="utf-8") as f:
        f.write(os.linesep.join(emails) + os.linesep)


def build_email_table(
    rows: list[dict[str, str]], include_account: bool = False
) -> Table:
    table = Table()
    if include_account:
        table.add_column("Account")
    table.add_column("Label")
    table.add_column("Hide my email")
    table.add_column("Created Date Time")
    table.add_column("IsActive")

    for row in rows:
        cells = []
        if include_account:
            cells.append(row["account"])
        cells.extend(
            [
                row["label"],
                row["email"],
                row["created"],
                row["active"],
            ]
        )
        table.add_row(*cells)

    return table


def export_email_rows(
    rows: list[dict[str, str]],
    export: str,
    include_account: bool = False,
) -> None:
    headers = ["Label", "Email", "Created", "IsActive"]
    if include_account:
        headers.insert(0, "Account")

    with open(export, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            output_row = []
            if include_account:
                output_row.append(row["account"])
            output_row.extend(
                [
                    row["label"],
                    row["email"],
                    row["created"],
                    row["active"],
                ]
            )
            writer.writerow(output_row)


class RichHideMyEmail(HideMyEmail):
    def __init__(
        self,
        cookie_file: str = DEFAULT_COOKIE_FILE,
        account_name: Optional[str] = None,
        console: Optional[Console] = None,
    ):
        super().__init__()
        self.account_name = account_name
        self._cookie_file = cookie_file
        self.console = console or Console()
        self.cookie_error = None
        self._load_cookies()

    def _log_prefix(self) -> str:
        if not self.account_name:
            return ""
        return f"({self.account_name}) "

    def _log(self, message: str) -> None:
        self.console.log(f"{self._log_prefix()}{message}")

    def _cookie_reference(self) -> str:
        return f'"{self._cookie_file}"'

    def _load_cookies(self) -> None:
        if not os.path.exists(self._cookie_file):
            self.cookie_error = (
                f"Missing {self._cookie_reference()}. Export fresh iCloud cookies "
                "from https://www.icloud.com/settings/ and save them before retrying."
            )
            self._log(f'[bold yellow][WARN][/] {self.cookie_error}')
            return

        try:
            with open(self._cookie_file, "r", encoding="utf-8") as f:
                cookie_lines = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.lstrip().startswith("//")
                ]
        except OSError as exc:
            self.cookie_error = (
                f"Could not read {self._cookie_reference()}: {exc}"
            )
            return

        if not cookie_lines:
            self.cookie_error = (
                f"{self._cookie_reference()} is empty or invalid. Paste one "
                "semicolon-separated cookie line exported from iCloud settings."
            )
            return

        if len(cookie_lines) > 1:
            self._log(
                f'[bold yellow][WARN][/] {self._cookie_reference()} contains '
                "multiple cookie lines. Only the first non-comment line will be used."
            )

        self.cookies = cookie_lines[0]

    def _ensure_cookie_configured(self) -> bool:
        if self.cookies:
            return True

        err_msg = self.cookie_error or (
            f"No iCloud cookie is configured in {self._cookie_reference()}. "
            "Export fresh cookies from https://www.icloud.com/settings/ and "
            "save them before retrying."
        )
        self._log(f"[bold red][ERR][/] - {err_msg}")
        return False

    def _prompt_generation_mode(self) -> str:
        return normalize_generation_mode(
            Prompt.ask(
                "Generation mode",
                choices=[OLD_ACCOUNT_MODE, FRESH_ACCOUNT_MODE],
                default=OLD_ACCOUNT_MODE,
                console=self.console,
            )
        )

    def _format_duration(self, seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        minutes, remaining_seconds = divmod(total_seconds, 60)
        hours, remaining_minutes = divmod(minutes, 60)

        if hours:
            return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
        if minutes:
            return f"{minutes}m {remaining_seconds}s"
        return f"{remaining_seconds}s"

    def _format_error_message(self, response: dict) -> str:
        error = response["error"] if "error" in response else {}
        err_msg = "Unknown"
        if isinstance(error, int) and "reason" in response:
            err_msg = str(response["reason"])
        elif isinstance(error, dict) and "errorMessage" in error:
            err_msg = str(error["errorMessage"])
        elif "reason" in response:
            err_msg = str(response["reason"])

        normalized = err_msg.lower()

        if "global_session" in normalized or "unauthorized" in normalized:
            return (
                f"Apple rejected the iCloud session cookie from "
                f"{self._cookie_reference()}. The cookie is missing, expired, "
                "or stale. Export fresh cookies from https://www.icloud.com/settings/ "
                "and retry."
            )

        if any(
            token in normalized
            for token in ("rate limit", "too many", "throttl", "http 429")
        ):
            return (
                "Apple rate limit reached. Wait about 30 minutes before "
                "retrying, or reduce the number of concurrent requests."
            )

        if "invalid apple response" in normalized:
            return (
                "Apple returned an invalid response. The service may be "
                "temporarily unavailable, or the iCloud session may have "
                "expired. Retry once with fresh cookies."
            )

        return err_msg

    def _log_request_error(
        self, action: str, response: dict, email: Optional[str] = None
    ) -> None:
        err_msg = self._format_error_message(response)
        if email is None:
            self._log(
                f"[bold red][ERR][/] - Failed to {action}. Reason: {err_msg}"
            )
            return

        self._log(
            f'[bold red][ERR][/] "{email}" - Failed to {action}. Reason: {err_msg}'
        )

    async def _generate_one(self) -> Optional[str]:
        gen_res = await self.generate_email()
        if not gen_res:
            return None
        if "success" not in gen_res or not gen_res["success"]:
            self._log_request_error("generate email", gen_res)
            return None

        email = gen_res["result"]["hme"]
        self._log(f'[50%] "{email}" - Successfully generated')

        reserve_res = await self.reserve_email(email)
        if not reserve_res:
            return None
        if "success" not in reserve_res or not reserve_res["success"]:
            self._log_request_error("reserve email", reserve_res, email)
            return None

        self._log(f'[100%] "{email}" - Successfully reserved')
        return email

    async def _generate_batch(self, num: int) -> list[str]:
        tasks = []
        for _ in range(num):
            tasks.append(asyncio.create_task(self._generate_one()))

        results = await asyncio.gather(*tasks)
        return [email for email in results if email is not None]

    async def _generate_with_old_account_mode(
        self, count: int, show_status: bool = True
    ) -> list[str]:
        async def run_batches() -> list[str]:
            emails = []
            remaining = count
            while remaining > 0:
                batch = await self._generate_batch(
                    remaining if remaining < MAX_CONCURRENT_TASKS else MAX_CONCURRENT_TASKS
                )
                remaining -= MAX_CONCURRENT_TASKS
                emails.extend(batch)
            return emails

        if show_status:
            with self.console.status("[bold green]Generating iCloud email(s)..."):
                return await run_batches()
        return await run_batches()

    async def _generate_with_fresh_account_mode(
        self, count: int, show_status: bool = True
    ) -> list[str]:
        emails = []
        started_at = time.monotonic()
        estimated_duration = count * FRESH_ACCOUNT_SLOT_SECONDS

        self._log(
            "Fresh-account mode enabled: one generation attempt will be made "
            "in each 12-minute window, at a random time between minute 5 and 12."
        )
        self._log(
            f"Estimated total duration: up to about {self._format_duration(estimated_duration)}."
        )

        async def run_attempts() -> list[str]:
            for index in range(count):
                slot_start = started_at + (index * FRESH_ACCOUNT_SLOT_SECONDS)
                target_time = slot_start + random.uniform(
                    FRESH_ACCOUNT_MIN_DELAY_SECONDS,
                    FRESH_ACCOUNT_MAX_DELAY_SECONDS,
                )
                wait_seconds = max(0, target_time - time.monotonic())

                if wait_seconds > 0:
                    target_clock = (
                        datetime.datetime.now()
                        + datetime.timedelta(seconds=wait_seconds)
                    ).strftime("%H:%M:%S")
                    self._log(
                        f"[{index + 1}/{count}] Waiting "
                        f"{self._format_duration(wait_seconds)} before the next "
                        f'generation attempt (target {target_clock}).'
                    )
                    await asyncio.sleep(wait_seconds)

                email = await self._generate_one()
                if email is not None:
                    emails.append(email)

            return emails

        if show_status:
            with self.console.status("[bold green]Respecting Apple rate limit..."):
                return await run_attempts()
        return await run_attempts()

    async def generate(
        self,
        count: Optional[int],
        mode: Optional[str] = None,
        persist: bool = True,
        show_rules: bool = True,
        show_status: bool = True,
    ) -> list[str]:
        try:
            if not self._ensure_cookie_configured():
                return []

            prompted_interactively = False
            if show_rules:
                self.console.rule()

            if count is None:
                count = int(
                    IntPrompt.ask(
                        Text.assemble(("How many iCloud emails you want to generate?")),
                        console=self.console,
                    )
                )
                prompted_interactively = True

            if mode is None and prompted_interactively:
                mode = self._prompt_generation_mode()

            mode = normalize_generation_mode(mode)
            self._log(f'Generating {count} email(s) with mode "{mode}"...')

            if show_rules:
                self.console.rule()

            if mode == FRESH_ACCOUNT_MODE:
                emails = await self._generate_with_fresh_account_mode(
                    count, show_status=show_status
                )
            else:
                emails = await self._generate_with_old_account_mode(
                    count, show_status=show_status
                )

            if persist and emails:
                save_emails(emails)
                if show_rules:
                    self.console.rule()
                self._log(f':star: Emails have been saved into "{DEFAULT_EMAILS_FILE}"')
                self._log(
                    f"[bold green]All done![/] Successfully generated "
                    f"[bold green]{len(emails)}[/] email(s)"
                )

            return emails
        except KeyboardInterrupt:
            return []

    async def list(
        self,
        active: bool,
        search: Optional[str],
        export: Optional[str] = None,
        show_table: bool = True,
    ) -> list[dict[str, str]]:
        if not self._ensure_cookie_configured():
            return []

        gen_res = await self.list_email()
        if not gen_res:
            return []

        if "success" not in gen_res or not gen_res["success"]:
            self._log_request_error("list emails", gen_res)
            return []

        rows = []
        for row in gen_res["result"]["hmeEmails"]:
            if row["isActive"] != active:
                continue
            if search is not None and not re.search(search, row["label"]):
                continue

            rows.append(
                {
                    "label": row["label"],
                    "email": row["hme"],
                    "created": str(
                        datetime.datetime.fromtimestamp(
                            row["createTimestamp"] / 1000
                        )
                    ),
                    "active": str(row["isActive"]),
                }
            )

        if show_table:
            self.console.print(build_email_table(rows))
            if export and rows:
                export_email_rows(rows, export)
                self._log(f':star: {len(rows)} email(s) exported to "{export}"')

        return rows


async def generate_account(
    account: AccountConfig, console: Console
) -> tuple[AccountConfig, list[str]]:
    async with RichHideMyEmail(
        cookie_file=account.cookie_file,
        account_name=account.name,
        console=console,
    ) as hme:
        emails = await hme.generate(
            account.count,
            account.mode,
            persist=False,
            show_rules=False,
            show_status=False,
        )
        return account, emails


async def list_account(
    account: AccountConfig,
    active: bool,
    search: Optional[str],
    console: Console,
) -> tuple[AccountConfig, list[dict[str, str]]]:
    async with RichHideMyEmail(
        cookie_file=account.cookie_file,
        account_name=account.name,
        console=console,
    ) as hme:
        rows = await hme.list(active, search, show_table=False)
        return account, rows


async def generate_with_accounts_file(
    accounts_file: str,
    count: Optional[int],
    mode: Optional[str] = None,
) -> None:
    console = Console()
    try:
        accounts = load_accounts_config(
            accounts_file,
            default_count=count,
            default_mode=normalize_generation_mode(mode),
        )
    except ValueError as exc:
        console.log(f"[bold red][ERR][/] - {exc}")
        return

    missing_count_accounts = [account.name for account in accounts if account.count is None]
    if missing_count_accounts:
        console.log(
            "[bold red][ERR][/] - Every account must define a count in the "
            f'accounts file, or you must pass a global "--count". Missing count '
            f'for: {", ".join(missing_count_accounts)}'
        )
        return

    console.rule()
    console.log(
        f'Loaded {len(accounts)} account(s) from "{accounts_file}". Running generation in parallel.'
    )
    console.rule()

    results = await asyncio.gather(
        *(generate_account(account, console) for account in accounts)
    )

    all_emails = []
    console.rule()
    for account, emails in results:
        all_emails.extend(emails)
        console.log(
            f'({account.name}) Generated {len(emails)} email(s) with mode "{account.mode}".'
        )

    if all_emails:
        save_emails(all_emails)
        console.log(f':star: Emails have been saved into "{DEFAULT_EMAILS_FILE}"')

    console.log(
        f"[bold green]All done![/] Successfully generated "
        f"[bold green]{len(all_emails)}[/] email(s) across "
        f"[bold green]{len(accounts)}[/] account(s)"
    )


async def list_with_accounts_file(
    accounts_file: str,
    active: bool,
    search: Optional[str],
    export: Optional[str] = None,
) -> None:
    console = Console()
    try:
        accounts = load_accounts_config(accounts_file)
    except ValueError as exc:
        console.log(f"[bold red][ERR][/] - {exc}")
        return

    results = await asyncio.gather(
        *(list_account(account, active, search, console) for account in accounts)
    )

    all_rows = []
    for account, rows in results:
        for row in rows:
            row_with_account = dict(row)
            row_with_account["account"] = account.name
            all_rows.append(row_with_account)

    console.print(build_email_table(all_rows, include_account=True))

    if export and all_rows:
        export_email_rows(all_rows, export, include_account=True)
        console.log(f':star: {len(all_rows)} email(s) exported to "{export}"')


async def generate(
    count: Optional[int],
    mode: Optional[str] = None,
    accounts_file: Optional[str] = None,
) -> None:
    if accounts_file:
        await generate_with_accounts_file(accounts_file, count, mode)
        return

    async with RichHideMyEmail() as hme:
        await hme.generate(count, mode)


async def list(
    active: bool,
    search: Optional[str],
    export: Optional[str] = None,
    accounts_file: Optional[str] = None,
) -> None:
    if accounts_file:
        await list_with_accounts_file(accounts_file, active, search, export)
        return

    async with RichHideMyEmail() as hme:
        await hme.list(active, search, export)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(generate(None, None, None))
    except KeyboardInterrupt:
        pass
