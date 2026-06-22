import asyncio
import builtins
import csv
import datetime
import json
import math
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from rich.console import Console
from rich.prompt import FloatPrompt, IntPrompt, Prompt
from rich.table import Table

from icloud import HideMyEmail


DEFAULT_COOKIE_FILE = "cookie.txt"
DEFAULT_ACCOUNTS_FILE = "accounts.json"
DEFAULT_EMAILS_FILE = "emails.txt"

# Safety limits that keep an iCloud account from being flagged. These are the
# real-world ceilings observed when generating HideMyEmail aliases.
MAX_PER_HOUR = 5
MAX_PER_DAY = 25
# Comfortable default pace used to suggest a run duration (aliases per hour).
COMFORTABLE_PER_HOUR = 4
# Never fire two generations closer than this, even when no rolling limit binds.
MIN_GAP_SECONDS = 90
# Small buffer added on top of the rolling windows so we stay strictly under.
SCHEDULE_GAP_BUFFER_SECONDS = 30

HOUR_SECONDS = 60 * 60
DAY_SECONDS = 24 * HOUR_SECONDS


@dataclass
class AccountConfig:
    name: str
    cookie_file: str
    count: Optional[int] = None
    daily_limit: int = MAX_PER_DAY
    duration_hours: Optional[float] = None


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    days, remaining_hours = divmod(hours, 24)

    if days:
        return f"{days}d {remaining_hours}h {remaining_minutes}m"
    if hours:
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def minimum_safe_duration_seconds(count: int, daily_limit: int) -> float:
    """Shortest run that still respects MAX_PER_HOUR and the daily limit.

    Computed by packing the generations as early as the rolling-window limits
    allow (the schedule with a zero-length window), so it accounts for the
    combined hour/day constraints exactly.
    """
    if count <= 1:
        return 0.0
    schedule = build_generation_schedule(count, 0.0, daily_limit)
    return schedule[-1] if schedule else 0.0


def suggested_duration_hours(count: int, daily_limit: int) -> float:
    """A comfortable, human run length for `count` aliases (in hours)."""
    if count <= 1:
        return 1.0
    comfortable = count / COMFORTABLE_PER_HOUR
    min_safe = minimum_safe_duration_seconds(count, daily_limit) / HOUR_SECONDS
    return float(max(1, math.ceil(max(comfortable, min_safe))))


def build_generation_schedule(
    count: int, duration_seconds: float, daily_limit: int
) -> list[float]:
    """Offsets (seconds from start) for `count` generations.

    Guarantees at most MAX_PER_HOUR per rolling hour and `daily_limit` per
    rolling day, while spreading the work across `duration_seconds` with random,
    human-looking timing. If the window is too short to stay safe, the schedule
    is automatically extended past it.
    """
    offsets: list[float] = []
    slot = duration_seconds / count if count > 0 else 0.0
    for i in range(count):
        # Human target: a random point inside this alias' time slot.
        target = i * slot + random.uniform(0.2, 0.9) * slot
        earliest = 0.0
        if i >= MAX_PER_HOUR:
            earliest = max(
                earliest,
                offsets[i - MAX_PER_HOUR] + HOUR_SECONDS + SCHEDULE_GAP_BUFFER_SECONDS,
            )
        if i >= daily_limit:
            earliest = max(
                earliest,
                offsets[i - daily_limit] + DAY_SECONDS + SCHEDULE_GAP_BUFFER_SECONDS,
            )
        if offsets:
            earliest = max(earliest, offsets[-1] + MIN_GAP_SECONDS)
        offsets.append(max(target, earliest))
    return offsets


def analyze_plan(
    count: int, duration_seconds: float, daily_limit: int
) -> list[str]:
    """Human-readable warnings for an unsafe generation plan (empty if safe)."""
    warnings: list[str] = []

    if count > 1:
        min_safe = minimum_safe_duration_seconds(count, daily_limit)
        if duration_seconds < min_safe:
            window = "instant" if duration_seconds <= 0 else format_duration(duration_seconds)
            warnings.append(
                f"The requested {window} window is too short to stay within "
                f"{MAX_PER_HOUR}/hour and {daily_limit}/day. The run will be "
                f"automatically extended to about {format_duration(min_safe)} "
                "to protect the account."
            )

    if daily_limit > MAX_PER_DAY:
        warnings.append(
            f"Daily limit of {daily_limit} exceeds the recommended {MAX_PER_DAY}/day; "
            "higher values increase the risk of the iCloud account being flagged."
        )

    return warnings


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


def parse_account_daily_limit(value: Any, fallback: int, index: int) -> int:
    if value is None:
        return fallback

    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(
            f'Account #{index} has an invalid "daily_limit". It must be a '
            "positive integer."
        )

    return value


def parse_account_duration_hours(
    value: Any, fallback: Optional[float], index: int
) -> Optional[float]:
    if value is None:
        return fallback

    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(
            f'Account #{index} has an invalid "duration_hours". It must be a '
            "non-negative number."
        )

    return float(value)


