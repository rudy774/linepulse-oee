"""LinePulse OEE manufacturing analytics toolkit."""

from .adapters import AdapterSpec, available_adapters, convert_csv, write_canonical_csv
from .analyze import analyze_events
from .charts import render_pareto_svg
from .dashboard import render_operator_dashboard
from .model import AssetMetrics, Event, PlantReport, ReportRecommendation
from .reason_codes import ReasonCodeMap, read_reason_code_map
from .shift_calendar import ShiftCalendar, read_shift_calendar
from .validation import ValidationIssue, validate_events

__all__ = [
    "AdapterSpec",
    "AssetMetrics",
    "Event",
    "PlantReport",
    "ReportRecommendation",
    "ReasonCodeMap",
    "ShiftCalendar",
    "ValidationIssue",
    "analyze_events",
    "available_adapters",
    "convert_csv",
    "read_reason_code_map",
    "read_shift_calendar",
    "render_operator_dashboard",
    "render_pareto_svg",
    "validate_events",
    "write_canonical_csv",
]
