# garmin-mcp

MCP server exposing Garmin Connect data, plus manual weigh-in entry.

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
| `get_activity` | `activity_id`, `include?` (splits, typed_splits, split_summaries, exercise_sets, weather, hr_zones, power_zones, gear) |
| `get_body_composition` | `start`, `end?` |
| `get_daily_weigh_ins` | `date` |
| `get_trend` | `metric`, `start`, `end` |
| `add_body_composition` | `weight_kg`, `timestamp?`, composition fields |
| `delete_weigh_in` | `date`, `sample_pk?` |

`get_trend` metrics: `steps`, `resting_hr`, `sleep_score`, `hrv`, `weight`,
`body_battery`. Prefer it over looping the per-day tools.

Dates are `YYYY-MM-DD` in the watch's local timezone. Read units are Garmin's
own: metres, seconds, m/s, grams.

## Writing weigh-ins

`add_body_composition` is for transcribing a smart scale that does not sync to
Garmin itself. Mind three things:

- **It takes kilograms**, while `get_body_composition` reads back grams.
- `timestamp` (`YYYY-MM-DDTHH:MM`) is read in the **server's own timezone**, so
  keep the host's clock on the zone your watch records in. An explicit offset is
  honoured if given.
- The FIT upload is asynchronous and de-duplicated by timestamp, so the return
  value proves nothing; verify with `get_body_composition`.

Garmin stores nine fields: weight, BMI, body fat %, water %, bone mass, muscle
mass, visceral fat rating, physique rating and metabolic age. Three more that
the FIT format carries — basal metabolism, active metabolism and visceral fat
*mass* — are dropped by Garmin on import, so the tool does not accept them.
Garmin's own BMR is `bmrKilocalories` in `get_daily_summary`, derived from your
profile, not from an upload. **Protein %** has no Garmin field at all.

`delete_weigh_in` exists because a FIT upload can't be edited in place; a
mistyped entry has to be deleted and re-added.

Responses are trimmed before returning (`client.py`): nulls, empty values,
internal ids and GMT duplicates are dropped, and embedded per-minute sample
arrays are stripped so a summary call stays small. `get_body_composition` is
exempt from that last rule — its weigh-in list is the payload, not telemetry.
