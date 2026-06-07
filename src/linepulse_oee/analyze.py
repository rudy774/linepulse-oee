from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, TextIO

from .model import VALID_STATES, AssetMetrics, Event, PlantReport


def read_events(source: str | Path | TextIO) -> list[Event]:
    """Read manufacturing state intervals from a CSV path or file object."""
    close_after = False
    if isinstance(source, (str, Path)):
        handle = Path(source).open("r", encoding="utf-8-sig", newline="")
        close_after = True
    else:
        handle = source

    try:
        reader = csv.DictReader(handle)
        events = [_event_from_row(row, reader.line_num) for row in reader]
    finally:
        if close_after:
            handle.close()

    return events


def analyze_events(events: Iterable[Event]) -> PlantReport:
    by_asset: dict[str, AssetMetrics] = {}
    warnings: list[str] = []

    for event in sorted(events, key=lambda item: (item.asset, item.start, item.end)):
        metrics = by_asset.setdefault(event.asset, AssetMetrics(asset=event.asset))
        duration = event.duration_seconds

        if duration <= 0:
            warnings.append(
                f"Skipped non-positive interval for {event.asset} at {event.start.isoformat()}."
            )
            continue

        if event.state != "planned_stop":
            metrics.planned_seconds += duration

        if event.state == "running":
            metrics.runtime_seconds += duration
            metrics.good_count += event.good_count
            metrics.scrap_count += event.scrap_count
            if event.ideal_cycle_seconds and event.total_count > 0:
                ideal_runtime = event.ideal_cycle_seconds * event.total_count
                metrics.speed_loss_seconds += max(0.0, duration - ideal_runtime)
                metrics.quality_loss_seconds += event.ideal_cycle_seconds * event.scrap_count
        elif event.state != "planned_stop":
            metrics.downtime_seconds += duration
            reason = event.reason or event.state
            metrics.downtime_by_reason[reason] = (
                metrics.downtime_by_reason.get(reason, 0.0) + duration
            )

    return PlantReport(assets=sorted(by_asset.values(), key=lambda item: item.asset), warnings=warnings)


def analyze_csv(path: str | Path) -> PlantReport:
    return analyze_events(read_events(path))


def render_markdown(report: PlantReport) -> str:
    lines = [
        "# LinePulse OEE Report",
        "",
        "## Asset Summary",
        "",
        "| Asset | OEE | Availability | Performance | Quality | Lost Hours | Good | Scrap |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for asset in report.assets:
        lines.append(
            "| {asset} | {oee} | {availability} | {performance} | {quality} | {lost_hours:.2f} | {good} | {scrap} |".format(
                asset=asset.asset,
                oee=_percent(asset.oee),
                availability=_percent(asset.availability),
                performance=_percent(asset.performance),
                quality=_percent(asset.quality),
                lost_hours=asset.lost_seconds / 3600,
                good=asset.good_count,
                scrap=asset.scrap_count,
            )
        )

    lines.extend(["", "## Bottleneck Ranking", ""])

    for index, asset in enumerate(report.bottlenecks, start=1):
        top_reason = _top_reason(asset.downtime_by_reason)
        lines.append(
            f"{index}. **{asset.asset}**: {asset.lost_seconds / 3600:.2f} lost hours"
            + (f" (top downtime: {top_reason})" if top_reason else "")
        )

    if report.downtime_pareto:
        lines.extend(
            [
                "",
                "## Downtime Pareto",
                "",
                "| Reason | Lost Hours | Share | Cumulative | Assets |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for item in report.downtime_pareto:
            lines.append(
                "| {reason} | {hours:.2f} | {share} | {cumulative} | {assets} |".format(
                    reason=item.reason,
                    hours=item.seconds / 3600,
                    share=_percent(item.percent_of_downtime),
                    cumulative=_percent(item.cumulative_percent),
                    assets=", ".join(item.assets),
                )
            )

    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)

    return "\n".join(lines) + "\n"


def render_text_table(report: PlantReport) -> str:
    rows = [
        [
            "Asset",
            "OEE",
            "Availability",
            "Performance",
            "Quality",
            "Lost hours",
        ]
    ]
    for asset in report.assets:
        rows.append(
            [
                asset.asset,
                _percent(asset.oee),
                _percent(asset.availability),
                _percent(asset.performance),
                _percent(asset.quality),
                f"{asset.lost_seconds / 3600:.2f}",
            ]
        )

    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )


def render_pareto_table(report: PlantReport) -> str:
    rows = [["Reason", "Lost hours", "Share", "Cumulative", "Assets"]]
    for item in report.downtime_pareto:
        rows.append(
            [
                item.reason,
                f"{item.seconds / 3600:.2f}",
                _percent(item.percent_of_downtime),
                _percent(item.cumulative_percent),
                ", ".join(item.assets),
            ]
        )

    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )


def _event_from_row(row: dict[str, str], line_num: int) -> Event:
    asset = _required(row, "asset", line_num)
    state = _required(row, "state", line_num).strip().lower()
    if state not in VALID_STATES:
        states = ", ".join(sorted(VALID_STATES))
        raise ValueError(f"Line {line_num}: unknown state {state!r}. Expected one of: {states}.")

    event = Event(
        asset=asset,
        start=_parse_datetime(_required(row, "start", line_num), line_num, "start"),
        end=_parse_datetime(_required(row, "end", line_num), line_num, "end"),
        state=state,
        reason=(row.get("reason") or "").strip(),
        good_count=_parse_int(row.get("good_count"), line_num, "good_count"),
        scrap_count=_parse_int(row.get("scrap_count"), line_num, "scrap_count"),
        ideal_cycle_seconds=_parse_optional_float(
            row.get("ideal_cycle_seconds"), line_num, "ideal_cycle_seconds"
        ),
    )
    return event


def _required(row: dict[str, str], key: str, line_num: int) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise ValueError(f"Line {line_num}: missing required column {key!r}.")
    return value


def _parse_datetime(value: str, line_num: int, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"Line {line_num}: invalid {field_name} timestamp {value!r}.") from exc


def _parse_int(value: str | None, line_num: int, field_name: str) -> int:
    if value is None or not value.strip():
        return 0
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"Line {line_num}: invalid integer for {field_name}: {value!r}.") from exc
    if parsed < 0:
        raise ValueError(f"Line {line_num}: {field_name} cannot be negative.")
    return parsed


def _parse_optional_float(value: str | None, line_num: int, field_name: str) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Line {line_num}: invalid number for {field_name}: {value!r}.") from exc
    if parsed <= 0:
        raise ValueError(f"Line {line_num}: {field_name} must be greater than zero.")
    return parsed


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _top_reason(reasons: dict[str, float]) -> str:
    if not reasons:
        return ""
    reason, seconds = max(reasons.items(), key=lambda item: item[1])
    return f"{reason}, {seconds / 60:.0f} min"
