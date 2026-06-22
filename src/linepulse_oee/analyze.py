from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, TextIO

from .model import VALID_STATES, AssetMetrics, Event, PlantReport
from .reason_codes import ReasonCodeMap, read_reason_code_map
from .shift_calendar import ShiftCalendar, read_shift_calendar
from .validation import format_validation_warning, require_event_columns, validate_events


CONTEXT_FIELDS = ("run_id", "product", "work_order", "shift")


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
        require_event_columns(reader.fieldnames)
        events = [_event_from_row(row, reader.line_num) for row in reader]
    finally:
        if close_after:
            handle.close()

    return events


def analyze_events(
    events: Iterable[Event],
    calendar: ShiftCalendar | None = None,
    reason_map: ReasonCodeMap | None = None,
    filters: dict[str, Iterable[str]] | None = None,
) -> PlantReport:
    events = sorted(events, key=lambda item: (item.asset, item.start, item.end))
    normalized_filters = normalize_context_filters(filters)
    if normalized_filters:
        events = [
            event for event in events if _event_matches_context_filters(event, normalized_filters)
        ]

    by_asset: dict[str, AssetMetrics] = {}
    horizons: dict[str, list[datetime]] = {}
    planned_stop_seconds: dict[str, float] = {}
    covered_seconds: dict[str, float] = {}
    unmapped_reasons: set[str] = set()
    warnings: list[str] = []
    contexts = summarize_contexts(events)

    for event in events:
        metrics = by_asset.setdefault(event.asset, AssetMetrics(asset=event.asset))
        duration = event.duration_seconds

        if duration <= 0:
            warnings.append(
                f"Skipped non-positive interval for {event.asset} at {event.start.isoformat()}."
            )
            continue

        _extend_horizon(horizons, event)
        effective_duration = (
            calendar.overlap_seconds(event.asset, event.start, event.end)
            if calendar
            else duration
        )

        if event.state == "planned_stop":
            if calendar:
                planned_stop_seconds[event.asset] = (
                    planned_stop_seconds.get(event.asset, 0.0) + effective_duration
                )
            continue

        if not calendar:
            metrics.planned_seconds += duration
        elif effective_duration <= 0:
            continue
        else:
            covered_seconds[event.asset] = covered_seconds.get(event.asset, 0.0) + effective_duration

        factor = effective_duration / duration

        if event.state == "running":
            metrics.runtime_seconds += effective_duration
            good_count = round(event.good_count * factor)
            scrap_count = round(event.scrap_count * factor)
            metrics.good_count += good_count
            metrics.scrap_count += scrap_count
            if event.ideal_cycle_seconds and event.total_count > 0:
                ideal_runtime = event.ideal_cycle_seconds * (good_count + scrap_count)
                metrics.speed_loss_seconds += max(0.0, effective_duration - ideal_runtime)
                metrics.quality_loss_seconds += event.ideal_cycle_seconds * scrap_count
        else:
            metrics.downtime_seconds += effective_duration
            reason = _normalize_reason(event.reason or event.state, reason_map, unmapped_reasons)
            metrics.downtime_by_reason[reason] = (
                metrics.downtime_by_reason.get(reason, 0.0) + effective_duration
            )

    if calendar:
        _apply_calendar_planned_time(
            by_asset=by_asset,
            horizons=horizons,
            planned_stop_seconds=planned_stop_seconds,
            covered_seconds=covered_seconds,
            calendar=calendar,
            warnings=warnings,
        )

    if reason_map and reason_map.warn_unmapped:
        for reason in sorted(unmapped_reasons):
            warnings.append(f"Reason {reason!r} was not mapped; used as-is.")

    return PlantReport(
        assets=sorted(by_asset.values(), key=lambda item: item.asset),
        warnings=warnings,
        contexts=contexts,
        filters=normalized_filters,
    )


def analyze_csv(
    path: str | Path,
    calendar_path: str | Path | None = None,
    reason_map_path: str | Path | None = None,
    filters: dict[str, Iterable[str]] | None = None,
) -> PlantReport:
    calendar = read_shift_calendar(calendar_path) if calendar_path else None
    reason_map = read_reason_code_map(reason_map_path) if reason_map_path else None
    events = read_events(path)
    normalized_filters = normalize_context_filters(filters)
    filtered_events = [
        event for event in events if _event_matches_context_filters(event, normalized_filters)
    ]
    validation_issues = validate_events(filtered_events, warn_gaps=False)
    report = analyze_events(
        filtered_events,
        calendar=calendar,
        reason_map=reason_map,
        filters=normalized_filters,
    )
    report.warnings[:0] = [format_validation_warning(issue) for issue in validation_issues]
    return report


