from __future__ import annotations

from html import escape

from .model import (
    AssetMetrics,
    DowntimeParetoItem,
    PlantReport,
    ReportRecommendation,
    safe_ratio,
)


def render_operator_dashboard(
    report: PlantReport,
    title: str = "LinePulse operator board",
) -> str:
    """Render a self-contained operator-facing HTML dashboard."""
    aggregate = _aggregate_metrics(report)
    constraint = report.bottlenecks[0] if report.bottlenecks else None
    title_text = title.strip() or "LinePulse operator board"

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{_e(title_text)}</title>",
            f"  <style>{_CSS}</style>",
            "</head>",
            "<body>",
            '  <main class="board-shell">',
            '    <div class="status-rail" aria-hidden="true"></div>',
            '    <div class="board">',
            _render_header(title_text, report, aggregate, constraint),
            _render_kpis(aggregate, constraint),
            _render_asset_section(report.assets),
            _render_pareto_section(report),
            _render_recommendations(report.recommendations),
            _render_warnings(report.warnings),
            "    </div>",
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _aggregate_metrics(report: PlantReport) -> dict[str, float | int]:
    planned_seconds = sum(asset.planned_seconds for asset in report.assets)
    runtime_seconds = sum(asset.runtime_seconds for asset in report.assets)
    downtime_seconds = sum(asset.downtime_seconds for asset in report.assets)
    speed_loss_seconds = sum(asset.speed_loss_seconds for asset in report.assets)
    quality_loss_seconds = sum(asset.quality_loss_seconds for asset in report.assets)
    good_count = sum(asset.good_count for asset in report.assets)
    scrap_count = sum(asset.scrap_count for asset in report.assets)
    total_count = good_count + scrap_count
    availability = safe_ratio(runtime_seconds, planned_seconds)
    performance = safe_ratio(max(0.0, runtime_seconds - speed_loss_seconds), runtime_seconds)
    quality = safe_ratio(good_count, total_count)
    return {
        "assets": len(report.assets),
        "planned_seconds": planned_seconds,
        "runtime_seconds": runtime_seconds,
        "downtime_seconds": downtime_seconds,
        "speed_loss_seconds": speed_loss_seconds,
        "quality_loss_seconds": quality_loss_seconds,
        "lost_seconds": downtime_seconds + speed_loss_seconds + quality_loss_seconds,
        "good_count": good_count,
        "scrap_count": scrap_count,
        "total_count": total_count,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": availability * performance * quality,
    }


def _render_header(
    title: str,
    report: PlantReport,
    aggregate: dict[str, float | int],
    constraint: AssetMetrics | None,
) -> str:
    constraint_text = constraint.asset if constraint else "No constraint"
    return f"""
      <header class="board-header">
        <div>
          <p class="eyebrow">LinePulse OEE</p>
          <h1>{_e(title)}</h1>
        </div>
        <div class="shift-ticket">
          <span>Assets</span>
          <strong>{int(aggregate["assets"])}</strong>
          <span>Constraint</span>
          <strong>{_e(constraint_text)}</strong>
        </div>
        {_render_context(report)}
      </header>"""


def _render_context(report: PlantReport) -> str:
    if not report.filters and not report.contexts:
        return '<div class="context-strip"><span class="chip muted">No production context</span></div>'

    chips: list[str] = []
    if report.filters:
        chips.append('<span class="context-label">Filters</span>')
        chips.extend(_context_chips(report.filters))
    if report.contexts:
        chips.append('<span class="context-label">Available</span>')
        chips.extend(_context_chips(report.contexts))
    return f'<div class="context-strip">{"".join(chips)}</div>'


def _context_chips(context: dict[str, tuple[str, ...]]) -> list[str]:
    chips: list[str] = []
    for name, values in sorted(context.items()):
        if not values:
            continue
        chips.append(
            '<span class="chip">'
            f'<b>{_e(name.replace("_", " "))}</b>{_e(", ".join(values))}'
            "</span>"
        )
    return chips


