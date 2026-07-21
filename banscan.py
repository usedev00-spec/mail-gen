"""Detect Amazon-ban aliases and deactivate them.

Amazon sends a ``baa-customer-appeal`` email to the Hide My Email alias tied to a
banned account. Those aliases keep forwarding, so this module:

1. Scans a Gmail inbox (over IMAP) that the aliases forward to, for Amazon emails
   whose subject contains ``baa-customer-appeal``, and extracts the alias each one
   was addressed to.
2. Maps each banned alias to the iCloud account (cookie file) that owns it, by
   cross-referencing every account's Hide My Email list.
3. Checks — with a non-destructive probe — whether the current cookies can actually
   deactivate an alias, then (after confirmation) deactivates the banned ones.

The Gmail mailbox is opened read-only with ``BODY.PEEK`` so nothing is ever marked
read or otherwise modified. The Gmail app password is never logged and lives only in
the git-ignored ``banscan.json`` (or the ``GMAIL_*`` env vars).
"""

import asyncio
import getpass
import imaplib
import json
import os
import random
import re
import ssl
import uuid
from email.parser import BytesParser
from email.policy import default as default_policy
from email.utils import getaddresses

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from main import (
    DEFAULT_ACCOUNTS_FILE,
    DEFAULT_COOKIE_FILE,
    AccountConfig,
    RichHideMyEmail,
    filter_accounts,
    load_accounts_config,
)

DEFAULT_GMAIL_CONFIG = "banscan.json"

# Session/auth failures Apple reports; mirrors RichHideMyEmail._format_error_message.
_AUTH_TOKENS = ("global_session", "unauthorized")

# Headers that can carry the alias a forwarded message was addressed to. iCloud
# rewrites/forwards to the real inbox but the alias survives in one of these.
_RECIPIENT_HEADERS = (
    "To",
    "Cc",
    "Bcc",
    "Delivered-To",
    "X-Original-To",
    "X-Forwarded-To",
    "Resent-To",
    "Envelope-To",
)

