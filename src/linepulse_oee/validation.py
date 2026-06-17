from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from .model import Event


REQUIRED_EVENT_COLUMNS = ("asset", "start", "end", "state")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


def validate_event_columns(fieldnames: list[str] | None) -> list[ValidationIssue]:
    if not fieldnames:
        return [
            ValidationIssue(
                severity="error",
                code="missing_header",
                message="CSV is empty or missing a header row.",
            )
        ]

    present = {field.strip() for field in fieldnames}
    missing = [column for column in REQUIRED_EVENT_COLUMNS if column not in present]
    if not missing:
        return []

    required = ", ".join(REQUIRED_EVENT_COLUMNS)
    missing_list = ", ".join(missing)
    return [
        ValidationIssue(
            severity="error",
            code="missing_required_columns",
            message=(
                f"Missing required column(s): {missing_list}. "
                f"Required columns: {required}."
            ),
        )
    ]


def require_event_columns(fieldnames: list[str] | None) -> None:
    issues = validate_event_columns(fieldnames)
    if issues:
        raise ValueError(issues[0].message)


def validate_events(
    events: Iterable[Event],
    *,
    warn_gaps: bool = True,
    gap_tolerance_seconds: float = 0.0,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sorted_events = sorted(events, key=lambda item: (item.asset, item.start, item.end, item.state))
    seen: set[tuple[object, ...]] = set()
    by_asset: dict[str, list[Event]] = {}

    for event in sorted_events:
        key = (
            event.asset,
            event.start,
            event.end,
            event.state,
            event.reason,
            event.good_count,
            event.scrap_count,
            event.ideal_cycle_seconds,
        )
        if key in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_interval",
                    message=(
                        f"{event.asset} has a duplicate {event.state} interval from "
                        f"{event.start.isoformat()} to {event.end.isoformat()}."
                    ),
                )
            )
        seen.add(key)

        duration = event.duration_seconds
        if duration <= 0:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="non_positive_interval",
                    message=(
                        f"{event.asset} interval starting {event.start.isoformat()} "
                        "must end after it starts."
                    ),
                )
            )
            continue

        if event.state in {"downtime", "idle", "changeover"} and not event.reason:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="missing_reason",
                    message=(
                        f"{event.asset} {event.state} interval from {event.start.isoformat()} "
                        "has no reason. Add a governed downtime reason for useful Pareto output."
                    ),
                )
            )

        if event.state == "running" and event.total_count == 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="running_without_counts",
                    message=(
                        f"{event.asset} running interval from {event.start.isoformat()} "
                        "has zero good and scrap counts."
                    ),
                )
            )
        elif event.state != "running" and event.total_count > 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="counts_on_non_running_interval",
                    message=(
                        f"{event.asset} {event.state} interval from {event.start.isoformat()} "
                        "contains production counts. Verify whether the state or counts are correct."
                    ),
                )
            )

        by_asset.setdefault(event.asset, []).append(event)

    tolerance = timedelta(seconds=gap_tolerance_seconds)
    for asset, asset_events in by_asset.items():
        previous: Event | None = None
        for event in asset_events:
            if event.duration_seconds <= 0:
                continue
            if previous is None:
                previous = event
                continue

            if event.start < previous.end:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="overlapping_intervals",
                        message=(
                            f"{asset} interval starting {event.start.isoformat()} overlaps "
                            f"the previous interval ending {previous.end.isoformat()}."
                        ),
                    )
                )
            elif warn_gaps and event.start > previous.end + tolerance:
                gap_minutes = (event.start - previous.end).total_seconds() / 60
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="timeline_gap",
                        message=(
                            f"{asset} has a {gap_minutes:.1f} minute gap between "
                            f"{previous.end.isoformat()} and {event.start.isoformat()}."
                        ),
                    )
                )

            if event.end > previous.end:
                previous = event

    return issues


def has_errors(issues: Iterable[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def render_validation_issues(issues: Iterable[ValidationIssue]) -> str:
    issue_list = list(issues)
    if not issue_list:
        return "Validation passed: no issues found."

    rows = [["Severity", "Code", "Message"]]
    rows.extend([issue.severity, issue.code, issue.message] for issue in issue_list)
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )


def format_validation_warning(issue: ValidationIssue) -> str:
    return f"Data quality {issue.severity}: {issue.message}"