def _render_kpis(
    aggregate: dict[str, float | int],
    constraint: AssetMetrics | None,
) -> str:
    top_loss = _hours(constraint.lost_seconds) if constraint else "0.00 h"
    return f"""
      <section class="kpi-grid" aria-label="Plant performance">
        {_kpi("OEE", _percent(float(aggregate["oee"])), "status", float(aggregate["oee"]))}
        {_kpi("Availability", _percent(float(aggregate["availability"])), "runtime", float(aggregate["availability"]))}
        {_kpi("Performance", _percent(float(aggregate["performance"])), "rate", float(aggregate["performance"]))}
        {_kpi("Quality", _percent(float(aggregate["quality"])), "yield", float(aggregate["quality"]))}
        {_kpi("Lost time", _hours(float(aggregate["lost_seconds"])), "top loss " + top_loss, None)}
        {_kpi("Good", _count(int(aggregate["good_count"])), "accepted units", None)}
        {_kpi("Scrap", _count(int(aggregate["scrap_count"])), "rejected units", None)}
      </section>"""


def _kpi(label: str, value: str, detail: str, status_value: float | None) -> str:
    status_class = _status_class(status_value) if status_value is not None else "neutral"
    return f"""
        <article class="kpi {status_class}">
          <span>{_e(label)}</span>
          <strong>{_e(value)}</strong>
          <small>{_e(detail)}</small>
        </article>"""


def _render_asset_section(assets: list[AssetMetrics]) -> str:
    if not assets:
        return """
      <section class="section">
        <div class="section-heading">
          <h2>Assets</h2>
        </div>
        <p class="empty">No asset rows matched this report boundary.</p>
      </section>"""

    cards = "\n".join(_render_asset_card(asset) for asset in assets)
    return f"""
      <section class="section">
        <div class="section-heading">
          <h2>Assets</h2>
          <span>{len(assets)} monitored</span>
        </div>
        <div class="asset-grid">
{cards}
        </div>
      </section>"""


def _render_asset_card(asset: AssetMetrics) -> str:
    top_reason = _top_reason(asset)
    status_class = _status_class(asset.oee)
    width = _bar_width(asset.oee)
    return f"""
          <article class="asset-card {status_class}">
            <div class="asset-card-top">
              <h3>{_e(asset.asset)}</h3>
              <strong>{_percent(asset.oee)}</strong>
            </div>
            <div class="meter" aria-hidden="true"><span style="width: {width}%"></span></div>
            <dl class="asset-stats">
              <div><dt>Run</dt><dd>{_hours(asset.runtime_seconds)}</dd></div>
              <div><dt>Down</dt><dd>{_hours(asset.downtime_seconds)}</dd></div>
              <div><dt>Good</dt><dd>{_count(asset.good_count)}</dd></div>
              <div><dt>Scrap</dt><dd>{_count(asset.scrap_count)}</dd></div>
            </dl>
            <p class="asset-reason">{_e(top_reason)}</p>
          </article>"""


def _render_pareto_section(report: PlantReport) -> str:
    if not report.downtime_pareto:
        return """
      <section class="section">
        <div class="section-heading">
          <h2>Downtime Pareto</h2>
        </div>
        <p class="empty">No downtime reason data in this report.</p>
      </section>"""

    rows = "\n".join(_render_pareto_row(item) for item in report.downtime_pareto[:8])
    return f"""
      <section class="section">
        <div class="section-heading">
          <h2>Downtime Pareto</h2>
          <span>{len(report.downtime_pareto)} reasons</span>
        </div>
        <div class="pareto-list">
{rows}
        </div>
      </section>"""