# "...for <alias@icloud.com>;" inside a Received header — another place the alias
# reliably shows up on forwarded mail.
_RECEIVED_FOR_RE = re.compile(r"for\s+<?([^\s<>;]+@[^\s<>;]+)>?", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Pure helpers (no network / no I/O — unit-tested in tests/test_ban_scan.py)
# --------------------------------------------------------------------------- #
def extract_recipient_addresses(raw_header_bytes) -> set[str]:
    """Return every recipient-side address found in a raw header block.

    Parses only the headers (the fetch uses ``BODY.PEEK[HEADER]``) and collects
    addresses from the recipient headers plus any ``Received ... for <addr>``.
    Lower-cased. Not filtered by domain — the caller intersects the result with
    the set of known aliases, so it doesn't matter that this also returns the
    Gmail destination address or other noise.
    """
    if isinstance(raw_header_bytes, str):
        raw_header_bytes = raw_header_bytes.encode("utf-8", "replace")

    msg = BytesParser(policy=default_policy).parsebytes(raw_header_bytes)

    header_values: list[str] = []
    for header in _RECIPIENT_HEADERS:
        header_values.extend(str(value) for value in msg.get_all(header, []))

    addresses = {
        addr.lower()
        for _name, addr in getaddresses(header_values)
        if addr
    }

    for received in msg.get_all("Received", []):
        for match in _RECEIVED_FOR_RE.finditer(str(received)):
            addresses.add(match.group(1).lower().strip(".;,"))

    addresses.discard("")
    return addresses


def map_banned_to_accounts(
    candidates: set[str],
    aliases_by_account: dict[str, dict[str, dict]],
) -> tuple[dict[str, list[dict]], set[str]]:
    """Split banned candidate addresses across the accounts that own them.

    ``aliases_by_account`` maps ``account_name -> {alias_lower -> record}``.
    Returns ``(banned_by_account, orphans)`` where ``banned_by_account`` maps
    ``account_name -> [record, ...]`` and ``orphans`` are candidate addresses that
    belong to no configured account (the Gmail address itself, aliases on an
    account not in the config, etc.).
    """
    candidates = {c.lower() for c in candidates}
    banned_by_account: dict[str, list[dict]] = {}
    matched: set[str] = set()

    for name, alias_map in aliases_by_account.items():
        hits = [alias_map[alias] for alias in candidates if alias in alias_map]
        if hits:
            banned_by_account[name] = hits
            matched.update(alias for alias in candidates if alias in alias_map)

    orphans = candidates - matched
    return banned_by_account, orphans


def _response_blob(response) -> str:
    try:
        return json.dumps(response, default=str).lower()
    except (TypeError, ValueError):
        return str(response).lower()


def classify_deactivate_probe(response) -> str:
    """Classify a probe ``deactivate`` response into a capability verdict.

    - ``"unauthorized"``: the cookies are stale/rejected (auth token in the body).
    - ``"ambiguous"``: a transport-level failure we generated ourselves (timeout,
      network error, rate limit, empty/invalid body) — can't tell, caller should
      fall back to a round-trip test.
    - ``"ok"``: Apple accepted the session; the bogus ``anonymousId`` was simply
      rejected on its own merits, so real deactivations will work.
    """
    if not isinstance(response, dict):
        return "ambiguous"

    if any(token in _response_blob(response) for token in _AUTH_TOKENS):
        return "unauthorized"

    # Our own transport error dicts look like {"error": 1, "reason": ...} and
    # never carry a "success" key (that only comes from a parsed Apple body).
    if "success" not in response and response.get("error") == 1:
        return "ambiguous"

    return "ok"


# --------------------------------------------------------------------------- #
# Gmail IMAP (blocking — run via asyncio.to_thread)
# --------------------------------------------------------------------------- #
def load_gmail_config(
    path: str = DEFAULT_GMAIL_CONFIG,
    console: Console | None = None,
    allow_prompt: bool = True,
) -> dict:
    """Load Gmail IMAP settings from ``path``, env vars, or an interactive prompt.

    Precedence: ``GMAIL_ADDRESS`` / ``GMAIL_APP_PASSWORD`` env vars override the
    file. If address or app password is still missing and ``allow_prompt`` is set,
    ask for them (password via ``getpass``, never echoed) and offer to save them to
    the git-ignored config file with 0600 permissions.
    """
    config: dict = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'Could not read Gmail config "{path}": {exc}') from exc
        if not isinstance(config, dict):
            raise ValueError(f'Gmail config "{path}" must be a JSON object.')

    env_address = os.environ.get("GMAIL_ADDRESS")
    env_password = os.environ.get("GMAIL_APP_PASSWORD")
    if env_address:
        config["address"] = env_address
    if env_password:
        config["app_password"] = env_password

    if not config.get("address") or not config.get("app_password"):
        if not allow_prompt:
            raise ValueError(
                f'Gmail address / app password not configured. Create "{path}" '
                f"(see {path.replace('.json', '.example.json')}) or set the "
                "GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables."
            )
        console = console or Console()
        console.print(
            "[dim]No Gmail credentials found. Enter the Gmail account your aliases "
            "forward to (an app password is required — Gmail settings → Security → "
            "App passwords).[/]"
        )
        if not config.get("address"):
            config["address"] = Prompt.ask("Gmail address", console=console)
        if not config.get("app_password"):
            config["app_password"] = getpass.getpass("Gmail app password (hidden): ")
        if Confirm.ask(
            f'Save these to "{path}" (git-ignored) for next time?',
            default=True,
            console=console,
        ):
            _save_gmail_config(path, config)
            console.print(f'[dim]Saved to "{path}".[/]')

    config.setdefault("imap_host", "imap.gmail.com")
    config.setdefault("imap_port", 993)
    config.setdefault("from_query", "amazon")
    config.setdefault("subject_query", "baa-customer-appeal")
    return config