def render_markdown(report: PlantReport) -> str:
    lines = [
        "# LinePulse OEE Report",
        "",
    ]

    if report.filters or report.contexts:
        lines.extend(["## Report Context", ""])
        if report.filters:
            lines.append(f"- Filters: {_format_context_dict(report.filters)}")
        if report.contexts:
            lines.append(f"- Available context: {_format_context_dict(report.contexts)}")
        lines.append("")

    lines.extend(
        [
        "## Asset Summary",
        "",
        "| Asset | OEE | Availability | Performance | Quality | Lost Hours | Good | Scrap |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

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

    if report.recommendations:
        lines.extend(["", "## Recommendations", ""])
        for index, recommendation in enumerate(report.recommendations, start=1):
            lines.append(f"{index}. **{recommendation.title}** ({recommendation.priority})")
            lines.append(f"   - {recommendation.message}")
            if recommendation.evidence:
                lines.append(f"   - Evidence: {' '.join(recommendation.evidence)}")
            if recommendation.next_steps:
                lines.append(f"   - Next: {recommendation.next_steps[0]}")

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


def render_context_summary(report: PlantReport) -> str:
    lines: list[str] = []
    if report.filters:
        lines.append(f"Filters: {_format_context_dict(report.filters)}")
    if report.contexts:
        lines.append(f"Available context: {_format_context_dict(report.contexts)}")
    return "\n".join(lines)


def render_recommendations(report: PlantReport) -> str:
    lines: list[str] = []
    for index, recommendation in enumerate(report.recommendations, start=1):
        lines.append(f"{index}. [{recommendation.priority}] {recommendation.title}")
        lines.append(f"   {recommendation.message}")
        if recommendation.next_steps:
            lines.append(f"   Next: {recommendation.next_steps[0]}")
    return "\n".join(lines)


def normalize_context_filters(
    filters: dict[str, Iterable[str]] | None,
) -> dict[str, tuple[str, ...]]:
    if not filters:
        return {}

    normalized: dict[str, tuple[str, ...]] = {}
    for field in CONTEXT_FIELDS:
        values = tuple(
            value.strip()
            for value in filters.get(field, ())
            if value and value.strip()
        )
        if values:
            normalized[field] = values
    return normalized


def summarize_contexts(events: Iterable[Event]) -> dict[str, tuple[str, ...]]:
    values: dict[str, set[str]] = {field: set() for field in CONTEXT_FIELDS}
    for event in events:
        for field in CONTEXT_FIELDS:
            value = getattr(event, field)
            if value:
                values[field].add(value)

    return {
        field: tuple(sorted(field_values))
        for field, field_values in values.items()
        if field_values
    }


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
        run_id=(row.get("run_id") or "").strip(),
        product=(row.get("product") or "").strip(),
        work_order=(row.get("work_order") or "").strip(),
        shift=(row.get("shift") or "").strip(),
    )
    return event


def _event_matches_context_filters(
    event: Event,
    filters: dict[str, tuple[str, ...]],
) -> bool:
    for field, allowed_values in filters.items():
        if getattr(event, field) not in allowed_values:
            return False
    return True


def _format_context_dict(context: dict[str, tuple[str, ...]]) -> str:
    return "; ".join(
        f"{field}={', '.join(values)}" for field, values in sorted(context.items()) if values
    )


def _normalize_reason(
    reason: str,
    reason_map: ReasonCodeMap | None,
    unmapped_reasons: set[str],
) -> str:
    if not reason_map:
        return reason

    normalized, matched = reason_map.normalize(reason)
    if not matched:
        unmapped_reasons.add(normalized)
    return normalized


def _extend_horizon(horizons: dict[str, list[datetime]], event: Event) -> None:
    if event.asset not in horizons:
        horizons[event.asset] = [event.start, event.end]
        return
    horizons[event.asset][0] = min(horizons[event.asset][0], event.start)
    horizons[event.asset][1] = max(horizons[event.asset][1], event.end)


def _apply_calendar_planned_time(
    by_asset: dict[str, AssetMetrics],
    horizons: dict[str, list[datetime]],
    planned_stop_seconds: dict[str, float],
    covered_seconds: dict[str, float],
    calendar: ShiftCalendar,
    warnings: list[str],
) -> None:
    for asset, metrics in by_asset.items():
        if asset not in horizons:
            continue

        start, end = horizons[asset]
        calendar_seconds = calendar.planned_seconds(asset, start, end)
        planned_seconds = max(
            0.0,
            calendar_seconds - planned_stop_seconds.get(asset, 0.0),
        )
        metrics.planned_seconds = planned_seconds

        gap_seconds = max(0.0, planned_seconds - covered_seconds.get(asset, 0.0))
        if gap_seconds > 0:
            metrics.downtime_seconds += gap_seconds
            metrics.downtime_by_reason["unclassified calendar gap"] = (
                metrics.downtime_by_reason.get("unclassified calendar gap", 0.0) + gap_seconds
            )
            warnings.append(
                f"Added {gap_seconds / 60:.1f} minutes of unclassified calendar gap for {asset}."
            )


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
