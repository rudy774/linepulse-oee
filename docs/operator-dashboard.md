# Operator Dashboard

LinePulse can generate a self-contained HTML operator board from the same CSV evidence used by JSON, Markdown, and CLI reports.

```powershell
linepulse dashboard examples/machine_events_with_context.csv --output reports/operator-dashboard.html
```

The dashboard is designed for an operator station, supervisor desk, or shared shift-review screen. It includes plant OEE, availability, performance, quality, lost time, asset cards, downtime Pareto bars, report context, recommendations, and warnings.

Use the same report boundaries as `linepulse analyze`:

```powershell
linepulse dashboard examples/machine_events_with_context.csv --run-id RUN-1001 --output reports/run-1001-dashboard.html
linepulse dashboard examples/machine_events_with_context.csv --product Widget-A --shift day --output reports/widget-a-day.html
linepulse dashboard examples/machine_events.csv --calendar examples/shift_calendar.json --reason-map examples/reason_codes.json --output reports/shift-board.html
```

The generated file has no runtime dependencies and can be opened directly in a browser.
