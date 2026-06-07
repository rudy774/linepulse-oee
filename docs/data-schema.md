# Data Schema

LinePulse OEE expects CSV input with the following columns.

| Column | Required | Description |
| --- | --- | --- |
| `asset` | Yes | Machine, cell, or line identifier. |
| `start` | Yes | ISO-8601 interval start timestamp. |
| `end` | Yes | ISO-8601 interval end timestamp. |
| `state` | Yes | One of `running`, `downtime`, `planned_stop`, `idle`, or `changeover`. |
| `reason` | No | Downtime or changeover reason code. |
| `good_count` | No | Good units produced during the interval. Defaults to `0`. |
| `scrap_count` | No | Rejected units produced during the interval. Defaults to `0`. |
| `ideal_cycle_seconds` | No | Ideal cycle time for the asset and product. Used for performance loss. |

## Metric Definitions

Planned production time excludes `planned_stop` intervals.

Availability:

```text
runtime_seconds / planned_production_seconds
```

Performance:

```text
ideal_cycle_seconds * total_count / runtime_seconds
```

Quality:

```text
good_count / total_count
```

OEE:

```text
availability * performance * quality
```

Lost production time is estimated as:

```text
downtime_seconds + speed_loss_seconds + quality_loss_seconds
```

Where:

- `downtime_seconds` is non-running planned production time.
- `speed_loss_seconds` is runtime not explained by ideal cycle time and produced count.
- `quality_loss_seconds` is rejected unit count multiplied by ideal cycle time.

## Notes

- Timestamps may include timezone offsets, but all rows in one file should use a consistent convention.
- Unknown states are rejected so data quality problems surface early.
- Performance is not capped at 100 percent. Values above 100 percent are useful signals that the ideal cycle time or counts may need review.

