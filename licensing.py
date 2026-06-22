"""Offline access-key verification for the iCloud HideMyEmail tool.

Access keys are Ed25519-signed payloads minted by the private ``keygen.py`` tool.
Only the public key ships here (it is safe to publish), so keys can be verified
fully offline — no server, no database. Keys cannot be forged without the private
key, which never leaves the issuer.
"""

import base64
import datetime
import json
import os
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from rich.console import Console
from rich.prompt import Prompt

# Public verification key (hex), produced by `python3 keygen.py --pubkey`.
# Safe to ship: it can only verify keys, never create them.
PUBLIC_KEY_HEX = "a38b59463eaa4b177ad5de1e2ac1c750d14aa02631ce5af7e33220f8e822f846"

ENV_VAR = "HIDEMYEMAIL_KEY"
LICENSE_PATH = Path.home() / ".hidemyemail" / "license.key"
MAX_PROMPT_ATTEMPTS = 3


def _public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))


def _unpad_b64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _split(key: str) -> tuple[bytes, bytes]:
    payload_b64, signature_b64 = key.strip().split(".")
    return _unpad_b64(payload_b64), _unpad_b64(signature_b64)


def verify(key: str) -> bool:
    """Return True if `key` is genuine and not expired."""
    if not key:
        return False

    try:
        payload, signature = _split(key)
    except (ValueError, AttributeError):
        return False

    try:
        _public_key().verify(signature, payload)
    except InvalidSignature:
        return False

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False

    expiry = data.get("exp")
    if expiry is not None and str(expiry) < datetime.date.today().isoformat():
        return False

    return True


def key_info(key: str) -> dict:
    """Decoded payload of a key (does NOT verify it)."""
    payload, _ = _split(key)
    return json.loads(payload)


def load_saved_key() -> Optional[str]:
    try:
        return LICENSE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def save_key(key: str) -> None:
    LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_PATH.write_text(key.strip(), encoding="utf-8")


def has_valid_license() -> bool:
    """True if a saved file or the env var holds a valid key."""
    for candidate in (load_saved_key(), os.getenv(ENV_VAR)):
        if candidate and verify(candidate):
            return True
    return False


def require_license(console: Optional[Console] = None) -> None:
    """Ensure a valid access key is present, prompting to paste one if needed.

    Resolution order: saved file -> environment variable -> interactive prompt.
    Exits the program if no valid key is supplied.
    """
    if has_valid_license():
        return

    console = console or Console()
    console.print(
        "\n[bold yellow]An access key is required to use this tool.[/]\n"
        f"Paste your key below, or set the [bold]{ENV_VAR}[/] environment variable."
    )

    for _ in range(MAX_PROMPT_ATTEMPTS):
        key = Prompt.ask("[bold]Access key", console=console).strip()
        if verify(key):
            save_key(key)
            console.print("[green]✓ Access key accepted.[/]\n")
            return
        console.print("[red]✗ Invalid or expired key. Please try again.[/]")

    console.print("[red]No valid access key provided. Exiting.[/]")
    raise SystemExit(1)