def load_accounts_config(
    accounts_file: str,
    default_count: Optional[int] = None,
    default_daily_limit: int = MAX_PER_DAY,
    default_duration_hours: Optional[float] = None,
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

        account_count = parse_account_count(
            item.get("count"), default_count, index
        )
        account_daily_limit = parse_account_daily_limit(
            item.get("daily_limit"), default_daily_limit, index
        )
        account_duration_hours = parse_account_duration_hours(
            item.get("duration_hours"), default_duration_hours, index
        )

        accounts.append(
            AccountConfig(
                name=account_name,
                cookie_file=cookie_file,
                count=account_count,
                daily_limit=account_daily_limit,
                duration_hours=account_duration_hours,
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

    def _format_duration(self, seconds: float) -> str:
        return format_duration(seconds)

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

    async def _countdown(self, status, index, total, target_monotonic) -> None:
        """Tick a live, second-by-second countdown until ``target_monotonic``."""
        target_clock = (
            datetime.datetime.now()
            + datetime.timedelta(seconds=max(0.0, target_monotonic - time.monotonic()))
        ).strftime("%H:%M:%S")
        while True:
            remaining = target_monotonic - time.monotonic()
            if remaining <= 0:
                break
            status.update(
                f"[bold green]Next alias [{index + 1}/{total}] at {target_clock}[/] "
                f"— [bold]{self._format_duration(remaining)}[/] remaining"
            )
            await asyncio.sleep(min(1.0, remaining))

    async def _run_schedule(
        self, schedule: list[float], show_status: bool = True
    ) -> list[str]:
        emails: list[str] = []
        total = len(schedule)
        started_at = time.monotonic()

        async def run_attempts(status=None) -> list[str]:
            for index, offset in enumerate(schedule):
                target_monotonic = started_at + offset
                wait_seconds = target_monotonic - time.monotonic()

                if wait_seconds > 0:
                    if status is not None:
                        await self._countdown(status, index, total, target_monotonic)
                    else:
                        target_clock = (
                            datetime.datetime.now()
                            + datetime.timedelta(seconds=wait_seconds)
                        ).strftime("%H:%M:%S")
                        self._log(
                            f"[{index + 1}/{total}] Next alias at {target_clock} "
                            f"(in {self._format_duration(wait_seconds)})."
                        )
                        await asyncio.sleep(wait_seconds)

                email = await self._generate_one()
                if email is not None:
                    emails.append(email)

            return emails

        if show_status:
            with self.console.status(
                "[bold green]Generating aliases at a safe, human pace..."
            ) as status:
                return await run_attempts(status)
        return await run_attempts()

    def _resolve_count(self, count: Optional[int]) -> int:
        if count is not None:
            return count
        return IntPrompt.ask(
            "How many iCloud aliases do you want to generate?",
            console=self.console,
        )

    def _resolve_daily_limit(self, daily_limit: Optional[int]) -> int:
        if daily_limit is not None:
            return max(1, daily_limit)
        return IntPrompt.ask(
            "Maximum aliases per calendar day?",
            default=MAX_PER_DAY,
            console=self.console,
        )

    def _resolve_duration_hours(
        self, count: int, daily_limit: int, duration_hours: Optional[float]
    ) -> float:
        if duration_hours is not None:
            return max(0.0, duration_hours)
        return FloatPrompt.ask(
            "Spread the run over how many hours?",
            default=suggested_duration_hours(count, daily_limit),
            console=self.console,
        )

    async def generate(
        self,
        count: Optional[int],
        daily_limit: Optional[int] = None,
        duration_hours: Optional[float] = None,
        persist: bool = True,
        show_rules: bool = True,
        show_status: bool = True,
    ) -> list[str]:
        try:
            if not self._ensure_cookie_configured():
                return []

            if show_rules:
                self.console.rule()

            count = self._resolve_count(count)
            if count <= 0:
                self._log("Nothing to generate (count is 0).")
                return []

            daily_limit = self._resolve_daily_limit(daily_limit)
            duration_hours = self._resolve_duration_hours(
                count, daily_limit, duration_hours
            )
            duration_seconds = duration_hours * HOUR_SECONDS

            for warning in analyze_plan(count, duration_seconds, daily_limit):
                self._log(f"[bold yellow][WARN][/] {warning}")

            schedule = build_generation_schedule(
                count, duration_seconds, daily_limit
            )
            total_span = schedule[-1] if schedule else 0.0
            self._log(
                f"Generating {count} alias(es) over ~{self._format_duration(total_span)} "
                f"(max {MAX_PER_HOUR}/hour, {daily_limit}/day)."
            )

            if show_rules:
                self.console.rule()

            emails = await self._run_schedule(schedule, show_status=show_status)

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
            account.daily_limit,
            account.duration_hours,
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
    daily_limit: Optional[int] = None,
    duration_hours: Optional[float] = None,
) -> None:
    console = Console()
    try:
        accounts = load_accounts_config(
            accounts_file,
            default_count=count,
            default_daily_limit=daily_limit if daily_limit is not None else MAX_PER_DAY,
            default_duration_hours=duration_hours,
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
            f"({account.name}) Generated {len(emails)} email(s)."
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
    daily_limit: Optional[int] = None,
    duration_hours: Optional[float] = None,
    accounts_file: Optional[str] = None,
) -> None:
    if accounts_file:
        await generate_with_accounts_file(
            accounts_file, count, daily_limit, duration_hours
        )
        return

    async with RichHideMyEmail() as hme:
        await hme.generate(count, daily_limit, duration_hours)


async def list_emails(
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
    import licensing

    licensing.require_license()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(generate(None, None, None, None))
    except KeyboardInterrupt:
        pass
