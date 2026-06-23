# Roadmap

LinePulse OEE is growing into a dependency-light evidence-to-decision toolkit for manufacturing teams that have useful event data but not yet a full analytics or MES layer.

The product direction is simple: preserve auditable event evidence, add enough context to make the evidence trustworthy, and turn reports into practical next questions for operations, maintenance, quality, and continuous improvement.

## Delivered Foundations

- CSV event-log parsing for state intervals, counts, and ideal cycle time.
- Asset-level OEE, availability, performance, quality, and lost-time calculations.
- Bottleneck ranking by lost production time.
- Downtime Pareto tables across assets.
- Shift calendars and planned-stop handling.
- Reason-code normalization.
- Optional run, product, work-order, and shift context fields with report filters.
- Self-contained operator HTML dashboards.
- Starter adapters for historian, MES, and manual downtime exports.
- Dependency-free SVG Pareto charts.
- CSV validation for event-history and count/state issues.
- Report recommendations in CLI, Markdown, and JSON output.

## Product Principles

- Start with a bounded plant question, not a generic dashboard.
- Prefer interval and count evidence over manually edited summary totals.
- Make report boundaries explicit: asset, time window, shift, run, product, and work order where available.
- Preserve source transparency, schema assumptions, warnings, and calculation inputs.
- Keep the first workflow useful from CSV files before adding heavier infrastructure.
- Add features that improve data trust or decision quality, not just visual polish.

## Near-Term Priorities

1. **Count-delta imports**
   - Support source exports with absolute counters.
   - Convert counter samples into interval deltas.
   - Detect resets, rollovers, negative deltas, and implausible jumps.

2. **Defect and scrap classification**
   - Add optional defect or scrap reason fields.
   - Report unclassified scrap.
   - Add quality Pareto output by defect reason when data is available.

3. **Report lineage**
   - Include source file, generated timestamp, schema version, calendar path, reason-map path, adapter, and validation summary in JSON and Markdown.
   - Make reports easier to reproduce and audit.

4. **Adapter contracts and fixtures**
   - Add more realistic source examples from common historian, MES, ERP, and downtime-log exports.
   - Document adapter requirements and expected canonical output.
   - Keep adapter tests small, explicit, and source-shaped.

## Later Directions

- TEEP and capacity-utilization reporting once planned-time and OEE boundaries are stronger.
- MTBF and MTTR summaries from downtime/state history.
- Notebook examples for continuous-improvement reviews.
- Source metadata manifests for teams that need stronger traceability.

## v0.2.0 Target

The next release should make LinePulse more useful in a real improvement meeting:

- report recommendations
- context-aware example reports
- operator dashboard output
- stronger report lineage
- one more realistic adapter fixture
- documentation that shows a complete validate, analyze, review workflow

## v1.0.0 Definition

LinePulse can be considered 1.0 when:

- Core OEE calculations are stable and documented.
- CSV schema is versioned.
- Shift calendars are supported.
- Reason-code mapping is supported.
- Reports include asset summary, bottlenecks, downtime Pareto, recommendations, and lineage.
- Run, product, and work-order boundaries are supported.
- At least three real-world export adapter patterns are covered by tests.
- CI is green across supported Python versions.
