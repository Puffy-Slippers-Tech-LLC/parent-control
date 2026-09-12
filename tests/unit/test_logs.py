from datetime import datetime, timedelta
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from oh_no_parent_control.logs import DailyLogWriter
from common.oh_no_parent_control_ui.diagnostic_events import encode, event


def payload(operation=0):
    return encode(event("diagnostic.rejected", operation=operation))


def test_component_records_have_utc_times_and_no_caller_identity(tmp_path):
    now = datetime.fromisoformat("2026-08-31T09:15:00-07:00")
    writer = DailyLogWriter(tmp_path, now=lambda: now, monotonic=lambda: 10)
    writer.write("parent", "INFO", payload(), source_uid=1098765)
    record = json.loads((tmp_path / "parent" / "2026-08-31.events").read_text())
    assert record["component"] == "parent"
    assert record["elapsed_ms"] == 0
    assert record["timestamp"] == "2026-08-31T16:15:00.000Z"
    assert record["sequence"] == 1
    assert "1098765" not in json.dumps(record)
    assert "09:15" not in json.dumps(record)
    assert "uid" not in record


def test_utc_midnight_storage_export_and_clock_adjustment(tmp_path):
    wall = [datetime.fromisoformat("2026-08-31T23:59:59.123456-07:00")]
    ticks = [10]
    writer = DailyLogWriter(tmp_path, now=lambda: wall[0], monotonic=lambda: ticks[0])
    writer.write("parent", "INFO", payload(1))
    wall[0] -= timedelta(seconds=5)
    ticks[0] += 2
    writer.write("parent", "ERROR", payload(2))
    records = [json.loads(line) for line in
               (tmp_path / "parent" / "2026-09-01.events").read_text().splitlines()]
    assert [row["timestamp"] for row in records] == [
        "2026-09-01T06:59:59.123Z", "2026-09-01T06:59:54.123Z"]
    assert [row["elapsed_ms"] for row in records] == [0, 2000]
    assert (tmp_path / "parent" / "2026-09-01.incident.events").exists()
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        text = archive.read("parent/2026-09-01.log").decode()
    assert "[INFO] 2026-09-01T06:59:59.123Z segment=" in text
    assert "[ERROR] 2026-09-01T06:59:54.123Z segment=" in text


def test_history_retains_three_dates_without_touching_old_text_logs(tmp_path):
    day = [datetime(2026, 8, 20)]
    writer = DailyLogWriter(tmp_path, now=lambda: day[0])
    old = tmp_path / "kiosk" / "2020-01-01.log"
    old.write_text("old private text")
    for index in range(12):
        day[0] = datetime(2026, 8, 20) + timedelta(days=index)
        writer.write("kiosk", "INFO", payload(index))
    assert len(list((tmp_path / "kiosk").glob("*.events"))) == 3
    assert old.read_text() == "old private text"


def test_duplicates_are_counted_and_error_context_survives_rotation(tmp_path, monkeypatch):
    from oh_no_parent_control import logs
    monkeypatch.setattr(logs, "MAX_FILE_BYTES", 600)
    writer = DailyLogWriter(tmp_path)
    writer.write("broker", "ERROR", payload(1))
    writer.write("broker", "ERROR", payload(1))
    for index in range(2, 30):
        writer.write("broker", "INFO", payload(index))
    assert writer.summary()["suppressed"] == 1
    assert writer.summary()["rotations"] > 0
    incident = next((tmp_path / "broker").glob("*.incident.events"))
    assert json.loads(incident.read_text().splitlines()[-1])["operation"] == 1
    assert len(list((tmp_path / "broker").iterdir())) <= 4


def test_unattributed_increase_pins_history_without_an_exception(tmp_path):
    writer = DailyLogWriter(tmp_path)
    for source in ("initial", "broker-write-verified", "unattributed"):
        writer.write("broker", "INFO", encode(event("grant.observed", {
            "source": source, "previous_known": source != "initial",
            "previous": 0, "remaining": 27811, "ends_at_midnight": True,
        })))
    assert writer.summary()["incidents"] == 1
    incident = next((tmp_path / "broker").glob("*.incident.events"))
    assert len(incident.read_text().splitlines()) == 3


def test_timed_external_change_survives_storage_and_export(tmp_path):
    writer = DailyLogWriter(tmp_path)
    timestamp = "2026-09-11T16:16:21.123-07:00"
    writer.write("broker", "INFO", encode(event("grant.observed-timed", {
        "observed_at": timestamp, "source": "external", "previous_known": True,
        "previous": 0, "remaining": 27811, "ends_at_midnight": True,
    })))
    assert writer.summary()["incidents"] == 1
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        text = "".join(archive.read(name).decode() for name in archive.namelist() if name.endswith(".log"))
        assert timestamp in text
        assert "source=external" in text


@pytest.mark.parametrize("component,level,message", [
    ("unknown", "INFO", payload()), ("child", "NOTICE", payload()),
    ("child", "INFO", ""), ("child", "INFO", "private@example.test"),
    ("child", "INFO", "x" * 4097),
    ("child", "INFO", encode(event("service.022"))),
])
def test_rejects_untrusted_record_fields(tmp_path, component, level, message):
    writer = DailyLogWriter(tmp_path)
    with pytest.raises(ValueError):
        writer.write(component, level, message, source_uid=1001)
    assert not any(tmp_path.rglob("*.events"))


@pytest.mark.parametrize("component", (None, "parent"))
def test_writer_refuses_linked_directories(tmp_path, component):
    private = tmp_path / "private"
    private.mkdir()
    root = tmp_path / "logs"
    if component is None:
        root.symlink_to(private, target_is_directory=True)
    else:
        root.mkdir()
        (root / component).symlink_to(private, target_is_directory=True)
    with pytest.raises(OSError):
        DailyLogWriter(root)
    assert not list(private.iterdir())
