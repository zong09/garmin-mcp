"""Shared Garmin client plus helpers that shrink Garmin's very wide payloads.

Garmin returns hundreds of fields per record, most of them null, internal ids,
or GMT duplicates of a local timestamp. Returning that raw would burn tens of
thousands of tokens per call, so every tool trims before returning.
"""

from __future__ import annotations

from typing import Any

from garminconnect import Garmin

from .auth import resume

_api: Garmin | None = None

# Substrings matched against key names; these carry no meaning for analysis.
NOISE = (
    "uuid",
    "userprofile",
    "ownerid",
    "ownerdisplay",
    "ownerfull",
    "ownerprofileimage",
    "deviceid",
    "privacy",
    "imageurl",
    "gmt",
)


def api() -> Garmin:
    """Return the process-wide client, creating it from the stored token once."""
    global _api
    if _api is None:
        _api = resume()
    return _api


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, (str, dict, list)) and not value)


def prune(obj: Any) -> Any:
    """Recursively drop nulls, empty values, and noise keys."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if any(n in key.lower() for n in NOISE):
                continue
            value = prune(value)
            if not _empty(value):
                out[key] = value
        return out
    if isinstance(obj, list):
        return [v for v in (prune(v) for v in obj) if not _empty(v)]
    return obj


def no_series(obj: Any, max_len: int = 12) -> Any:
    """Recursively drop long lists — Garmin embeds per-minute sample arrays in
    otherwise small summary payloads."""
    if isinstance(obj, dict):
        return {
            k: no_series(v, max_len)
            for k, v in obj.items()
            if not (isinstance(v, list) and len(v) > max_len)
        }
    if isinstance(obj, list):
        return [no_series(v, max_len) for v in obj]
    return obj


def compact(obj: Any) -> Any:
    """prune + no_series: the default shape for summary endpoints."""
    return no_series(prune(obj))


def pick(data: dict[str, Any], *paths: str) -> dict[str, Any]:
    """Select fields by dotted path, keyed by the last path segment.

    Paths that are absent are simply omitted, so a Garmin schema change drops a
    field instead of raising.
    """
    out: dict[str, Any] = {}
    for path in paths:
        value: Any = data
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is not None:
            out[path.rsplit(".", 1)[-1]] = value
    return out
