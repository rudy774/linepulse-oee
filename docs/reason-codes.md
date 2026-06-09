# Reason-Code Normalization

Reason-code normalization groups messy downtime labels into stable categories before bottleneck and Pareto reporting.

Use it when source systems or manual logs contain variants such as `Jam`, `material_jam`, `material-jam`, and `material jam`.

## CLI Usage

```powershell
linepulse analyze examples/machine_events.csv --reason-map examples/reason_codes.json --pareto
```

Reason maps are optional. Without `--reason-map`, LinePulse keeps the raw `reason` values from the CSV.

You can combine reason maps with shift calendars:

```powershell
linepulse analyze examples/machine_events.csv --calendar examples/shift_calendar.json --reason-map examples/reason_codes.json --pareto
```

## JSON Format

```json
{
  "warn_unmapped": true,
  "categories": [
    {
      "canonical": "material jam",
      "aliases": ["jam", "material_jam", "material-jam"]
    },
    {
      "canonical": "changeover",
      "aliases": ["die change", "model change", "change over"]
    }
  ]
}
```

## Supported Fields

| Field | Required | Description |
| --- | --- | --- |
| `warn_unmapped` | No | When true, warn once for each downtime reason not found in the map. Defaults to true. |
| `categories` | Yes | List of canonical reason categories. |
| `categories[].canonical` | Yes | Stable reason label used in reports. |
| `categories[].aliases` | No | Raw source labels that should map to the canonical label. |

Canonical labels automatically map to themselves. Alias matching is case-insensitive and treats whitespace, underscores, and hyphens as equivalent.

## Unmapped Reasons

When `warn_unmapped` is true, unmapped reasons are still included in reports using their original label, and LinePulse adds a warning such as:

```text
Reason 'operator check' was not mapped; used as-is.
```

This keeps reports complete while making cleanup work visible.

## Data Safety

Do not include sensitive customer, operator, or proprietary process information in shared reason maps. Prefer generic categories such as `material jam`, `quality hold`, `maintenance`, and `waiting on materials`.

