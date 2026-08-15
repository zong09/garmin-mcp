# garmin-mcp

MCP server exposing read-only Garmin Connect data.

Built on [`garminconnect`](https://github.com/cyberjunky/python-garminconnect), which
talks to Garmin's **unofficial** mobile API. There is no public API for personal
Connect data, so this can break whenever Garmin changes their endpoints. Use it
with your own account only.

## Setup

```sh
uv sync
uv run garmin-mcp login      # prompts for email, password and MFA code
```

Login writes an OAuth token to `~/.garminconnect/garmin_tokens.json` (mode 0600)
and forgets the password. Override the location with `GARMINTOKENS`. The token is
refreshed automatically; you only re-run `login` if it is revoked or expires.

`serve` never prompts — a stdio MCP server cannot ask for an MFA code — so it
only reads that token file and returns a clear error if it is missing.

## Connect to Claude Code

```sh
claude mcp add garmin -- uv --directory /home/zong09/projects/garmin-mcp run garmin-mcp serve
```

## Tools

| Tool | Arguments |
|---|---|
| `check_auth` | — |
| `get_daily_summary` | `date?` |
| `get_sleep` | `date?` |
| `get_health_metrics` | `date?` |
| `list_activities` | `start`, `end?`, `activity_type?`, `limit=20` |
| `get_activity` | `activity_id`, `include_splits=false` |
| `get_body_composition` | `start`, `end?` |
| `get_trend` | `metric`, `start`, `end` |

`get_trend` metrics: `steps`, `resting_hr`, `sleep_score`, `hrv`, `weight`,
`body_battery`. Prefer it over looping the per-day tools.

Dates are `YYYY-MM-DD` in the watch's local timezone. Units are Garmin's own:
metres, seconds, m/s, grams.

Responses are trimmed before returning (`client.py`): nulls, empty values,
internal ids and GMT duplicates are dropped, and embedded per-minute sample
arrays are stripped so a summary call stays small.
