from datetime import date, datetime, timezone
from io import BytesIO
from zipfile import ZipFile

import pytest

from oh_no_parent_control import diagnostics
from oh_no_parent_control.logs import DailyLogWriter
from common.oh_no_parent_control_ui.diagnostic_events import encode, event
from common.oh_no_parent_control_ui.diagnostic_bundle import validate_bundle
from common.oh_no_parent_control_ui.diagnostic_report import read_report


def test_packaged_diagnostic_modules_include_their_local_dependencies():
    """Source-tree imports must not conceal missing installed modules."""
    import ast
    from tests.support.paths import ROOT

    sources = next(line.split(":=", 1)[1].split()
                   for line in (ROOT / "Makefile").read_text().splitlines()
                   if line.startswith("COMMON_SOURCES :="))
    pending = ["diagnostics.py", "diagnostic_bundle.py"]
    checked = set()
    while pending:
        filename = pending.pop()
        if filename in checked:
            continue
        assert filename in sources, f"Diagnostic dependency missing from package: {filename}"
        checked.add(filename)
        tree = ast.parse((ROOT / "common/oh_no_parent_control_ui" / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                pending.append(node.module.split(".")[0] + ".py")


def test_export_includes_only_newest_three_dates_of_validated_events(tmp_path):
    for day in (10, 11, 15, 20, 21):
        writer = DailyLogWriter(tmp_path, now=lambda day=day: datetime(2026, 1, day))
        writer.write("parent", "INFO", encode(event("diagnostic.rejected", operation=day)))
    # Old files, including content that looks like an event, are never imported.
    (tmp_path / "parent" / "2026-01-21.log").write_text("private@example.test")
    bundle = diagnostics.collect_logs(tmp_path, date(2026, 1, 21))
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        logs, info = read_report(archive)
        assert set(logs) == {f"parent/2026-01-{day}.log" for day in (15, 20, 21)}
        records = [record for rows in logs.values() for record in rows]
        assert {record["operation"] for record in records} == {15, 20, 21}
        assert all(b"private@example.test" not in archive.read(name) for name in archive.namelist())


def test_export_orders_events_across_components_and_counts_corruption(tmp_path):
    writer = DailyLogWriter(tmp_path, now=lambda: datetime(2026, 1, 21))
    for index, component in enumerate(("parent", "broker", "child"), 1):
        writer.write(component, "INFO", encode(event("diagnostic.rejected", operation=index)))
    (tmp_path / "parent" / "2026-01-21.events.1").write_text("private@example.test\n")
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        logs, info = read_report(archive)
        records = sorted((record for rows in logs.values() for record in rows), key=lambda r: r["sequence"])
        assert [record["operation"] for record in records] == [1, 2, 3]
        assert info["counts"]["invalid"] == 1


def test_export_refuses_symlinks_without_reading_target(tmp_path):
    component = tmp_path / "parent"
    component.mkdir()
    (component / "2026-09-04.events").symlink_to(tmp_path / "private")
    with pytest.raises(OSError):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 4))


def test_empty_export_explains_missing_history(tmp_path):
    bundle = diagnostics.collect_logs(tmp_path, date(2026, 9, 4))
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        logs, info = read_report(archive)
        assert not logs
        assert info["counts"]["missing"] == 4
        assert {name for name in archive.namelist() if name.endswith("/")} == {
            "broker/", "parent/", "child/", "kiosk/"}


def test_export_rejects_hard_links(tmp_path):
    component = tmp_path / "kiosk"
    component.mkdir()
    source = tmp_path / "private"
    source.write_text("not a product log")
    (component / "2026-09-09.events").hardlink_to(source)
    with pytest.raises(ValueError, match="Unsupported diagnostic file"):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 9))


def test_trim_preserves_incident_context_before_routine_history(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "MAX_RECORDS", 3)
    writer = DailyLogWriter(tmp_path)
    writer.write("broker", "ERROR", encode(event("diagnostic.rejected", operation=1)))
    for index in range(2, 12):
        writer.write("broker", "INFO", encode(event("diagnostic.rejected", operation=index)))
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        logs, info = read_report(archive)
        records = [record for rows in logs.values() for record in rows]
        assert [record["operation"] for record in records] == [1, 10, 11]
        assert info["counts"]["truncated"] == 8


def test_export_selects_three_dates_independently_for_each_component(tmp_path):
    for component, days in (("broker", (18, 19, 20)), ("child", (2, 5, 9))):
        for day in days:
            writer = DailyLogWriter(tmp_path, now=lambda day=day: datetime(2026, 1, day))
            writer.write(component, "INFO", encode(event("diagnostic.rejected", operation=day)))
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        logs, _ = read_report(archive)
        assert set(logs) == {f"{component}/2026-01-{day:02}.log"
            for component, days in (("broker", (18, 19, 20)), ("child", (2, 5, 9))) for day in days}


def test_midnight_incident_does_not_move_retained_events_to_the_next_day(tmp_path):
    now = [datetime(2026, 1, 20, 23, 59, tzinfo=timezone.utc)]
    writer = DailyLogWriter(tmp_path, now=lambda: now[0])
    writer.write("broker", "INFO", encode(event("diagnostic.rejected", operation=1)))
    now[0] = datetime(2026, 1, 21, tzinfo=timezone.utc)
    writer.write("broker", "ERROR", encode(event("diagnostic.rejected", operation=2)))
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        logs, _ = read_report(archive)
        assert [r["operation"] for r in logs["broker/2026-01-20.log"]] == [1]
        assert [r["operation"] for r in logs["broker/2026-01-21.log"]] == [2]


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
