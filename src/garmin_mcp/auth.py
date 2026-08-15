"""Garmin authentication.

`login` runs interactively in a terminal (it may prompt for an MFA code) and
writes an OAuth token file. `resume` is what the MCP server uses: it only ever
reads that file, because a stdio server cannot prompt for MFA.
"""

from __future__ import annotations

import os
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin

TOKENSTORE = Path(
    os.getenv("GARMINTOKENS", "~/.garminconnect/garmin_tokens.json")
).expanduser()


class NotAuthenticated(RuntimeError):
    """No usable token on disk; the user must run `garmin-mcp login`."""


def resume() -> Garmin:
    """Build a client from the stored token, refreshing it if it is near expiry."""
    if not TOKENSTORE.exists():
        raise NotAuthenticated(
            f"No Garmin token at {TOKENSTORE}. Run `garmin-mcp login` in a terminal."
        )
    api = Garmin()
    try:
        api.login(tokenstore=str(TOKENSTORE))
    except Exception as exc:
        raise NotAuthenticated(
            f"Stored Garmin token is unusable ({exc}). "
            "Run `garmin-mcp login` in a terminal to re-authenticate."
        ) from exc
    return api


def login() -> Path:
    """Authenticate interactively and persist the token. Returns the token path."""
    try:
        resume()
    except Exception:
        pass
    else:
        print(f"Already authenticated; token at {TOKENSTORE}")
        return TOKENSTORE

    email = input("Garmin email: ").strip()
    password = getpass("Garmin password: ")
    api = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA code: ").strip(),
    )
    TOKENSTORE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    api.login(tokenstore=str(TOKENSTORE))
    print(f"Logged in; token saved to {TOKENSTORE}")
    return TOKENSTORE