def _render_pareto_row(item: DowntimeParetoItem) -> str:
    reason = item.reason
    seconds = item.seconds
    share = item.percent_of_downtime
    cumulative = item.cumulative_percent
    assets = item.assets
    width = _bar_width(share)
    return f"""
          <div class="pareto-row">
            <div class="pareto-reason">
              <strong>{_e(reason)}</strong>
              <span>{_e(", ".join(assets))}</span>
            </div>
            <div class="pareto-track" aria-hidden="true"><span style="width: {width}%"></span></div>
            <div class="pareto-value">
              <strong>{_hours(seconds)}</strong>
              <span>{_percent(share)} / {_percent(cumulative)}</span>
            </div>
          </div>"""


def _render_recommendations(recommendations: list[ReportRecommendation]) -> str:
    if not recommendations:
        return ""
    rows = "\n".join(_render_recommendation(item, index) for index, item in enumerate(recommendations, start=1))
    return f"""
      <section class="section">
        <div class="section-heading">
          <h2>Next Actions</h2>
          <span>{len(recommendations)} open</span>
        </div>
        <ol class="action-list">
{rows}
        </ol>
      </section>"""


def _render_recommendation(item: ReportRecommendation, index: int) -> str:
    next_step = item.next_steps[0] if item.next_steps else item.message
    return f"""
          <li>
            <span class="action-index">{index}</span>
            <div>
              <strong>{_e(item.title)}</strong>
              <p>{_e(next_step)}</p>
            </div>
            <span class="priority {_e(item.priority)}">{_e(item.priority)}</span>
          </li>"""


def _render_warnings(warnings: list[str]) -> str:
    if not warnings:
        return ""
    rows = "\n".join(f"<li>{_e(warning)}</li>" for warning in warnings)
    return f"""
      <section class="section warning-section">
        <div class="section-heading">
          <h2>Warnings</h2>
          <span>{len(warnings)} found</span>
        </div>
        <ul class="warning-list">
{rows}
        </ul>
      </section>"""


def _top_reason(asset: AssetMetrics) -> str:
    if not asset.downtime_by_reason:
        return "No named downtime"
    reason, seconds = max(asset.downtime_by_reason.items(), key=lambda item: item[1])
    return f"Top downtime: {reason}, {_hours(seconds)}"


