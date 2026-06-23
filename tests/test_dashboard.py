from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from linepulse_oee.analyze import analyze_events, read_events
from linepulse_oee.cli import main
from linepulse_oee.dashboard import render_operator_dashboard


class OperatorDashboardTests(unittest.TestCase):
    def test_renders_operator_dashboard_with_context_and_actions(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds,run_id,product,work_order,shift
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,300,3,4,RUN-1001,Widget-A,WO-9001,day
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,material jam,0,0,4,RUN-1001,Widget-A,WO-9001,day
"""
        report = analyze_events(
            read_events(io.StringIO(csv_text)),
            filters={"run_id": ["RUN-1001"]},
        )

        html = render_operator_dashboard(report, title="Day shift board")

        self.assertIn("<!doctype html>", html)
        self.assertIn("Day shift board", html)
        self.assertIn("Press-1", html)
        self.assertIn("RUN-1001", html)
        self.assertIn("Widget-A", html)
        self.assertIn("Downtime Pareto", html)
        self.assertIn("Next Actions", html)
        self.assertIn("material jam", html)

    def test_escapes_dashboard_values(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press<&1,2026-06-01T06:00:00,2026-06-01T06:30:00,downtime,A&B <jam>,0,0,4
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        html = render_operator_dashboard(report)

        self.assertIn("Press&lt;&amp;1", html)
        self.assertIn("A&amp;B &lt;jam&gt;", html)
        self.assertNotIn("A&B <jam>", html)

    def test_cli_dashboard_writes_html(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,300,3,4
"""
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "events.csv"
            output_path = Path(tmp) / "operator.html"
            csv_path.write_text(csv_text, encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["dashboard", str(csv_path), "--output", str(output_path)])

            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("LinePulse operator board", html)
        self.assertIn("OEE", html)


if __name__ == "__main__":
    unittest.main()
