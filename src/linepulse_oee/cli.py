from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import adapter_choices, convert_csv, write_canonical_csv
from .analyze import (
    analyze_csv,
    render_markdown,
    render_pareto_table,
    render_recommendations,
    render_text_table,
)
from .charts import render_pareto_svg
from .validation import (
    ValidationIssue,
    has_errors,
    render_validation_issues,
    validate_events,
)


TEMPLATE = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,340,4,4.5
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,material jam,0,0,4.5
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
    analyze.add_argument("--json", type=Path, help="Write full report JSON to this path.")
    analyze.add_argument("--markdown", type=Path, help="Write Markdown report to this path.")
    analyze.add_argument("--pareto-svg", type=Path, help="Write a downtime Pareto SVG chart to this path.")
    analyze.add_argument(
        "--pareto",
        action="store_true",
        help="Print a downtime reason Pareto table after the asset summary.",
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

    report = analyze_csv(
        args.csv_path,
        calendar_path=args.calendar,
        reason_map_path=args.reason_map,
    )
    print(render_text_table(report))
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


if __name__ == "__main__":
    raise SystemExit(main())
