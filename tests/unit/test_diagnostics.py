from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pytest

from oh_no_parent_control import diagnostics


def test_export_contains_three_newest_available_log_dates_in_newest_first_order(tmp_path):
    component = tmp_path / "parent"
    component.mkdir()
    for day in (10, 11, 15, 20, 21):
        (component / f"2026-01-{day:02}.log").write_text(f"event {day}")
    (component / "other.txt").write_text("excluded")
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        assert archive.namelist() == [
            f"parent/2026-01-{day:02}.log" for day in (21, 20, 15)
        ]
        assert archive.read("parent/2026-01-21.log") == b"event 21"


def test_export_orders_component_logs_by_date_before_component(tmp_path):
    for component in ("broker", "parent"):
        directory = tmp_path / component
        directory.mkdir()
        for day in (20, 21):
            (directory / f"2026-01-{day:02}.log").write_text(component)

    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        assert archive.namelist() == [
            "broker/2026-01-21.log", "parent/2026-01-21.log",
            "broker/2026-01-20.log", "parent/2026-01-20.log",
        ]


def test_export_rejects_symlinks_and_oversized_logs(tmp_path, monkeypatch):
    component = tmp_path / "parent"
    component.mkdir()
    log = component / "2026-09-04.log"
    log.symlink_to(tmp_path / "private")
    with pytest.raises(OSError):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 4))
    log.unlink()
    log.write_text("12345")
    monkeypatch.setattr(diagnostics, "MAX_BYTES", 4)
    with pytest.raises(ValueError, match="limit"):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 4))


def test_export_reports_no_logs(tmp_path):
    with pytest.raises(ValueError, match="No recent logs"):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 4))


def test_export_rejects_hard_links(tmp_path):
    component = tmp_path / "kiosk"
    component.mkdir()
    source = tmp_path / "private"
    source.write_text("not a product log")
    (component / "2026-09-09.log").hardlink_to(source)
    with pytest.raises(ValueError, match="Unsupported log file"):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 9))


def test_download_saves_exact_archive_privately(tmp_path):
    from types import SimpleNamespace
    from gi.repository import Gio, GLib
    from common.oh_no_parent_control_ui.feedback import FeedbackDialog

    path = tmp_path / "download.zip"
    loop = GLib.MainLoop()
    messages = []
    dialog = SimpleNamespace()

    def done(message):
        messages.append(message)
        loop.quit()

    dialog._download_done = done
    dialog._download_saved = lambda *args: FeedbackDialog._download_saved(dialog, *args)
    chooser = SimpleNamespace(save_finish=lambda _: Gio.File.new_for_path(str(path)))
    FeedbackDialog._download_selected(dialog, chooser, None, b"archive contents")
    timeout = GLib.timeout_add_seconds(5, lambda: (loop.quit(), False)[1])
    try:
        loop.run()
    finally:
        GLib.source_remove(timeout)
    assert messages == ["Downloaded · Ready to examine"]
    assert path.read_bytes() == b"archive contents"
    assert path.stat().st_mode & 0o777 == 0o600
