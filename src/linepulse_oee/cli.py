from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyze import analyze_csv, render_markdown, render_pareto_table, render_text_table


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
    analyze.add_argument("--json", type=Path, help="Write full report JSON to this path.")
    analyze.add_argument("--markdown", type=Path, help="Write Markdown report to this path.")
    analyze.add_argument(
        "--pareto",
        action="store_true",
        help="Print a downtime reason Pareto table after the asset summary.",
    )

    subparsers.add_parser("template", help="Print a starter CSV template.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "template":
        print(TEMPLATE, end="")
        return 0

    report = analyze_csv(args.csv_path)
    print(render_text_table(report))
    if args.pareto and report.downtime_pareto:
        print()
        print(render_pareto_table(report))

    if args.json:
        _write_text(args.json, json.dumps(report.as_dict(), indent=2) + "\n")
    if args.markdown:
        _write_text(args.markdown, render_markdown(report))

    return 0


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
