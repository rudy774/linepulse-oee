# CSV Validation

LinePulse can validate canonical machine event CSVs before analysis.

Use validation when importing historian, MES, or manual downtime exports into a review workflow. It helps catch state-history problems before OEE, bottleneck, and Pareto reports are trusted.

## CLI Usage

```powershell
linepulse validate examples/machine_events.csv
```

Write machine-readable validation results:

```powershell
linepulse validate examples/machine_events.csv --json reports/validation.json
```

By default, validation warns when an asset timeline has a gap between rows. Disable those timeline-gap warnings when the file intentionally contains sparse intervals:

```powershell
linepulse validate examples/machine_events.csv --no-gap-warnings
```

## Checks

| Check | Severity | Why it matters |
| --- | --- | --- |
| Missing header | Error | The file cannot be parsed without column names. |
| Missing required columns | Error | `asset`, `start`, `end`, and `state` define the event interval. |
| Non-positive interval | Error | State history requires `end` to be after `start`. |
| Duplicate interval | Error | Duplicate rows double-count runtime or downtime. |
| Overlapping intervals | Error | One asset should not have two simultaneous states. |
| Timeline gap | Warning | Missing intervals may hide downtime, no-order time, or data-collection loss. |
| Missing reason | Warning | Downtime, idle, and changeover intervals need reasons for useful Pareto output. |
| Running interval with zero counts | Warning | Counts may be missing, or the state may not represent production. |
| Counts on non-running interval | Warning | The state or production counts may be assigned to the wrong interval. |

## Analysis Integration

`linepulse analyze` also adds validation warnings to report output. Gap warnings are reserved for `linepulse validate` so sparse files can still be analyzed without noisy output.

## Manufacturing Notes

These checks come from the same event-history principles used in MES and IIoT systems:

- state history should be interval evidence
- one asset should have one active state at a time
- reason codes should be governed before comparing Pareto charts
- count data should be treated as evidence that can be missing, reset, or assigned to the wrong state
