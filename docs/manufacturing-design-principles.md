# Manufacturing Design Principles

LinePulse should stay useful to real plant teams, not just produce nice-looking KPI output.

These principles guide feature work:

## Event Evidence First

Reports should be calculated from auditable event evidence:

- machine state intervals
- downtime reasons
- production counts
- scrap or reject counts
- shift, run, product, or order context when available

Avoid features that depend on manually edited summary totals when interval or count history can be used instead.

## Explicit Boundaries

Every OEE or downtime result should make its calculation boundary clear.

Current boundaries include asset and time interval. Future boundaries should include shift, production run, product, work order, and line where possible.

## Governed Reasons

Downtime Pareto output is only as useful as the reason model underneath it.

Use reason-code maps to group messy labels before comparing assets, shifts, or sites. Future reason models should support stable IDs, aliases, planned/unplanned semantics, and audit-friendly edits.

## Counts As Deltas

Manufacturing counters often reset, roll over, or jump because software samples a changing value rather than seeing every physical part.

Future count import features should prefer count deltas or explicit interval totals. They should flag suspicious negative, reset, rollover, or implausibly large count changes instead of silently treating them as production.

## Metadata And Lineage

Reports should preserve enough context for someone to trust and reproduce the result:

- source file or source system
- timestamp convention
- schema version
- units
- data quality warnings
- calendar and reason-map inputs

LinePulse should favor transparent files and deterministic calculations over hidden spreadsheet logic.

## Decision-First Reports

A report should help a real person choose the next useful question.

Tables and charts are not the finish line. When the evidence is strong enough, reports should point to the top constrained asset, the dominant downtime reason, the likely loss family, and the data-quality issues that could change the conclusion.

Recommendations should stay grounded in report evidence. They should not claim root cause unless the input data actually contains root-cause evidence.

## Practical Plant Adoption

Build the evidence and workflow before the screen.

Small manufacturers need tools that can start with CSV exports, historian/MES samples, and simple review reports. As the project matures, it should grow toward run-level OEE, stronger validation, adapter contracts, and optional event-stream or cloud outputs without making the first workflow heavy.
