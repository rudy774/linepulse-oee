# Changelog

## Unreleased

- Added optional JSON shift calendars with `linepulse analyze --calendar`.
- Planned production time can now be derived from shifts and breaks.
- `planned_stop` rows still subtract from calendar-derived planned time.
- Missing event coverage inside a planned calendar window is reported as `unclassified calendar gap` downtime.

## v0.1.0 - 2026-06-07

Initial public release of LinePulse OEE.

- Added CSV event-log parsing for manufacturing state intervals.
- Added asset-level OEE, availability, performance, quality, and lost-time calculations.
- Added bottleneck ranking by lost production time.
- Added downtime Pareto output in JSON, Markdown, and CLI table form.
- Added sample machine event data, schema documentation, unit tests, and GitHub Actions.
