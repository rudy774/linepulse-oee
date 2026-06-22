from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


CANONICAL_COLUMNS = (
    "asset",
    "start",
    "end",
    "state",
    "reason",
    "good_count",
    "scrap_count",
    "ideal_cycle_seconds",
    "run_id",
    "product",
    "work_order",
    "shift",
)


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    description: str
    required_columns: tuple[str, ...]


RowAdapter = Callable[[dict[str, str], int], dict[str, str]]


IGNITION_HISTORIAN = AdapterSpec(
    name="ignition-historian",
    description="Ignition-style interval export with equipment_path, timestamps, state_code, and counts.",
    required_columns=(
        "equipment_path",
        "start_ts",
        "end_ts",
        "state_code",
        "downtime_reason",
        "good_parts",
        "scrap_parts",
        "ideal_cycle_seconds",
    ),
)

MES_PRODUCTION_LOG = AdapterSpec(
    name="mes-production-log",
    description="MES production log with work_center, event_type, quantities, and standard cycle time.",
    required_columns=(
        "work_center",
        "started_at",
        "finished_at",
        "event_type",
        "reason_code",
        "good_qty",
        "reject_qty",
        "target_cycle_seconds",
    ),
)

MANUAL_DOWNTIME_LOG = AdapterSpec(
    name="manual-downtime-log",
    description="Manual downtime spreadsheet with down_start, down_end, reason, and planned flag.",
    required_columns=(
        "asset",
        "down_start",
        "down_end",
        "reason",
        "planned",
    ),
)


def available_adapters() -> tuple[AdapterSpec, ...]:
    return tuple(_ADAPTERS[name][0] for name in sorted(_ADAPTERS))


def adapter_choices() -> tuple[str, ...]:
    return tuple(spec.name for spec in available_adapters())


def convert_csv(source: str | Path | TextIO, adapter_name: str) -> list[dict[str, str]]:
    """Convert a known source export layout into LinePulse's canonical CSV rows."""
    try:
        spec, row_adapter = _ADAPTERS[adapter_name]
    except KeyError as exc:
        choices = ", ".join(adapter_choices())
        raise ValueError(f"Unknown adapter {adapter_name!r}. Expected one of: {choices}.") from exc

    close_after = False
    if isinstance(source, (str, Path)):
        handle = Path(source).open("r", encoding="utf-8-sig", newline="")
        close_after = True
    else:
        handle = source

    try:
        reader = csv.DictReader(handle)
        _validate_columns(spec, reader.fieldnames)
        return [row_adapter(_normalize_row(row), reader.line_num) for row in reader]
    finally:
        if close_after:
            handle.close()


def write_canonical_csv(rows: Iterable[dict[str, str]], destination: str | Path | TextIO) -> int:
    row_list = list(rows)
    close_after = False
    if isinstance(destination, (str, Path)):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("w", encoding="utf-8", newline="")
        close_after = True
    else:
        handle = destination

    try:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(row_list)
    finally:
        if close_after:
            handle.close()
    return len(row_list)


def _convert_ignition(row: dict[str, str], line_num: int) -> dict[str, str]:
    return _canonical_row(
        asset=_required(row, "equipment_path", line_num),
        start=_required(row, "start_ts", line_num),
        end=_required(row, "end_ts", line_num),
        state=_normalize_state(_required(row, "state_code", line_num), line_num),
        reason=_optional(row, "downtime_reason"),
        good_count=_optional(row, "good_parts", default="0"),
        scrap_count=_optional(row, "scrap_parts", default="0"),
        ideal_cycle_seconds=_optional(row, "ideal_cycle_seconds"),
        run_id=_first_optional(row, "run_id", "production_run_id", "job_id"),
        product=_first_optional(row, "product", "product_code", "sku", "part_number"),
        work_order=_first_optional(row, "work_order", "work_order_id", "order_id", "production_order"),
        shift=_first_optional(row, "shift", "shift_name"),
    )


def _convert_mes(row: dict[str, str], line_num: int) -> dict[str, str]:
    return _canonical_row(
        asset=_required(row, "work_center", line_num),
        start=_required(row, "started_at", line_num),
        end=_required(row, "finished_at", line_num),
        state=_normalize_state(_required(row, "event_type", line_num), line_num),
        reason=_optional(row, "reason_code"),
        good_count=_optional(row, "good_qty", default="0"),
        scrap_count=_optional(row, "reject_qty", default="0"),
        ideal_cycle_seconds=_optional(row, "target_cycle_seconds"),
        run_id=_first_optional(row, "run_id", "production_run_id", "job_id"),
        product=_first_optional(row, "product", "product_code", "sku", "part_number"),
        work_order=_first_optional(row, "work_order", "work_order_id", "order_id", "production_order"),
        shift=_first_optional(row, "shift", "shift_name"),
    )


