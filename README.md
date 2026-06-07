# LinePulse OEE

LinePulse OEE is a small open-source toolkit for turning manufacturing event logs into practical OEE, downtime, and bottleneck reports. It is designed for teams that have CSV exports from PLCs, historians, MES systems, or manual downtime logs, but do not yet have a clean analytics layer.

The first release focuses on three things:

- compute asset-level availability, performance, quality, and OEE
- rank bottlenecks by lost production time
- produce machine-readable JSON and human-readable Markdown reports from a simple CSV
- identify the largest downtime reasons with a plant-level Pareto table

## Why this exists

Many small manufacturers have useful production data trapped in spreadsheets. Commercial OEE products can be too heavy for early continuous-improvement work, while ad hoc spreadsheets are hard to audit. LinePulse OEE gives those teams a transparent baseline they can run, inspect, and extend.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
linepulse analyze examples/machine_events.csv --markdown reports/oee.md --json reports/oee.json
```

You can also run it without installing:

```powershell
python -m linepulse_oee.cli analyze examples/machine_events.csv --markdown reports/oee.md
```

## Input Format

LinePulse reads CSV files with one row per machine state interval:

```csv
asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:45:00,running,,520,8,4.5
Press-1,2026-06-01T06:45:00,2026-06-01T07:05:00,downtime,die change,0,0,4.5
```

Supported `state` values are:

- `running`
- `downtime`
- `planned_stop`
- `idle`
- `changeover`

Rows marked `planned_stop` are excluded from planned production time. Rows marked `running` contribute runtime and part counts. Other non-planned rows count as downtime or lost time.

See [docs/data-schema.md](docs/data-schema.md) for the full schema.

## CLI

Create a starter CSV:

```powershell
linepulse template > machine_events.csv
```

Analyze a file and print a compact summary:

```powershell
linepulse analyze examples/machine_events.csv
```

Print the downtime Pareto table too:

```powershell
linepulse analyze examples/machine_events.csv --pareto
```

Write JSON and Markdown reports:

```powershell
linepulse analyze examples/machine_events.csv --json reports/oee.json --markdown reports/oee.md
```

## Example Output

```text
Asset      OEE    Availability  Performance  Quality  Lost hours
Press-1    71.8%  83.3%         87.9%        98.0%    0.65
Welder-2   64.4%  76.9%         86.3%        97.0%    0.93
```

Markdown and JSON reports include a `Downtime Pareto` section that ranks downtime reasons by lost hours, share of downtime, cumulative share, and affected assets.

## Roadmap

- shift calendars and takt targets
- reason-code normalization
- Pareto charts for downtime reasons
- notebook examples for continuous improvement reviews
- adapters for common historian and MES exports
- optional web dashboard for non-technical users

## Contributing

Contributions are welcome, especially sample schemas from real manufacturing systems, test CSVs, documentation improvements, and adapters. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE).
