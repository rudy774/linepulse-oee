from __future__ import annotations

import io
import unittest

from linepulse_oee.analyze import (
    analyze_events,
    read_events,
    render_markdown,
    render_pareto_table,
)


class AnalyzeEventsTests(unittest.TestCase):
    def test_calculates_oee_components(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,700,20,4
Press-1,2026-06-01T07:00:00,2026-06-01T07:30:00,downtime,maintenance,0,0,4
Press-1,2026-06-01T07:30:00,2026-06-01T08:00:00,planned_stop,break,0,0,4
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        self.assertEqual(len(report.assets), 1)
        asset = report.assets[0]
        self.assertEqual(asset.asset, "Press-1")
        self.assertEqual(asset.planned_seconds, 5400)
        self.assertEqual(asset.runtime_seconds, 3600)
        self.assertEqual(asset.downtime_seconds, 1800)
        self.assertAlmostEqual(asset.availability, 2 / 3)
        self.assertAlmostEqual(asset.performance, 0.8)
        self.assertAlmostEqual(asset.quality, 700 / 720)
        self.assertAlmostEqual(asset.oee, (2 / 3) * 0.8 * (700 / 720))
        self.assertEqual(asset.downtime_by_reason["maintenance"], 1800)

    def test_rejects_unknown_state(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,broken,,0,0,4
"""
        with self.assertRaisesRegex(ValueError, "unknown state"):
            read_events(io.StringIO(csv_text))

    def test_markdown_contains_bottleneck_ranking(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,720,0,4
Welder-2,2026-06-01T06:00:00,2026-06-01T07:00:00,downtime,fixtures,0,0,8
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))
        markdown = render_markdown(report)

        self.assertIn("# LinePulse OEE Report", markdown)
        self.assertIn("**Welder-2**", markdown)
        self.assertIn("top downtime: fixtures", markdown)

    def test_builds_downtime_pareto_across_assets(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,downtime,material jam,0,0,4
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,changeover,0,0,4
Welder-2,2026-06-01T06:00:00,2026-06-01T06:20:00,downtime,material jam,0,0,8
Welder-2,2026-06-01T06:20:00,2026-06-01T06:30:00,idle,waiting on fixtures,0,0,8
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        pareto = report.downtime_pareto
        self.assertEqual([item.reason for item in pareto], ["material jam", "changeover", "waiting on fixtures"])
        self.assertEqual(pareto[0].seconds, 3000)
        self.assertAlmostEqual(pareto[0].percent_of_downtime, 3000 / 4500)
        self.assertAlmostEqual(pareto[-1].cumulative_percent, 1.0)
        self.assertEqual(pareto[0].assets, ("Press-1", "Welder-2"))
        self.assertIn("Downtime Pareto", render_markdown(report))
        self.assertIn("material jam", render_pareto_table(report))


if __name__ == "__main__":
    unittest.main()