def _save_gmail_config(path: str, config: dict) -> None:
    """Persist the Gmail config with owner-only (0600) permissions."""
    payload = {
        "address": config.get("address", ""),
        "app_password": config.get("app_password", ""),
        "imap_host": config.get("imap_host", "imap.gmail.com"),
        "imap_port": config.get("imap_port", 993),
        "from_query": config.get("from_query", "amazon"),
        "subject_query": config.get("subject_query", "baa-customer-appeal"),
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _quote_mailbox(name: str) -> str:
    return '"' + name.replace('"', '\\"') + '"'


def _imap_quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


def _find_all_mail_mailbox(imap: imaplib.IMAP4) -> str:
    """Return the mailbox flagged ``\\All`` (Gmail "All Mail"), else "INBOX".

    Using the special-use flag rather than a hard-coded name keeps this working
    across Gmail locales (e.g. "[Gmail]/Tous les messages" in French).
    """
    try:
        typ, data = imap.list()
    except imaplib.IMAP4.error:
        return "INBOX"
    if typ != "OK" or not data:
        return "INBOX"
    for line in data:
        if line is None:
            continue
        decoded = line.decode(errors="replace") if isinstance(line, bytes) else str(line)
        if "\\All" in decoded:
            match = re.search(r'"([^"]*)"\s*$', decoded)
            if match:
                return match.group(1)
            return decoded.split()[-1]
    return "INBOX"


def scan_ban_recipients(config: dict) -> tuple[int, set[str]]:
    """Search Gmail for Amazon ban emails and return (count, recipient aliases).

    Blocking (imaplib); call from async code via ``asyncio.to_thread``. Selects the
    mailbox read-only and fetches with ``BODY.PEEK`` so the inbox is never touched.
    """
    host = config.get("imap_host", "imap.gmail.com")
    port = int(config.get("imap_port", 993))
    address = config["address"]
    password = config["app_password"]
    from_query = config.get("from_query", "amazon")
    subject_query = config.get("subject_query", "baa-customer-appeal")

    imap = imaplib.IMAP4_SSL(host, port)
    try:
        imap.login(address, password)

        mailbox = _find_all_mail_mailbox(imap)
        typ, _ = imap.select(_quote_mailbox(mailbox), readonly=True)
        if typ != "OK":
            imap.select("INBOX", readonly=True)

        typ, data = imap.search(
            None, "FROM", _imap_quote(from_query), "SUBJECT", _imap_quote(subject_query)
        )
        if typ != "OK" or not data or not data[0]:
            return 0, set()

        ids = data[0].split()
        recipients: set[str] = set()
        for num in ids:
            typ, msg_data = imap.fetch(num, "(BODY.PEEK[HEADER])")
            if typ != "OK" or not msg_data:
                continue
            for part in msg_data:
                if isinstance(part, tuple) and part[1]:
                    recipients |= extract_recipient_addresses(part[1])
        return len(ids), recipients
    finally:
        try:
            imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


# --------------------------------------------------------------------------- #
# iCloud side (async)
# --------------------------------------------------------------------------- #
async def _fetch_account_records(
    account: AccountConfig, console: Console
) -> tuple[AccountConfig, list[dict], str | None]:
    """Return (account, raw hme records, error). Records include ``anonymousId``."""
    async with RichHideMyEmail(
        cookie_file=account.cookie_file,
        account_name=account.name,
        console=console,
    ) as hme:
        if not hme._ensure_cookie_configured():
            return account, [], hme.cookie_error or "cookie non configuré"
        response = await hme.list_email()
        if not isinstance(response, dict) or not response.get("success"):
            message = (
                hme._format_error_message(response)
                if isinstance(response, dict)
                else "réponse vide"
            )
            return account, [], message
        records = response.get("result", {}).get("hmeEmails", []) or []
        return account, records, None


async def probe_account_deactivation(
    hme: RichHideMyEmail, records: list[dict]
) -> tuple[str, str]:
    """Verify the current cookies can deactivate. Returns (verdict, method).

    ``verdict`` in {"ok", "unauthorized", "unknown"}. First runs a non-destructive
    probe (deactivate with a bogus anonymousId). If that's ambiguous, falls back to
    a deactivate/reactivate round-trip on a real alias, restoring its state.
    """
    probe = await hme.deactivate_email(uuid.uuid4().hex)
    verdict = classify_deactivate_probe(probe)
    if verdict in ("ok", "unauthorized"):
        return verdict, "sonde"

    # Ambiguous probe → round-trip on a real alias, then restore its state.
    record = records[0] if records else None
    anonymous_id = record.get("anonymousId") if record else None
    if not anonymous_id:
        return "unknown", "sonde ambiguë, aucun alias exploitable pour le repli"

    was_active = bool(record.get("isActive"))
    if was_active:
        first = await hme.deactivate_email(anonymous_id)
        await hme.reactivate_email(anonymous_id)
    else:
        first = await hme.reactivate_email(anonymous_id)
        await hme.deactivate_email(anonymous_id)

    ok = isinstance(first, dict) and bool(first.get("success"))
    return ("ok" if ok else "unauthorized"), "aller-retour"


async def _deactivate_records(
    hme: RichHideMyEmail,
    records: list[dict],
    console: Console,
    account_name: str,
) -> tuple[list[str], list[tuple[str, str]]]:
    deactivated: list[str] = []
    failed: list[tuple[str, str]] = []
    for index, record in enumerate(records):
        alias = str(record.get("hme", "?"))
        anonymous_id = record.get("anonymousId")
        if not anonymous_id:
            failed.append((alias, "anonymousId manquant"))
            console.log(f"({account_name}) [red]✗ {alias} — anonymousId manquant[/]")
            continue

        response = await hme.deactivate_email(anonymous_id)
        if isinstance(response, dict) and response.get("success"):
            deactivated.append(alias)
            console.log(f"({account_name}) [green]✓ désactivé[/] : {alias}")
        else:
            message = (
                hme._format_error_message(response)
                if isinstance(response, dict)
                else "réponse invalide"
            )
            failed.append((alias, message))
            console.log(f"({account_name}) [red]✗ échec[/] {alias} : {message}")

        # Gentle, human-ish pacing between actions on the same account.
        if index < len(records) - 1:
            await asyncio.sleep(random.uniform(1.0, 3.0))

    return deactivated, failed


def _resolve_accounts(
    accounts_file: str | None,
    account_names: list[str] | None,
    cookie_file: str | None,
    account_name: str | None,
) -> list[AccountConfig]:
    """Resolve the selection tuple used across the CLI into AccountConfig list."""
    if cookie_file or account_name:
        return [
            AccountConfig(
                name=account_name or "default",
                cookie_file=cookie_file or DEFAULT_COOKIE_FILE,
            )
        ]
    if accounts_file:
        accounts = load_accounts_config(accounts_file)
        if account_names:
            accounts = filter_accounts(accounts, account_names)
        return accounts
    return [AccountConfig(name="default", cookie_file=DEFAULT_COOKIE_FILE)]


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
async def run_ban_check(
    accounts_file: str | None = None,
    account_names: list[str] | None = None,
    cookie_file: str | None = None,
    account_name: str | None = None,
    dry_run: bool = False,
    assume_yes: bool = False,
    gmail_config_path: str = DEFAULT_GMAIL_CONFIG,
    console: Console | None = None,
) -> None:
    console = console or Console()

    # 1) Scan Gmail for Amazon ban emails and extract recipient aliases.
    try:
        gmail_config = load_gmail_config(gmail_config_path, console=console)
    except ValueError as exc:
        console.log(f"[bold red][ERR][/] {exc}")
        return

    console.rule("[bold green]Scan des mails de ban Amazon")
    console.log(
        f"Connexion IMAP à {gmail_config['imap_host']} "
        f"({gmail_config['address']})…"
    )
    try:
        count, candidates = await asyncio.to_thread(scan_ban_recipients, gmail_config)
    except imaplib.IMAP4.error as exc:
        console.log(
            f"[bold red][ERR][/] Échec IMAP : {exc}. Vérifie le mot de passe "
            "d'application Gmail et que l'accès IMAP est activé."
        )
        return
    except (OSError, ssl.SSLError) as exc:
        console.log(f"[bold red][ERR][/] Connexion IMAP impossible : {exc}")
        return

    candidates.discard(gmail_config["address"].lower())
    console.log(
        f'{count} mail(s) « {gmail_config["subject_query"]} » d\'Amazon trouvé(s), '
        f"{len(candidates)} adresse(s) destinataire(s) extraite(s)."
    )
    if candidates:
        console.print(
            "[dim]Alias destinataires extraits :[/] "
            + ", ".join(sorted(candidates))
        )
    if not candidates:
        console.log("[green]Aucun alias banni détecté. Rien à faire.[/]")
        return

    # 2) List every account's aliases (in parallel) to know who owns what.
    try:
        accounts = _resolve_accounts(
            accounts_file, account_names, cookie_file, account_name
        )
    except ValueError as exc:
        console.log(f"[bold red][ERR][/] {exc}")
        return

    console.rule("[bold green]Comptes iCloud")
    results = await asyncio.gather(
        *(_fetch_account_records(account, console) for account in accounts)
    )

    accounts_by_name: dict[str, AccountConfig] = {}
    aliases_by_account: dict[str, dict[str, dict]] = {}
    records_by_account: dict[str, list[dict]] = {}
    for account, records, error in results:
        accounts_by_name[account.name] = account
        if error:
            console.log(f"({account.name}) [yellow]⚠ liste indisponible : {error}[/]")
            continue
        alias_map = {
            (record.get("hme") or "").lower(): record
            for record in records
            if record.get("hme")
        }
        aliases_by_account[account.name] = alias_map
        records_by_account[account.name] = records
        console.log(f"({account.name}) {len(records)} alias au total.")

    # 3) Map banned aliases to their accounts and report per account.
    banned_by_account, orphans = map_banned_to_accounts(candidates, aliases_by_account)

    console.rule("[bold green]Alias bannis par compte iCloud")
    if not banned_by_account:
        console.log(
            "[green]Aucun des alias bannis ne correspond à un compte iCloud "
            "configuré.[/]"
        )
    for name, records in banned_by_account.items():
        table = Table(
            title=f"Compte iCloud « {name} » — {len(records)} alias banni(s)"
        )
        table.add_column("Label")
        table.add_column("Alias")
        table.add_column("État")
        for record in records:
            state = "[green]actif[/]" if record.get("isActive") else "[dim]inactif[/]"
            table.add_row(
                str(record.get("label", "")), str(record.get("hme", "")), state
            )
        console.print(table)
    if orphans:
        console.log(
            f"[yellow]{len(orphans)} adresse(s) bannie(s) sans compte iCloud "
            f"configuré (ignorée(s)) : {', '.join(sorted(orphans))}[/]"
        )

    if not banned_by_account:
        return

    # 4) Per account: probe deactivation capability, then (confirm →) deactivate.
    console.rule("[bold green]Vérification & désactivation")
    total_deactivated = total_failed = total_skipped = 0

    for name, banned in banned_by_account.items():
        account = accounts_by_name[name]
        async with RichHideMyEmail(
            cookie_file=account.cookie_file,
            account_name=account.name,
            console=console,
        ) as hme:
            if not hme._ensure_cookie_configured():
                total_skipped += len(banned)
                continue

            verdict, method = await probe_account_deactivation(
                hme, records_by_account.get(name, [])
            )
            if verdict == "unauthorized":
                console.log(
                    f"({name}) [bold red]✗ Impossible de désactiver avec ces "
                    "cookies[/] (session iCloud périmée). Réexporte des cookies "
                    "frais depuis icloud.com/settings puis relance."
                )
                total_skipped += len(banned)
                continue
            if verdict == "unknown":
                console.log(
                    f"({name}) [yellow]⚠ Capacité de désactivation non confirmée "
                    "(sonde ambiguë). On tentera quand même après confirmation.[/]"
                )
            else:
                console.log(
                    f"({name}) [green]✓ Cookies OK pour désactiver[/] "
                    f"(test : {method})."
                )

            active = [record for record in banned if record.get("isActive")]
            already_inactive = len(banned) - len(active)
            if already_inactive:
                console.log(
                    f"({name}) {already_inactive} alias banni(s) déjà inactif(s) — "
                    "ignoré(s)."
                )
                total_skipped += already_inactive
            if not active:
                console.log(f"({name}) Aucun alias banni actif à désactiver.")
                continue

            if dry_run:
                console.log(
                    f"({name}) [cyan]Dry-run[/] : {len(active)} alias seraient "
                    "désactivés (aucune action réelle)."
                )
                continue

            proceed = assume_yes or Confirm.ask(
                f"Désactiver les {len(active)} alias banni(s) actif(s) du compte "
                f"« {name} » ?",
                default=False,
                console=console,
            )
            if not proceed:
                console.log(f"({name}) Ignoré (pas de confirmation).")
                total_skipped += len(active)
                continue

            deactivated, failed = await _deactivate_records(hme, active, console, name)
            total_deactivated += len(deactivated)
            total_failed += len(failed)

    console.rule("[bold green]Résumé")
    console.log(
        f"[bold]Désactivés : {total_deactivated}  |  "
        f"Ignorés : {total_skipped}  |  Échecs : {total_failed}[/]"
    )
