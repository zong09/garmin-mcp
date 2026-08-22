"""MCP tools over Garmin Connect: reads, plus add/delete of weigh-ins.

The read tools follow Garmin's own units: distance in metres, duration in
seconds, speed in metres/second, weight in grams. add_body_composition takes
kilograms instead, because that is what a scale reports.
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
        "Access to the signed-in user's Garmin Connect data. Every tool reads "
        "except add_body_composition and delete_weigh_in, which change the "
        "user's weigh-in history. "
        "Dates are ISO YYYY-MM-DD in the user's local timezone, as recorded by "
        "the watch. Distances are metres, durations seconds, speeds m/s; reads "
        "report weight in grams, but add_body_composition takes kilograms."
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


@mcp.tool()
def add_body_composition(
    weight_kg: float,
    timestamp: str | None = None,
    percent_fat: float | None = None,
    percent_hydration: float | None = None,
    bmi: float | None = None,
    bone_mass: float | None = None,
    muscle_mass: float | None = None,
    basal_met: float | None = None,
    active_met: float | None = None,
    visceral_fat_rating: float | None = None,
    visceral_fat_mass: float | None = None,
    physique_rating: float | None = None,
    metabolic_age: float | None = None,
) -> dict[str, Any]:
    """Record a weigh-in, with optional body composition. Writes to Garmin.

    Units are the scale's own, not Garmin's: weight and the mass fields are
    kilograms, `percent_*` are percentages, `basal_met`/`active_met` are
    kcal/day. Note the asymmetry with get_body_composition, which reports weight
    in grams.

    `timestamp` is naive local time, `YYYY-MM-DDTHH:MM`; a UTC offset is
    silently discarded, so do not pass one. Omit it to mean now.

    `visceral_fat_rating` is the unitless index most scales report. Only pass
    `visceral_fat_mass` if the scale really reports a mass in kg.

    The upload is asynchronous, so the returned import result does not prove the
    data landed — confirm with get_body_composition. Re-uploading the same
    timestamp is rejected as a duplicate.
    """
    return prune(
        api().add_body_composition(
            timestamp=timestamp,
            weight=weight_kg,
            percent_fat=percent_fat,
            percent_hydration=percent_hydration,
            visceral_fat_mass=visceral_fat_mass,
            bone_mass=bone_mass,
            muscle_mass=muscle_mass,
            basal_met=basal_met,
            active_met=active_met,
            physique_rating=physique_rating,
            metabolic_age=metabolic_age,
            visceral_fat_rating=visceral_fat_rating,
            bmi=bmi,
        )
    )


@mcp.tool()
def delete_weigh_in(date: str, sample_pk: str | None = None) -> dict[str, Any]:
    """Delete a weigh-in. Destructive — this removes data from Garmin Connect.

    Omit `sample_pk` when the day holds a single weigh-in. When it holds none or
    several, nothing is deleted and the candidates are returned so you can
    re-call with the samplePk you meant.
    """
    client = api()
    if sample_pk is None:
        day = client.get_daily_weigh_ins(date) or {}
        entries = day.get("dateWeightList") or []
        if len(entries) != 1:
            return {
                "deleted": False,
                "date": date,
                "reason": f"{len(entries)} weigh-ins on {date}; pass sample_pk",
                "candidates": [
                    pick(e, "samplePk", "weight", "sourceType") for e in entries
                ],
            }
        sample_pk = str(entries[0]["samplePk"])
    client.delete_weigh_in(sample_pk, date)
    return {"deleted": True, "date": date, "sample_pk": sample_pk}


def serve() -> None:
    mcp.run("stdio")
