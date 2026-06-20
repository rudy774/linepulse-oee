# Report Recommendations

LinePulse reports include deterministic recommendations that translate OEE, downtime, bottleneck, and data-quality evidence into the first improvement questions a plant team should ask.

Recommendations appear in:

- terminal output from `linepulse analyze`
- Markdown reports written with `--markdown`
- JSON reports written with `--json`

## What Recommendations Cover

| Category | Trigger | Purpose |
| --- | --- | --- |
| `data-quality` | Report warnings are present. | Fix event-history, reason-code, or coverage issues before comparing assets. |
| `constraint` | One asset has the largest calculated lost production time. | Start improvement work where the report shows the largest loss. |
| `downtime` | A named downtime reason leads the Pareto table. | Focus the first review on the biggest reason bucket. |
| `coverage` | Calendar-planned time is not covered by event rows. | Close gaps between the shift calendar and the source event history. |
| `performance` | Speed loss is the dominant loss on the top constrained asset. | Review rate assumptions, minor stops, and slow-cycle evidence. |
| `quality` | Scrap-related quality loss is the dominant loss on the top constrained asset. | Add defect or scrap classification before treating quality loss as root cause. |
| `counting` | Running intervals have no good or scrap counts. | Improve count evidence so quality and performance are trustworthy. |
| `next-data` | No clear loss driver is present. | Add richer boundaries, reason maps, counts, or run context. |

## JSON Shape

Each recommendation includes a priority, category, title, message, evidence, and next steps:

```json
{
  "priority": "high",
  "category": "constraint",
  "title": "Start with Welder-2",
  "message": "Welder-2 is the top constraint in this report by lost production time.",
  "evidence": [
    "Welder-2 has 1.00 lost hours (100.0% of plant loss)."
  ],
  "next_steps": [
    "Review the raw event rows for this asset over the report window."
  ]
}
```

## Interpretation

Recommendations are review prompts, not automated root cause.

- Validate the source CSV before using recommendations in an improvement meeting.
- Normalize reason codes before comparing assets, shifts, teams, or sites.
- Keep shift, run, product, and work-order boundaries explicit when the source system can provide them.
- Pair Pareto output with maintenance notes, operator comments, quality records, or process history before assigning cause.
- Treat scrap and performance recommendations as signals that better classification or rate governance is needed.
