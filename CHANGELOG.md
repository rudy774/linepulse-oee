# Changelog

## Unreleased

- Added optional JSON shift calendars with `linepulse analyze --calendar`.
- Planned production time can now be derived from shifts and breaks.
- `planned_stop` rows still subtract from calendar-derived planned time.
- Missing event coverage inside a planned calendar window is reported as `unclassified calendar gap` downtime.
- Added optional reason-code normalization with `linepulse analyze --reason-map`.
- Downtime aliases can now be grouped into canonical categories before Pareto reporting.
- Unmapped reasons are reported as warnings when a reason map is supplied.
- Added `linepulse convert` adapter examples for Ignition historian exports, MES production logs, and manual downtime spreadsheets.
- Added dependency-free SVG downtime Pareto charts with `linepulse analyze --pareto-svg`.
- Added `linepulse validate` for event CSV data-quality checks.
- Added report recommendations in CLI, Markdown, and JSON output.
- Added optional run, product, work-order, and shift context fields with `linepulse analyze` filters.
- Added `linepulse dashboard` for self-contained operator HTML dashboards.

## v0.1.0 - 2026-06-07

Initial public release of LinePulse OEE.

- Added CSV event-log parsing for manufacturing state intervals.
- Added asset-level OEE, availability, performance, quality, and lost-time calculations.
- Added bottleneck ranking by lost production time.
- Added downtime Pareto output in JSON, Markdown, and CLI table form.
- Added sample machine event data, schema documentation, unit tests, and GitHub Actions.
