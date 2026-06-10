# Adapter Examples

Adapters convert common manufacturing exports into the canonical LinePulse event CSV schema.

Use adapters when the source file comes from a historian, MES, or manual downtime spreadsheet and does not already use the columns documented in [data-schema.md](data-schema.md).

## CLI Usage

```powershell
linepulse convert examples/adapters/ignition_historian_export.csv --adapter ignition-historian --output reports/ignition_events.csv
linepulse analyze reports/ignition_events.csv --pareto
```

The converter writes a normal LinePulse CSV with these columns:

```csv
asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
```

You can then use all existing analysis options, including `--calendar`, `--reason-map`, `--json`, `--markdown`, and `--pareto`.

## Supported Adapters

| Adapter | Source pattern | Example |
| --- | --- | --- |
| `ignition-historian` | Ignition-style interval export with state codes and count tags | [examples/adapters/ignition_historian_export.csv](../examples/adapters/ignition_historian_export.csv) |
| `mes-production-log` | MES production log with work center, event type, quantities, and standard cycle | [examples/adapters/mes_production_log.csv](../examples/adapters/mes_production_log.csv) |
| `manual-downtime-log` | Manual downtime spreadsheet with start/end, reason, and planned flag | [examples/adapters/manual_downtime_log.csv](../examples/adapters/manual_downtime_log.csv) |

## Ignition Historian Export

Required columns:

| Source column | LinePulse column |
| --- | --- |
| `equipment_path` | `asset` |
| `start_ts` | `start` |
| `end_ts` | `end` |
| `state_code` | `state` |
| `downtime_reason` | `reason` |
| `good_parts` | `good_count` |
| `scrap_parts` | `scrap_count` |
| `ideal_cycle_seconds` | `ideal_cycle_seconds` |

Common source states such as `RUNNING`, `PRODUCTION`, `FAULT`, `SETUP`, `IDLE`, and `PLANNED_STOP` are normalized to LinePulse states.

## MES Production Log

Required columns:

| Source column | LinePulse column |
| --- | --- |
| `work_center` | `asset` |
| `started_at` | `start` |
| `finished_at` | `end` |
| `event_type` | `state` |
| `reason_code` | `reason` |
| `good_qty` | `good_count` |
| `reject_qty` | `scrap_count` |
| `target_cycle_seconds` | `ideal_cycle_seconds` |

Event types such as `PRODUCTION_RUN`, `UNPLANNED_DOWN`, `CHANGEOVER`, `IDLE`, and `PLANNED_STOP` are normalized to LinePulse states.

## Manual Downtime Log

Required columns:

| Source column | LinePulse column |
| --- | --- |
| `asset` | `asset` |
| `down_start` | `start` |
| `down_end` | `end` |
| `reason` | `reason` |
| `planned` | `state` |

The `planned` value accepts `yes`, `true`, `1`, or `planned` for planned stops, and `no`, `false`, `0`, or `unplanned` for downtime.

Optional column:

| Source column | LinePulse column |
| --- | --- |
| `ideal_cycle_seconds` | `ideal_cycle_seconds` |

## Adding New Adapters

Keep new adapters dependency-light and fixture-driven:

- add a sample source CSV under `examples/adapters/`
- add a row converter in `src/linepulse_oee/adapters.py`
- document required columns here
- add tests that prove the converted output can be read by `linepulse analyze`
