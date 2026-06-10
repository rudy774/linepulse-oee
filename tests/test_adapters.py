from __future__ import annotations

import io
import unittest

from linepulse_oee.adapters import convert_csv, write_canonical_csv
from linepulse_oee.analyze import analyze_events, read_events


def _canonical_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    write_canonical_csv(rows, buffer)
    return buffer.getvalue()


class AdapterTests(unittest.TestCase):
    def test_ignition_historian_adapter_outputs_analyzable_events(self) -> None:
        source = """equipment_path,start_ts,end_ts,state_code,downtime_reason,good_parts,scrap_parts,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,RUNNING,,350,3,4.5
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,FAULT,material jam,0,0,4.5
"""
        rows = convert_csv(io.StringIO(source), "ignition-historian")

        self.assertEqual(rows[0]["state"], "running")
        self.assertEqual(rows[1]["state"], "downtime")
        self.assertEqual(rows[1]["reason"], "material jam")

        report = analyze_events(read_events(io.StringIO(_canonical_csv(rows))))
        asset = report.assets[0]
        self.assertEqual(asset.asset, "Press-1")
        self.assertEqual(asset.runtime_seconds, 1800)
        self.assertEqual(asset.downtime_by_reason["material jam"], 900)

    def test_mes_production_log_adapter_maps_event_types(self) -> None:
        source = """work_center,started_at,finished_at,event_type,reason_code,good_qty,reject_qty,target_cycle_seconds
Cell-A,2026-06-01T07:00:00,2026-06-01T07:20:00,PRODUCTION_RUN,,120,2,7.2
Cell-A,2026-06-01T07:20:00,2026-06-01T07:35:00,CHANGEOVER,model change,0,0,7.2
"""
        rows = convert_csv(io.StringIO(source), "mes-production-log")

        self.assertEqual(rows[0]["asset"], "Cell-A")
        self.assertEqual(rows[0]["state"], "running")
        self.assertEqual(rows[0]["scrap_count"], "2")
        self.assertEqual(rows[1]["state"], "changeover")

    def test_manual_downtime_adapter_uses_planned_flag(self) -> None:
        source = """asset,down_start,down_end,reason,planned,ideal_cycle_seconds
Press-1,2026-06-01T08:00:00,2026-06-01T08:15:00,team meeting,yes,4.5
Press-1,2026-06-01T08:15:00,2026-06-01T08:30:00,material jam,no,4.5
"""
        rows = convert_csv(io.StringIO(source), "manual-downtime-log")

        self.assertEqual(rows[0]["state"], "planned_stop")
        self.assertEqual(rows[1]["state"], "downtime")
        self.assertEqual(rows[1]["good_count"], "0")

    def test_rejects_unknown_adapter(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown adapter"):
            convert_csv(io.StringIO("asset,start,end\n"), "spreadsheet-of-mystery")

    def test_reports_missing_required_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required column"):
            convert_csv(io.StringIO("asset,start,end\n"), "manual-downtime-log")


if __name__ == "__main__":
    unittest.main()