def _status_class(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 0.75:
        return "good"
    if value >= 0.55:
        return "watch"
    return "down"


def _bar_width(value: float) -> str:
    return f"{max(0.0, min(1.0, value)) * 100:.1f}"


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _hours(seconds: float) -> str:
    return f"{seconds / 3600:.2f} h"


def _count(value: int) -> str:
    return f"{value:,}"


def _e(value: object) -> str:
    return escape(str(value), quote=True)


_CSS = """
:root {
  --ink: #16181d;
  --panel: #ffffff;
  --field: #f3f5f2;
  --line: #cbd2cf;
  --muted: #69716e;
  --steel: #45515a;
  --yellow: #f2bd2c;
  --green: #16805f;
  --red: #c4474d;
  --teal: #126b76;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--field);
  color: var(--ink);
  font-family: "Segoe UI", Arial, sans-serif;
}

.board-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
}

.status-rail {
  background:
    repeating-linear-gradient(
      -45deg,
      #1e2326 0 14px,
      #1e2326 14px 28px,
      var(--yellow) 28px 42px,
      var(--yellow) 42px 56px
    );
}

.board {
  width: min(1480px, 100%);
  margin: 0 auto;
  padding: 24px;
}

.board-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--ink);
}

.eyebrow,
.context-label,
.section-heading span,
.kpi span,
.kpi small,
.asset-stats dt,
.pareto-value span,
.priority,
.shift-ticket span {
  color: var(--muted);
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 0.74rem;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  font-family: Bahnschrift, "Segoe UI", Arial, sans-serif;
  font-size: 5rem;
  line-height: 0.95;
  max-width: 12ch;
}

.shift-ticket {
  min-width: 220px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 18px;
  padding: 14px;
  border: 2px solid var(--ink);
  background: var(--panel);
  box-shadow: 5px 5px 0 var(--yellow);
}

.shift-ticket strong {
  text-align: right;
}

.context-strip {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-height: 34px;
}

.chip {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  min-height: 30px;
  padding: 5px 10px;
  border: 1px solid var(--line);
  background: var(--panel);
  font-size: 0.88rem;
}

.chip b {
  color: var(--teal);
}

.chip.muted {
  color: var(--muted);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(120px, 1fr));
  gap: 10px;
  padding: 18px 0;
}

.kpi {
  min-height: 124px;
  display: grid;
  align-content: space-between;
  padding: 14px;
  border: 1px solid var(--line);
  border-top: 8px solid var(--steel);
  background: var(--panel);
}

.kpi strong {
  font-family: Bahnschrift, "Segoe UI", Arial, sans-serif;
  font-size: 3rem;
  line-height: 0.92;
}

.good {
  border-top-color: var(--green);
}

.watch {
  border-top-color: var(--yellow);
}

.down {
  border-top-color: var(--red);
}

.neutral {
  border-top-color: var(--steel);
}

.section {
  padding: 22px 0;
  border-top: 1px solid var(--line);
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: end;
  margin-bottom: 12px;
}

h2 {
  font-family: Bahnschrift, "Segoe UI", Arial, sans-serif;
  font-size: 1.35rem;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.asset-card {
  padding: 14px;
  border: 1px solid var(--line);
  border-top: 8px solid var(--steel);
  background: var(--panel);
}

.asset-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.asset-card h3 {
  font-size: 1.05rem;
}

.asset-card-top strong {
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 1.18rem;
}

.meter,
.pareto-track {
  height: 12px;
  overflow: hidden;
  background: #dde4e1;
}

.meter {
  margin: 12px 0;
}

.meter span,
.pareto-track span {
  display: block;
  height: 100%;
  background: var(--teal);
}

.asset-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.asset-stats div {
  min-width: 0;
}

.asset-stats dd {
  margin: 2px 0 0;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-weight: 700;
}

.asset-reason {
  margin-top: 12px;
  color: var(--muted);
  font-size: 0.92rem;
}

.pareto-list {
  display: grid;
  gap: 10px;
}

.pareto-row {
  display: grid;
  grid-template-columns: minmax(170px, 1.25fr) minmax(180px, 4fr) minmax(120px, auto);
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}

.pareto-reason {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.pareto-reason span {
  color: var(--muted);
  font-size: 0.85rem;
}

.pareto-value {
  text-align: right;
}

.pareto-value strong {
  display: block;
  font-family: "Cascadia Mono", Consolas, monospace;
}

.action-list,
.warning-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.action-list li {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 12px;
  border: 1px solid var(--line);
  background: var(--panel);
}

.action-index {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 2px solid var(--ink);
  font-family: "Cascadia Mono", Consolas, monospace;
  font-weight: 700;
}

.action-list p {
  margin-top: 4px;
  color: var(--muted);
}

.priority {
  padding: 4px 8px;
  border: 1px solid currentColor;
}

.priority.high {
  color: var(--red);
}

.priority.medium {
  color: #9a6810;
}

.priority.low {
  color: var(--teal);
}

.warning-section {
  border-top-color: var(--red);
}

.warning-list li,
.empty {
  padding: 12px;
  border-left: 5px solid var(--yellow);
  background: var(--panel);
  color: var(--muted);
}

@media (max-width: 1080px) {
  h1 {
    font-size: 3.7rem;
  }

  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .kpi strong {
    font-size: 2.4rem;
  }

  .pareto-row {
    grid-template-columns: 1fr;
  }

  .pareto-value {
    text-align: left;
  }
}

@media (max-width: 720px) {
  .board-shell {
    grid-template-columns: 10px minmax(0, 1fr);
  }

  .board {
    padding: 16px;
  }

  .board-header {
    grid-template-columns: 1fr;
  }

  h1 {
    font-size: 2.35rem;
  }

  .shift-ticket {
    min-width: 0;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .kpi strong {
    font-size: 2rem;
  }

  .asset-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
"""
