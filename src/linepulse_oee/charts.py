from __future__ import annotations

from html import escape

from .model import DowntimeParetoItem, PlantReport


def render_pareto_svg(
    report: PlantReport,
    *,
    title: str = "Downtime Pareto",
    max_reasons: int = 10,
    width: int = 960,
) -> str:
    """Render downtime Pareto data as a dependency-free SVG chart."""
    if max_reasons < 1:
        raise ValueError("max_reasons must be at least 1.")

    items = report.downtime_pareto[:max_reasons]
    if not items:
        return _render_empty_chart(title=title, width=width)

    row_height = 52
    top = 130
    bottom = 78
    height = top + (len(items) * row_height) + bottom
    left = 236
    right = 112
    plot_width = max(320, width - left - right)
    bar_height = 24
    points: list[tuple[float, float]] = []

    parts = [
        _svg_open(width, height, title, "Downtime reasons ranked by lost hours with cumulative downtime share."),
        f'<rect width="{width}" height="{height}" rx="18" fill="#F8FAFC"/>',
        f'<rect x="24" y="24" width="{width - 48}" height="{height - 48}" rx="12" fill="#FFFFFF" stroke="#CBD5E1"/>',
        f'<text x="52" y="64" fill="#0F172A" font-family="Segoe UI, Arial, sans-serif" font-size="26" font-weight="700">{_text(title)}</text>',
        "<text x=\"52\" y=\"94\" fill=\"#475569\" font-family=\"Segoe UI, Arial, sans-serif\" font-size=\"15\">Bars show each reason's share of downtime with lost-hour labels. The orange line shows cumulative downtime share.</text>",
        _axis_label(left, top - 18, "Downtime share", "#2563EB"),
        _axis_label(left + plot_width - 156, top - 18, "Cumulative share", "#EA580C"),
        _grid_line(left, top - 8, left + plot_width, top - 8),
    ]

    for tick in (0.0, 0.5, 1.0):
        x = left + (plot_width * tick)
        parts.append(_grid_line(x, top - 8, x, top + (len(items) * row_height) - 18, dash=True))
        parts.append(
            f'<text x="{x}" y="{top + (len(items) * row_height) + 18}" fill="#64748B" '
            f'font-family="Segoe UI, Arial, sans-serif" font-size="12" text-anchor="middle">{tick:.0%}</text>'
        )

    for index, item in enumerate(items):
        center_y = top + (index * row_height) + 16
        bar_y = center_y - (bar_height / 2)
        bar_width = plot_width * item.percent_of_downtime
        bar_label_x = min(left + bar_width + 10, left + plot_width - 58)
        bar_label_fill = "#FFFFFF" if bar_label_x < left + bar_width else "#1E293B"
        cumulative_x = left + (plot_width * item.cumulative_percent)
        points.append((cumulative_x, center_y))
        reason = _truncate(item.reason, 28)

        parts.extend(
            [
                f'<text x="52" y="{center_y + 5}" fill="#0F172A" '
                f'font-family="Segoe UI, Arial, sans-serif" font-size="15" font-weight="600">{_text(reason)}</text>',
                f'<rect x="{left}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_height}" rx="5" fill="#2563EB"/>',
                f'<text x="{bar_label_x:.1f}" y="{center_y + 5}" fill="{bar_label_fill}" '
                f'font-family="Segoe UI, Arial, sans-serif" font-size="13">{item.seconds / 3600:.2f}h</text>',
                f'<circle cx="{cumulative_x:.1f}" cy="{center_y:.1f}" r="5" fill="#EA580C"/>',
                f'<text x="{left + plot_width + 14}" y="{center_y + 5}" fill="#9A3412" '
                f'font-family="Segoe UI, Arial, sans-serif" font-size="13">{item.cumulative_percent:.1%}</text>',
            ]
        )

    parts.append(_line_path(points))
    parts.append(
        f'<text x="52" y="{height - 42}" fill="#64748B" '
        f'font-family="Segoe UI, Arial, sans-serif" font-size="13">{_summary_text(items)}</text>'
    )
    parts.append(
        f'<text x="52" y="{height - 22}" fill="#64748B" '
        'font-family="Segoe UI, Arial, sans-serif" font-size="12">'
        "Generated from downtime interval evidence. Normalize reason codes before comparing lines or sites.</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _render_empty_chart(*, title: str, width: int) -> str:
    height = 260
    return "\n".join(
        [
            _svg_open(width, height, title, "No downtime reason data is available for this report."),
            f'<rect width="{width}" height="{height}" rx="18" fill="#F8FAFC"/>',
            f'<rect x="24" y="24" width="{width - 48}" height="{height - 48}" rx="12" fill="#FFFFFF" stroke="#CBD5E1"/>',
            f'<text x="52" y="72" fill="#0F172A" font-family="Segoe UI, Arial, sans-serif" font-size="26" font-weight="700">{_text(title)}</text>',
            '<text x="52" y="126" fill="#475569" font-family="Segoe UI, Arial, sans-serif" font-size="16">No downtime reason data was found.</text>',
            '<text x="52" y="156" fill="#64748B" font-family="Segoe UI, Arial, sans-serif" font-size="14">Add non-running intervals with governed reasons, then run the report again.</text>',
            "</svg>",
        ]
    ) + "\n"


def _svg_open(width: int, height: int, title: str, desc: str) -> str:
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">'
        f'<title id="title">{_text(title)}</title><desc id="desc">{_text(desc)}</desc>'
    )


def _axis_label(x: float, y: float, label: str, color: str) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="13" font-weight="700">{_text(label)}</text>'
    )


def _grid_line(x1: float, y1: float, x2: float, y2: float, *, dash: bool = False) -> str:
    dash_attr = ' stroke-dasharray="4 6"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#E2E8F0"{dash_attr}/>'


def _line_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    path = " ".join(
        ("M" if index == 0 else "L") + f" {x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    return f'<path d="{path}" fill="none" stroke="#EA580C" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'


def _summary_text(items: list[DowntimeParetoItem]) -> str:
    top = items[0]
    return _text(
        f"Top reason: {top.reason} at {top.seconds / 3600:.2f} lost hours. "
        f"Shown reasons cover {items[-1].cumulative_percent:.1%} of downtime."
    )


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _text(value: str) -> str:
    return escape(value, quote=True)
