from __future__ import annotations

import io
import unittest

from linepulse_oee.analyze import (
    analyze_events,
    read_events,
    render_context_summary,
    render_markdown,
    render_pareto_table,
    render_recommendations,
)
from linepulse_oee.reason_codes import read_reason_code_map
from linepulse_oee.shift_calendar import read_shift_calendar


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

    def test_reads_optional_context_columns(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds,run_id,product,work_order,shift
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,300,0,4,RUN-1001,Widget-A,WO-9001,day
"""
        event = read_events(io.StringIO(csv_text))[0]

        self.assertEqual(event.run_id, "RUN-1001")
        self.assertEqual(event.product, "Widget-A")
        self.assertEqual(event.work_order, "WO-9001")
        self.assertEqual(event.shift, "day")

    def test_filters_events_by_production_context(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds,run_id,product,work_order,shift
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,300,0,4,RUN-1001,Widget-A,WO-9001,day
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,material jam,0,0,4,RUN-1001,Widget-A,WO-9001,day
Press-1,2026-06-01T06:45:00,2026-06-01T07:15:00,running,,320,0,4,RUN-1002,Widget-B,WO-9002,day
Welder-2,2026-06-01T06:00:00,2026-06-01T06:30:00,downtime,fixtures,0,0,8,RUN-1001,Widget-A,WO-9001,night
"""
        report = analyze_events(
            read_events(io.StringIO(csv_text)),
            filters={
                "run_id": ["RUN-1001"],
                "product": ["Widget-A"],
                "work_order": ["WO-9001"],
                "shift": ["day"],
            },
        )

        self.assertEqual([asset.asset for asset in report.assets], ["Press-1"])
        asset = report.assets[0]
        self.assertEqual(asset.runtime_seconds, 1800)
        self.assertEqual(asset.downtime_seconds, 900)
        self.assertEqual(asset.downtime_by_reason["material jam"], 900)
        self.assertEqual(report.filters["run_id"], ("RUN-1001",))
        self.assertEqual(report.contexts["product"], ("Widget-A",))
        self.assertIn("run_id=RUN-1001", render_context_summary(report))
        self.assertIn("## Report Context", render_markdown(report))
        self.assertEqual(report.as_dict()["filters"]["work_order"], ["WO-9001"])

    def test_recommends_when_context_filter_matches_no_events(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds,run_id
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,300,0,4,RUN-1001
"""
        report = analyze_events(
            read_events(io.StringIO(csv_text)),
            filters={"run_id": ["RUN-9999"]},
        )

        self.assertEqual(report.assets, [])
        self.assertEqual(report.recommendations[0].category, "context-filter")
        self.assertIn("RUN-9999", report.recommendations[0].evidence[0])

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

    def test_report_recommendations_prioritize_constraint_and_downtime_reason(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,720,0,4
Welder-2,2026-06-01T06:00:00,2026-06-01T07:00:00,downtime,fixtures,0,0,8
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        recommendations = report.recommendations
        self.assertEqual(recommendations[0].category, "constraint")
        self.assertIn("Welder-2", recommendations[0].title)
        self.assertTrue(any(item.category == "downtime" for item in recommendations))
        self.assertIn("Recommendations", render_markdown(report))
        self.assertIn("Start with Welder-2", render_recommendations(report))
        self.assertIn("recommendations", report.as_dict())

    def test_report_recommendations_call_out_quality_loss(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,60,40,30
"""
        report = analyze_events(read_events(io.StringIO(csv_text)))

        self.assertTrue(any(item.category == "quality" for item in report.recommendations))
        quality = next(item for item in report.recommendations if item.category == "quality")
        self.assertIn("Classify scrap", quality.title)
        self.assertTrue(quality.next_steps)

    def test_shift_calendar_derives_planned_time_and_excludes_breaks(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,60,0,60
Press-1,2026-06-01T07:15:00,2026-06-01T08:00:00,downtime,maintenance,0,0,60
"""
        calendar = read_shift_calendar(
            io.StringIO(
                """{
  "weekdays": ["monday"],
  "shifts": [
    {
      "name": "day",
      "start": "06:00",
      "end": "08:00",
      "breaks": [{"name": "break", "start": "07:00", "end": "07:15"}]
    }
  ]
}"""
            )
        )

        report = analyze_events(read_events(io.StringIO(csv_text)), calendar=calendar)
        asset = report.assets[0]

        self.assertEqual(asset.planned_seconds, 6300)
        self.assertEqual(asset.runtime_seconds, 3600)
        self.assertEqual(asset.downtime_seconds, 2700)
        self.assertAlmostEqual(asset.availability, 3600 / 6300)
        self.assertEqual(report.warnings, [])

    def test_shift_calendar_honors_planned_stop_rows(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,60,0,60
Press-1,2026-06-01T07:00:00,2026-06-01T07:30:00,planned_stop,team meeting,0,0,60
Press-1,2026-06-01T07:30:00,2026-06-01T09:00:00,downtime,maintenance,0,0,60
"""
        calendar = read_shift_calendar(
            io.StringIO(
                """{
  "weekdays": ["monday"],
  "shifts": [{"name": "day", "start": "06:00", "end": "09:00"}]
}"""
            )
        )

        report = analyze_events(read_events(io.StringIO(csv_text)), calendar=calendar)
        asset = report.assets[0]

        self.assertEqual(asset.planned_seconds, 9000)
        self.assertEqual(asset.runtime_seconds, 3600)
        self.assertEqual(asset.downtime_seconds, 5400)
        self.assertNotIn("team meeting", asset.downtime_by_reason)

    def test_shift_calendar_adds_unclassified_gap_warning(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,60,0,60
Press-1,2026-06-01T07:50:00,2026-06-01T08:00:00,downtime,maintenance,0,0,60
"""
        calendar = read_shift_calendar(
            io.StringIO(
                """{
  "weekdays": ["monday"],
  "shifts": [{"name": "day", "start": "06:00", "end": "08:00"}]
}"""
            )
        )

        report = analyze_events(read_events(io.StringIO(csv_text)), calendar=calendar)
        asset = report.assets[0]

        self.assertEqual(asset.planned_seconds, 7200)
        self.assertEqual(asset.downtime_by_reason["maintenance"], 600)
        self.assertEqual(asset.downtime_by_reason["unclassified calendar gap"], 3000)
        self.assertIn("unclassified calendar gap", report.warnings[0])

    def test_reason_code_map_groups_aliases_and_warns_on_unmapped_reasons(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:15:00,downtime,Jam,0,0,4
Press-1,2026-06-01T06:15:00,2026-06-01T06:30:00,downtime,material_jam,0,0,4
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,operator check,0,0,4
Welder-2,2026-06-01T06:00:00,2026-06-01T06:20:00,idle,fixture wait,0,0,8
"""
        reason_map = read_reason_code_map(
            io.StringIO(
                """{
  "warn_unmapped": true,
  "categories": [
    {"canonical": "material jam", "aliases": ["jam", "material_jam", "material-jam"]},
    {"canonical": "waiting on fixtures", "aliases": ["fixture wait", "waiting fixtures"]}
  ]
}"""
            )
        )

        report = analyze_events(read_events(io.StringIO(csv_text)), reason_map=reason_map)

        press = next(asset for asset in report.assets if asset.asset == "Press-1")
        self.assertEqual(press.downtime_by_reason["material jam"], 1800)
        self.assertEqual(press.downtime_by_reason["operator check"], 900)
        self.assertNotIn("Jam", press.downtime_by_reason)
        self.assertTrue(
            any("Reason 'operator check' was not mapped" in warning for warning in report.warnings)
        )

        pareto = report.downtime_pareto
        self.assertEqual(pareto[0].reason, "material jam")
        self.assertIn("waiting on fixtures", [item.reason for item in pareto])

    def test_reason_code_map_rejects_conflicting_aliases(self) -> None:
        with self.assertRaisesRegex(ValueError, "maps to both"):
            read_reason_code_map(
                io.StringIO(
                    """{
  "categories": [
    {"canonical": "material jam", "aliases": ["jam"]},
    {"canonical": "quality hold", "aliases": ["jam"]}
  ]
}"""
                )
            )


if __name__ == "__main__":
    unittest.main()
