from __future__ import annotations

import io
import unittest

from linepulse_oee.analyze import analyze_events, read_events
from linepulse_oee.charts import render_pareto_svg


class ParetoChartTests(unittest.TestCase):
    def test_renders_pareto_svg_with_bars_and_cumulative_line(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,downtime,material jam,0,0,4
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,changeover,0,0,4
Welder-2,2026-06-01T06:00:00,2026-06-01T06:20:00,downtime,material jam,0,0,8
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        svg = render_pareto_svg(report)

        self.assertIn("<svg", svg)
        self.assertIn("Downtime Pareto", svg)
        self.assertIn("material jam", svg)
        self.assertIn("changeover", svg)
        self.assertIn("<rect", svg)
        self.assertIn("<path", svg)
        self.assertIn("76.9%", svg)
        self.assertIn("downtime interval evidence", svg)

    def test_renders_empty_state_when_no_downtime_reasons_exist(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,700,20,4
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        svg = render_pareto_svg(report)

        self.assertIn("No downtime reason data was found", svg)
        self.assertNotIn("<path", svg)

    def test_escapes_reason_labels(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,downtime,A&B <jam>,0,0,4
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        svg = render_pareto_svg(report)

        self.assertIn("A&amp;B &lt;jam&gt;", svg)
        self.assertNotIn("A&B <jam>", svg)

    def test_rejects_non_positive_max_reasons(self) -> None:
        report = analyze_events([])

        with self.assertRaisesRegex(ValueError, "max_reasons"):
            render_pareto_svg(report, max_reasons=0)


if __name__ == "__main__":
    unittest.main()
