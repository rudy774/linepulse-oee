from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TextIO


WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


@dataclass(frozen=True)
class BreakRule:
    start: time
    end: time
    name: str = ""


@dataclass(frozen=True)
class ShiftRule:
    start: time
    end: time
    name: str = ""
    breaks: tuple[BreakRule, ...] = ()


@dataclass(frozen=True)
class CalendarRule:
    weekdays: frozenset[int]
    shifts: tuple[ShiftRule, ...]


@dataclass(frozen=True)
class ShiftCalendar:
    default_rule: CalendarRule
    asset_rules: dict[str, CalendarRule] = field(default_factory=dict)

    def planned_intervals(
        self,
        asset: str,
        range_start: datetime,
        range_end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        if range_end <= range_start:
            return []

        rule = self.asset_rules.get(asset, self.default_rule)
        intervals: list[tuple[datetime, datetime]] = []
        current = range_start.date() - timedelta(days=1)
        last_day = range_end.date() + timedelta(days=1)

        while current <= last_day:
            if current.weekday() in rule.weekdays:
                for shift in rule.shifts:
                    intervals.extend(
                        _clip_segments(
                            _shift_segments(current, shift, range_start.tzinfo),
                            range_start,
                            range_end,
                        )
                    )
            current += timedelta(days=1)

        return sorted(intervals)

    def planned_seconds(self, asset: str, range_start: datetime, range_end: datetime) -> float:
        return sum(
            (end - start).total_seconds()
            for start, end in self.planned_intervals(asset, range_start, range_end)
        )

    def overlap_seconds(self, asset: str, start: datetime, end: datetime) -> float:
        return sum(
            _overlap_seconds(start, end, planned_start, planned_end)
            for planned_start, planned_end in self.planned_intervals(asset, start, end)
        )


def read_shift_calendar(source: str | Path | TextIO) -> ShiftCalendar:
    close_after = False
    if isinstance(source, (str, Path)):
        handle = Path(source).open("r", encoding="utf-8")
        close_after = True
    else:
        handle = source

    try:
        data = json.load(handle)
    finally:
        if close_after:
            handle.close()

    if not isinstance(data, dict):
        raise ValueError("Shift calendar must be a JSON object.")

    default_rule = _calendar_rule_from_dict(data, "calendar")
    asset_rules = _asset_rules_from_dict(data)
    return ShiftCalendar(default_rule=default_rule, asset_rules=asset_rules)


def _asset_rules_from_dict(data: dict[str, object]) -> dict[str, CalendarRule]:
    assets = data.get("assets") or {}
    if not isinstance(assets, dict):
        raise ValueError("calendar: assets must be an object keyed by asset name.")

    rules = {}
    for asset, asset_data in assets.items():
        if not isinstance(asset_data, dict):
            raise ValueError(f"assets.{asset}: schedule override must be an object.")
        rules[str(asset)] = _calendar_rule_from_dict(
            {
                "weekdays": asset_data.get("weekdays", data.get("weekdays")),
                "shifts": asset_data.get("shifts", data.get("shifts")),
            },
            f"assets.{asset}",
        )
    return rules


def _calendar_rule_from_dict(data: dict[str, object], context: str) -> CalendarRule:
    weekdays = _parse_weekdays(data.get("weekdays"), context)
    shifts_data = data.get("shifts")
    if not isinstance(shifts_data, list) or not shifts_data:
        raise ValueError(f"{context}: shifts must be a non-empty list.")

    shifts = tuple(
        _shift_from_dict(item, f"{context}.shifts[{index}]")
        for index, item in enumerate(shifts_data)
    )
    return CalendarRule(weekdays=frozenset(weekdays), shifts=shifts)


def _shift_from_dict(data: object, context: str) -> ShiftRule:
    if not isinstance(data, dict):
        raise ValueError(f"{context}: shift must be an object.")
    breaks = tuple(
        _break_from_dict(item, f"{context}.breaks[{index}]")
        for index, item in enumerate(data.get("breaks") or [])
    )
    return ShiftRule(
        name=str(data.get("name") or ""),
        start=_parse_time(data.get("start"), f"{context}.start"),
        end=_parse_time(data.get("end"), f"{context}.end"),
        breaks=breaks,
    )


def _break_from_dict(data: object, context: str) -> BreakRule:
    if not isinstance(data, dict):
        raise ValueError(f"{context}: break must be an object.")
    return BreakRule(
        name=str(data.get("name") or ""),
        start=_parse_time(data.get("start"), f"{context}.start"),
        end=_parse_time(data.get("end"), f"{context}.end"),
    )


def _parse_weekdays(value: object, context: str) -> set[int]:
    if value == "all":
        return set(range(7))
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context}: weekdays must be a non-empty list or 'all'.")

    weekdays: set[int] = set()
    for item in value:
        key = str(item).strip().lower()
        if key not in WEEKDAYS:
            raise ValueError(f"{context}: unknown weekday {item!r}.")
        weekdays.add(WEEKDAYS[key])
    return weekdays


def _parse_time(value: object, context: str) -> time:
    if not isinstance(value, str):
        raise ValueError(f"{context}: expected time string like '06:00'.")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{context}: invalid time {value!r}.") from exc


def _shift_segments(day: date, shift: ShiftRule, tzinfo: object) -> list[tuple[datetime, datetime]]:
    shift_start = _combine(day, shift.start, tzinfo)
    shift_end = _combine(day, shift.end, tzinfo)
    if shift_end <= shift_start:
        shift_end += timedelta(days=1)

    segments = [(shift_start, shift_end)]
    for break_rule in shift.breaks:
        break_start = _combine(day, break_rule.start, tzinfo)
        if break_start < shift_start:
            break_start += timedelta(days=1)
        break_end = _combine(day, break_rule.end, tzinfo)
        if break_end <= break_start:
            break_end += timedelta(days=1)
        segments = _subtract_interval(segments, break_start, break_end)

    return segments


def _combine(day: date, clock: time, tzinfo: object) -> datetime:
    return datetime.combine(day, clock).replace(tzinfo=tzinfo)


def _subtract_interval(
    segments: list[tuple[datetime, datetime]],
    cut_start: datetime,
    cut_end: datetime,
) -> list[tuple[datetime, datetime]]:
    updated: list[tuple[datetime, datetime]] = []
    for start, end in segments:
        if cut_end <= start or cut_start >= end:
            updated.append((start, end))
            continue
        if cut_start > start:
            updated.append((start, min(cut_start, end)))
        if cut_end < end:
            updated.append((max(cut_end, start), end))
    return updated


def _clip_segments(
    segments: list[tuple[datetime, datetime]],
    range_start: datetime,
    range_end: datetime,
) -> list[tuple[datetime, datetime]]:
    clipped = []
    for start, end in segments:
        clipped_start = max(start, range_start)
        clipped_end = min(end, range_end)
        if clipped_end > clipped_start:
            clipped.append((clipped_start, clipped_end))
    return clipped


def _overlap_seconds(
    start: datetime,
    end: datetime,
    planned_start: datetime,
    planned_end: datetime,
) -> float:
    overlap_start = max(start, planned_start)
    overlap_end = min(end, planned_end)
    if overlap_end <= overlap_start:
        return 0.0
    return (overlap_end - overlap_start).total_seconds()