def _convert_manual_downtime(row: dict[str, str], line_num: int) -> dict[str, str]:
    is_planned = _parse_bool(_required(row, "planned", line_num), line_num, "planned")
    return _canonical_row(
        asset=_required(row, "asset", line_num),
        start=_required(row, "down_start", line_num),
        end=_required(row, "down_end", line_num),
        state="planned_stop" if is_planned else "downtime",
        reason=_required(row, "reason", line_num),
        good_count="0",
        scrap_count="0",
        ideal_cycle_seconds=_optional(row, "ideal_cycle_seconds"),
        run_id=_first_optional(row, "run_id", "production_run_id", "job_id"),
        product=_first_optional(row, "product", "product_code", "sku", "part_number"),
        work_order=_first_optional(row, "work_order", "work_order_id", "order_id", "production_order"),
        shift=_first_optional(row, "shift", "shift_name"),
    )


def _validate_columns(spec: AdapterSpec, fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise ValueError(f"{spec.name} input is empty or missing a header row.")

    present = {field.strip() for field in fieldnames}
    missing = [column for column in spec.required_columns if column not in present]
    if missing:
        missing_list = ", ".join(missing)
        required = ", ".join(spec.required_columns)
        raise ValueError(
            f"{spec.name} input is missing required column(s): {missing_list}. "
            f"Required columns: {required}."
        )


def _canonical_row(
    *,
    asset: str,
    start: str,
    end: str,
    state: str,
    reason: str = "",
    good_count: str = "0",
    scrap_count: str = "0",
    ideal_cycle_seconds: str = "",
    run_id: str = "",
    product: str = "",
    work_order: str = "",
    shift: str = "",
) -> dict[str, str]:
    return {
        "asset": asset.strip(),
        "start": start.strip(),
        "end": end.strip(),
        "state": state.strip(),
        "reason": reason.strip(),
        "good_count": (good_count or "0").strip(),
        "scrap_count": (scrap_count or "0").strip(),
        "ideal_cycle_seconds": ideal_cycle_seconds.strip(),
        "run_id": run_id.strip(),
        "product": product.strip(),
        "work_order": work_order.strip(),
        "shift": shift.strip(),
    }


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {key.strip(): (value or "") for key, value in row.items() if key is not None}


def _normalize_state(value: str, line_num: int) -> str:
    token = _clean_token(value)
    state_map = {
        "auto": "running",
        "production": "running",
        "production run": "running",
        "producing": "running",
        "run": "running",
        "running": "running",
        "break": "planned_stop",
        "meal": "planned_stop",
        "meeting": "planned_stop",
        "planned": "planned_stop",
        "planned stop": "planned_stop",
        "scheduled stop": "planned_stop",
        "changeover": "changeover",
        "setup": "changeover",
        "set up": "changeover",
        "tooling": "changeover",
        "blocked": "idle",
        "idle": "idle",
        "starved": "idle",
        "waiting": "idle",
        "down": "downtime",
        "downtime": "downtime",
        "fault": "downtime",
        "faulted": "downtime",
        "stop": "downtime",
        "stopped": "downtime",
        "unplanned down": "downtime",
        "unplanned downtime": "downtime",
    }
    try:
        return state_map[token]
    except KeyError as exc:
        expected = ", ".join(sorted(set(state_map)))
        raise ValueError(
            f"Line {line_num}: unknown source state {value!r}. Expected one of: {expected}."
        ) from exc


def _parse_bool(value: str, line_num: int, field_name: str) -> bool:
    token = _clean_token(value)
    if token in {"1", "planned", "planned stop", "true", "y", "yes"}:
        return True
    if token in {"0", "downtime", "false", "n", "no", "unplanned", "unplanned down"}:
        return False
    raise ValueError(f"Line {line_num}: invalid boolean for {field_name}: {value!r}.")


def _clean_token(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _required(row: dict[str, str], key: str, line_num: int) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise ValueError(f"Line {line_num}: missing required column {key!r}.")
    return value


def _optional(row: dict[str, str], key: str, default: str = "") -> str:
    value = row.get(key)
    if value is None or not value.strip():
        return default
    return value.strip()


def _first_optional(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value and value.strip():
            return value.strip()
    return ""


_ADAPTERS: dict[str, tuple[AdapterSpec, RowAdapter]] = {
    IGNITION_HISTORIAN.name: (IGNITION_HISTORIAN, _convert_ignition),
    MANUAL_DOWNTIME_LOG.name: (MANUAL_DOWNTIME_LOG, _convert_manual_downtime),
    MES_PRODUCTION_LOG.name: (MES_PRODUCTION_LOG, _convert_mes),
}
