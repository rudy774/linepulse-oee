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
| `run_id` | No | Production run, job, or batch identifier. |
| `product` | No | Product, SKU, part number, or model identifier. |
| `work_order` | No | Work order or production order identifier. |
| `shift` | No | Shift, crew, or scheduled production window label. |

## Metric Definitions

Planned production time excludes `planned_stop` intervals. When a shift calendar is supplied with `--calendar`, planned production time is derived from the calendar windows and planned breaks instead. See [shift-calendars.md](shift-calendars.md).

Downtime reasons can be normalized with `--reason-map`. See [reason-codes.md](reason-codes.md).

Source exports that do not match this schema can be converted with `linepulse convert`. See [adapters.md](adapters.md).

CSV event quality can be checked with `linepulse validate`. See [validation.md](validation.md).

Reports include deterministic improvement recommendations in JSON and Markdown output. See [recommendations.md](recommendations.md).

Optional context fields can be used to focus a report on one production boundary:

```powershell
linepulse analyze examples/machine_events_with_context.csv --run-id RUN-1001 --pareto
linepulse analyze examples/machine_events_with_context.csv --product Widget-A --shift day
linepulse analyze examples/machine_events_with_context.csv --work-order WO-9001 --json reports/wo-9001.json
```

Each context filter can be repeated. Values are matched exactly so the report boundary stays auditable.

Keep `run_id` and `work_order` separate when the source can provide both. The work order represents the business demand or order, while the run ID represents the actual execution boundary used to attach state intervals, counts, downtime, and OEE calculations.

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
