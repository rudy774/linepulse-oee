from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import adapter_choices, convert_csv, write_canonical_csv
from .analyze import (
    analyze_csv,
    render_markdown,
    render_context_summary,
    render_pareto_table,
    render_recommendations,
    render_text_table,
)
from .charts import render_pareto_svg
from .dashboard import render_operator_dashboard
from .validation import (
    ValidationIssue,
    has_errors,
    render_validation_issues,
    validate_events,
)


TEMPLATE = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds,run_id,product,work_order,shift
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,340,4,4.5,RUN-1001,Widget-A,WO-9001,day
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,material jam,0,0,4.5,RUN-1001,Widget-A,WO-9001,day
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linepulse",
        description="Analyze manufacturing event logs for OEE and bottlenecks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze a machine event CSV.")
    analyze.add_argument("csv_path", type=Path, help="Path to a machine event CSV.")
    analyze.add_argument(
        "--calendar",
        type=Path,
        help="Optional JSON shift calendar for deriving planned production time.",
    )
    analyze.add_argument(
        "--reason-map",
        type=Path,
        help="Optional JSON reason-code map for grouping downtime reason aliases.",
    )
    analyze.add_argument(
        "--run-id",
        action="append",
        dest="run_ids",
        help="Only analyze event rows with this run_id. Can be used more than once.",
    )
    analyze.add_argument(
        "--product",
        action="append",
        dest="products",
        help="Only analyze event rows with this product. Can be used more than once.",
    )
    analyze.add_argument(
        "--work-order",
        action="append",
        dest="work_orders",
        help="Only analyze event rows with this work_order. Can be used more than once.",
    )
    analyze.add_argument(
        "--shift",
        action="append",
        dest="shifts",
        help="Only analyze event rows with this shift. Can be used more than once.",
    )
    analyze.add_argument("--json", type=Path, help="Write full report JSON to this path.")
    analyze.add_argument("--markdown", type=Path, help="Write Markdown report to this path.")
    analyze.add_argument("--pareto-svg", type=Path, help="Write a downtime Pareto SVG chart to this path.")
    analyze.add_argument(
        "--pareto",
        action="store_true",
        help="Print a downtime reason Pareto table after the asset summary.",
    )

    dashboard = subparsers.add_parser(
        "dashboard",
        help="Build an operator HTML dashboard from a machine event CSV.",
    )
    dashboard.add_argument("csv_path", type=Path, help="Path to a machine event CSV.")
    dashboard.add_argument(
        "--calendar",
        type=Path,
        help="Optional JSON shift calendar for deriving planned production time.",
    )
    dashboard.add_argument(
        "--reason-map",
        type=Path,
        help="Optional JSON reason-code map for grouping downtime reason aliases.",
    )
    dashboard.add_argument(
        "--run-id",
        action="append",
        dest="run_ids",
        help="Only analyze event rows with this run_id. Can be used more than once.",
    )
    dashboard.add_argument(
        "--product",
        action="append",
        dest="products",
        help="Only analyze event rows with this product. Can be used more than once.",
    )
    dashboard.add_argument(
        "--work-order",
        action="append",
        dest="work_orders",
        help="Only analyze event rows with this work_order. Can be used more than once.",
    )
    dashboard.add_argument(
        "--shift",
        action="append",
        dest="shifts",
        help="Only analyze event rows with this shift. Can be used more than once.",
    )
    dashboard.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path for the generated operator dashboard HTML.",
    )
    dashboard.add_argument(
        "--title",
        default="LinePulse operator board",
        help="Dashboard title shown at the top of the generated HTML.",
    )

    convert = subparsers.add_parser(
        "convert",
        help="Convert supported historian, MES, or downtime exports to LinePulse CSV.",
    )
    convert.add_argument("csv_path", type=Path, help="Path to the source export CSV.")
    convert.add_argument(
        "--adapter",
        required=True,
        choices=adapter_choices(),
        help="Source export layout to convert.",
    )
    convert.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path for the normalized LinePulse CSV.",
    )

    validate = subparsers.add_parser("validate", help="Validate a LinePulse machine event CSV.")
    validate.add_argument("csv_path", type=Path, help="Path to a machine event CSV.")
    validate.add_argument(
        "--no-gap-warnings",
        action="store_true",
        help="Do not warn when an asset timeline has a gap between rows.",
    )
    validate.add_argument("--json", type=Path, help="Write validation issues as JSON.")

    subparsers.add_parser("template", help="Print a starter CSV template.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "template":
        print(TEMPLATE, end="")
        return 0

    if args.command == "convert":
        rows = convert_csv(args.csv_path, args.adapter)
        count = write_canonical_csv(rows, args.output)
        print(f"Wrote {count} normalized rows to {args.output}")
        return 0

    if args.command == "validate":
        try:
            from .analyze import read_events

            events = read_events(args.csv_path)
            issues = validate_events(events, warn_gaps=not args.no_gap_warnings)
        except ValueError as exc:
            issues = [ValidationIssue("error", "parse_error", str(exc))]

        print(render_validation_issues(issues))
        if args.json:
            payload = {
                "ok": not has_errors(issues),
                "issues": [issue.as_dict() for issue in issues],
            }
            _write_text(args.json, json.dumps(payload, indent=2) + "\n")
        return 1 if has_errors(issues) else 0

    if args.command == "dashboard":
        report = analyze_csv(
            args.csv_path,
            calendar_path=args.calendar,
            reason_map_path=args.reason_map,
            filters=_context_filters(args),
        )
        _write_text(args.output, render_operator_dashboard(report, title=args.title))
        print(f"Wrote operator dashboard to {args.output}")
        return 0

    report = analyze_csv(
        args.csv_path,
        calendar_path=args.calendar,
        reason_map_path=args.reason_map,
        filters=_context_filters(args),
    )
    print(render_text_table(report))
    context_summary = render_context_summary(report)
    if context_summary:
        print()
        print("Context")
        print(context_summary)

    if args.pareto and report.downtime_pareto:
        print()
        print(render_pareto_table(report))

    if report.recommendations:
        print()
        print("Recommendations")
        print(render_recommendations(report))

    if report.warnings:
        print()
        print("Warnings")
        for warning in report.warnings:
            print(f"- {warning}")

    if args.json:
        _write_text(args.json, json.dumps(report.as_dict(), indent=2) + "\n")
    if args.markdown:
        _write_text(args.markdown, render_markdown(report))
    if args.pareto_svg:
        _write_text(args.pareto_svg, render_pareto_svg(report))

    return 0


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _context_filters(args: argparse.Namespace) -> dict[str, tuple[str, ...]]:
    return {
        "run_id": tuple(args.run_ids or ()),
        "product": tuple(args.products or ()),
        "work_order": tuple(args.work_orders or ()),
        "shift": tuple(args.shifts or ()),
    }


if __name__ == "__main__":
    raise SystemExit(main())
