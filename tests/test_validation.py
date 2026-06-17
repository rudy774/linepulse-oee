from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from linepulse_oee.analyze import analyze_csv, read_events
from linepulse_oee.cli import main
from linepulse_oee.validation import render_validation_issues, validate_events


class ValidationTests(unittest.TestCase):
    def test_read_events_rejects_missing_required_columns_before_row_parsing(self) -> None:
        csv_text = """asset,start,end,reason
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,maintenance
"""
        with self.assertRaisesRegex(ValueError, "Missing required column"):
            read_events(io.StringIO(csv_text))

    def test_validate_events_detects_state_history_problems(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,100,0,4
Press-1,2026-06-01T06:45:00,2026-06-01T07:15:00,downtime,,0,0,4
Press-1,2026-06-01T06:45:00,2026-06-01T07:15:00,downtime,,0,0,4
Press-1,2026-06-01T07:30:00,2026-06-01T07:45:00,running,,0,0,4
"""
        issues = validate_events(read_events(io.StringIO(csv_text)))
        codes = {issue.code for issue in issues}

        self.assertIn("duplicate_interval", codes)
        self.assertIn("overlapping_intervals", codes)
        self.assertIn("timeline_gap", codes)
        self.assertIn("missing_reason", codes)
        self.assertIn("running_without_counts", codes)

    def test_analyze_csv_surfaces_validation_warnings(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T06:30:00,running,,0,0,4
Press-1,2026-06-01T06:30:00,2026-06-01T06:45:00,downtime,,0,0,4
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            path.write_text(csv_text, encoding="utf-8")

            report = analyze_csv(path)

        self.assertTrue(any("Data quality warning" in warning for warning in report.warnings))
        self.assertTrue(any("governed downtime reason" in warning for warning in report.warnings))

    def test_cli_validate_returns_nonzero_for_errors(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,100,0,4
Press-1,2026-06-01T06:30:00,2026-06-01T07:30:00,downtime,maintenance,0,0,4
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            path.write_text(csv_text, encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(["validate", str(path)])

        self.assertEqual(exit_code, 1)
        self.assertIn("overlapping_intervals", output.getvalue())

    def test_cli_validate_can_write_json(self) -> None:
        csv_text = """asset,start,end,state,reason,good_count,scrap_count,ideal_cycle_seconds
Press-1,2026-06-01T06:00:00,2026-06-01T07:00:00,running,,100,0,4
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            output_path = Path(tmp) / "validation.json"
            path.write_text(csv_text, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["validate", str(path), "--json", str(output_path)])

            payload = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn('"ok": true', payload)

    def test_render_validation_issues_has_empty_state(self) -> None:
        self.assertIn("Validation passed", render_validation_issues([]))


if __name__ == "__main__":
    unittest.main()
