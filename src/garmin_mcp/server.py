"""Read-only MCP tools over Garmin Connect.

Units follow Garmin's own: distance in metres, duration in seconds, speed in
metres/second, weight in grams.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Callable

from mcp.server import MCPServer

from .auth import TOKENSTORE
from .client import api, compact, pick, prune

mcp = MCPServer(
    name="garmin",
    version="0.1.0",
    instructions=(
        "Read-only access to the signed-in user's Garmin Connect data. "
        "Dates are ISO YYYY-MM-DD in the user's local timezone, as recorded by "
        "the watch. Distances are metres, durations seconds, speeds m/s."
    ),
)


def _day(value: str | None) -> str:
    return value or _date.today().isoformat()


def _try(fn: Callable[..., Any], *args: Any) -> Any:
    """Call an endpoint that legitimately has no data on some days."""
    try:
        return fn(*args)
    except Exception:
        return None


def _first(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return value[0] if value else {}
    return value if isinstance(value, dict) else {}


@mcp.tool()
def check_auth() -> dict[str, Any]:
    """Report whether a stored Garmin session is usable.

    Call this first if another tool fails with an authentication error.
    """
    try:
        profile = api().get_user_profile()
    except Exception as exc:
        return {"authenticated": False, "token_path": str(TOKENSTORE), "error": str(exc)}
    return {
        "authenticated": True,
        "token_path": str(TOKENSTORE),
        "display_name": profile.get("displayName") if isinstance(profile, dict) else None,
    }


@mcp.tool()
def get_daily_summary(date: str | None = None) -> dict[str, Any]:
    """Daily wellness totals: steps, calories, resting heart rate, stress,
    body battery and intensity minutes. Defaults to today."""
    return compact(api().get_stats(_day(date)))


@mcp.tool()
def get_sleep(date: str | None = None) -> dict[str, Any]:
    """Sleep summary for the night ending on `date`: total sleep, deep/light/REM
    and awake seconds, sleep score, overnight HRV. Defaults to today."""
    raw = api().get_sleep_data(_day(date))
    if not isinstance(raw, dict):
        return {}
    out = compact(raw.get("dailySleepDTO") or {})
    out.update(
        pick(raw, "restingHeartRate", "avgOvernightHrv", "bodyBatteryChange")
    )
    return out


@mcp.tool()
def get_health_metrics(date: str | None = None) -> dict[str, Any]:
    """HRV status, training readiness, training status and VO2 max for a single
    day. Sections are omitted when the watch recorded nothing. Defaults to today."""
    day = _day(date)
    client = api()
    hrv = _try(client.get_hrv_data, day) or {}
    return compact(
        {
            "hrv": hrv.get("hrvSummary") if isinstance(hrv, dict) else None,
            "training_readiness": _first(_try(client.get_training_readiness, day)),
            "training_status": _try(client.get_training_status, day),
            "max_metrics": _first(_try(client.get_max_metrics, day)),
        }
    )


@mcp.tool()
def list_activities(
    start: str,
    end: str | None = None,
    activity_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List recorded activities between two dates, newest first.

    `activity_type` filters by Garmin's type key, e.g. running, cycling,
    lap_swimming, strength_training. Use the returned activityId with
    get_activity for full detail.
    """
    rows = api().get_activities_by_date(start, end, activity_type) or []
    rows = rows[:limit]
    return [
        pick(
            row,
            "activityId",
            "activityName",
            "activityType.typeKey",
            "startTimeLocal",
            "distance",
            "duration",
            "averageSpeed",
            "averageHR",
            "maxHR",
            "calories",
            "elevationGain",
            "aerobicTrainingEffect",
        )
        for row in rows
    ]


@mcp.tool()
def get_activity(activity_id: str, include_splits: bool = False) -> dict[str, Any]:
    """Full detail for one activity. Set `include_splits` to add per-lap data."""
    out: dict[str, Any] = {"summary": compact(api().get_activity(activity_id))}
    if include_splits:
        splits = _try(api().get_activity_splits, activity_id)
        out["splits"] = prune(splits) if splits else None
    return prune(out)


@mcp.tool()
def get_body_composition(start: str, end: str | None = None) -> dict[str, Any]:
    """Weight and body composition weigh-ins over a date range. Weight is grams."""
    return compact(api().get_body_composition(start, end))


@mcp.tool()
def get_trend(metric: str, start: str, end: str) -> list[dict[str, Any]]:
    """Daily time series for one metric across a date range.

    `metric` is one of: steps, resting_hr, sleep_score, hrv, weight,
    body_battery. Prefer this over calling the per-day tools in a loop.
    """
    client = api()
    sources: dict[str, Callable[[], Any]] = {
        "steps": lambda: client.get_daily_steps(start, end),
        "resting_hr": lambda: client.get_rhr_daily(start, end),
        "sleep_score": lambda: client.get_sleep_daily(start, end),
        "hrv": lambda: client.get_hrv_data_range(start, end),
        "weight": lambda: client.get_body_composition(start, end),
        "body_battery": lambda: client.get_body_battery(start, end),
    }
    if metric not in sources:
        raise ValueError(f"Unknown metric {metric!r}; expected one of {', '.join(sources)}")

    data = sources[metric]() or []
    if isinstance(data, dict):
        # Range endpoints wrap their series in a single-key envelope.
        series = next(
            (v for v in data.values() if isinstance(v, list)), [data]
        )
    else:
        series = data
    return [prune(row) for row in series]


def serve() -> None:
    mcp.run("stdio")
