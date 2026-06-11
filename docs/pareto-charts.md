# Pareto Charts

LinePulse can generate a dependency-free SVG chart for downtime Pareto analysis.

Use it when you want a visual for a continuous-improvement meeting, README screenshot, or shared report folder.

## CLI Usage

```powershell
linepulse analyze examples/machine_events.csv --pareto-svg reports/pareto.svg
```

You can combine chart output with the existing report formats:

```powershell
linepulse analyze examples/machine_events.csv --pareto --markdown reports/oee.md --json reports/oee.json --pareto-svg reports/pareto.svg
```

The chart uses the same `downtime_pareto` data that appears in JSON, Markdown, and CLI table output:

- blue bars show each reason's downtime share, labeled with lost hours
- the orange line shows cumulative downtime share
- reasons are sorted from largest to smallest lost time

## Reason Maps

For cleaner charts, normalize messy downtime labels before rendering:

```powershell
linepulse analyze examples/machine_events.csv --reason-map examples/reason_codes.json --pareto-svg reports/pareto.svg
```

This prevents variants such as `Jam`, `material_jam`, and `material-jam` from appearing as separate bars.

## Interpretation Notes

Pareto charts should be treated as a review aid, not a substitute for the event model underneath them.

- Use interval downtime events rather than manually edited summary totals.
- Make shift, run, or time-window boundaries explicit when sharing results.
- Normalize reason codes before comparing lines, assets, shifts, or sites.
- Investigate the largest reasons against operator notes, maintenance history, and process data before treating the chart as root cause.

## Sample

![LinePulse OEE Pareto chart](assets/pareto-chart.svg)
