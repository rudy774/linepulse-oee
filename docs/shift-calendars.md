# Shift Calendars

Shift calendars let LinePulse OEE derive planned production time from a schedule instead of requiring every planned period to appear in the event CSV.

Use a calendar when your event data covers machine states, but your planned production windows live in a shift schedule, staffing plan, or production calendar.

## CLI Usage

```powershell
linepulse analyze examples/machine_events.csv --calendar examples/shift_calendar.json --pareto
```

Calendar-derived planned time is opt-in. Without `--calendar`, LinePulse keeps the original behavior: every non-`planned_stop` event row contributes to planned production time.

## JSON Format

```json
{
  "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
  "shifts": [
    {
      "name": "day",
      "start": "06:00",
      "end": "14:30",
      "breaks": [
        {"name": "lunch", "start": "11:30", "end": "12:00"}
      ]
    }
  ],
  "assets": {
    "Welder-2": {
      "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "shifts": [
        {"name": "welder day", "start": "06:00", "end": "15:00"}
      ]
    }
  }
}
```

Top-level `weekdays` and `shifts` apply to every asset. Entries under `assets` override the default schedule for a specific asset.

## Supported Fields

| Field | Required | Description |
| --- | --- | --- |
| `weekdays` | Yes | List of weekdays such as `monday` or `mon`, or the string `all`. |
| `shifts` | Yes | List of working windows. |
| `shifts[].name` | No | Human-readable shift name. |
| `shifts[].start` | Yes | Shift start time in `HH:MM` or ISO time format. |
| `shifts[].end` | Yes | Shift end time in `HH:MM` or ISO time format. |
| `shifts[].breaks` | No | Planned break windows excluded from planned production time. |
| `assets` | No | Asset-specific schedule overrides keyed by asset name. |

Shifts may cross midnight. If a shift `end` is earlier than or equal to `start`, LinePulse treats the end as occurring on the next day.

## Planned Stops And Gaps

CSV `planned_stop` rows still work when a calendar is used. Their overlap with calendar windows is subtracted from planned production time.

If a calendar says an asset should be producing but the CSV has no event coverage for part of that planned window, LinePulse adds that time as `unclassified calendar gap` downtime and emits a warning. This makes missing data visible instead of silently improving availability.

## Partial Intervals

If an event row partially overlaps a planned calendar window, LinePulse clips the duration to the planned overlap. Running counts are prorated by overlap and rounded to the nearest unit. For the most auditable results, export event rows that already split at shift boundaries, planned breaks, and planned stops.

