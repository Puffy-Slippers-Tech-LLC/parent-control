import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from oh_no_parent_control.logs import DailyLogWriter


class DailyLogWriterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.now = datetime(2026, 8, 31, 9, 15, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.writer = DailyLogWriter(self.root, now=lambda: self.now)

    def tearDown(self):
        self.temporary.cleanup()

    def test_writes_separate_component_daily_files(self):
        self.writer.write("parent", "INFO", "started", source_uid=1003)
        self.writer.write("child", "WARNING", "line one\nline two", source_uid=1001)

        parent = (self.root / "parent" / "2026-08-31.log").read_text()
        child = (self.root / "child" / "2026-08-31.log").read_text()
        self.assertIn("INFO uid=1003 started", parent)
        self.assertIn(r"WARNING uid=1001 line one\nline two", child)

    def test_new_daily_file_prunes_to_ten_days(self):
        directory = self.root / "kiosk"
        for day in range(20, 31):
            (directory / f"2026-08-{day:02d}.log").write_text("old\n")

        self.writer.write("kiosk", "INFO", "today", source_uid=991)

        logs = sorted(path.name for path in directory.glob("*.log"))
        self.assertEqual(len(logs), 10)
        self.assertEqual(logs[0], "2026-08-22.log")
        self.assertEqual(logs[-1], "2026-08-31.log")

    def test_cleanup_runs_only_when_todays_file_is_created(self):
        self.writer.write("broker", "INFO", "first")
        stale = self.root / "broker" / "2020-01-01.log"
        stale.write_text("stale\n")

        self.writer.write("broker", "INFO", "second")

        self.assertTrue(stale.exists())

    def test_rejects_untrusted_record_fields(self):
        for component, level, message in (
            ("unknown", "INFO", "message"),
            ("child", "NOTICE", "message"),
            ("child", "INFO", ""),
            ("child", "INFO", "x" * 4097),
        ):
            with self.subTest(component=component, level=level):
                with self.assertRaises(ValueError):
                    self.writer.write(component, level, message, source_uid=1001)
