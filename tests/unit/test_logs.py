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


def test_native_unlock_refusal_and_success_survive_storage_and_export(tmp_path):
    from common.oh_no_parent_control_ui.diagnostic_events import decode
    from common.oh_no_parent_control_ui.diagnostic_report import read_report

    fields = dict(reason="unlock-request", attempt=1, native_state="limit-reached",
                  native_should_lock=True, limit_enabled=True, session_available=True,
                  session_active=False, session_idle=True, session_locked=True,
                  locked=True, greeter=False, native_remaining=0, elapsed_ms=0)
    observations = [fields, dict(fields, reason="unlock-settled", native_state="active",
                                native_should_lock=False, session_active=True,
                                session_idle=False, native_remaining=289, elapsed_ms=1000),
                    dict(fields, attempt=2),
                    dict(fields, reason="unlock-settled", attempt=2, native_state="active",
                         native_should_lock=False, session_active=True, session_idle=False,
                         session_locked=False, locked=False, native_remaining=282, elapsed_ms=1000)]
    writer = DailyLogWriter(tmp_path)
    for observation in observations:
        payload = encode(event("child.session-state", observation))
        assert decode(payload, component="child")["fields"] == observation
        writer.write("child", "INFO", payload, source_uid=1098765)
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        logs, _ = read_report(archive)
        retained = [row for rows in logs.values() for row in rows]
        assert [row["fields"] for row in retained] == observations
        text = "".join(archive.read(name).decode() for name in archive.namelist())
        assert "1098765" not in text
        assert "an unlock request is not a successful unlock" in text
    assert writer.summary()["suppressed"] == 0


def test_unlock_continuation_decisions_survive_storage_and_export(tmp_path):
    from common.oh_no_parent_control_ui.diagnostic_report import read_report

    initial = dict(stage="armed", reason="native-lock", attempt=1, elapsed_ms=0,
                   native_should_lock=True, locked=True, session_active=False,
                   native_remaining=0)
    observations = [initial,
                    dict(initial, stage="retry", reason="none", elapsed_ms=120,
                         native_should_lock=False, session_active=True, native_remaining=290),
                    dict(initial, stage="unlocked", reason="none", elapsed_ms=380,
                         native_should_lock=False, session_active=True, locked=False,
                         native_remaining=290)]
    writer = DailyLogWriter(tmp_path)
    for observation in observations:
        writer.write("child", "INFO", encode(event("child.unlock-recovery", observation)))
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        logs, _ = read_report(archive)
        retained = [row for rows in logs.values() for row in rows]
        assert [row["fields"] for row in retained] == observations


def test_child_failure_and_frontend_transport_provenance_survive_customer_export(tmp_path):
    from common.oh_no_parent_control_ui.diagnostic_report import read_report

    observations = [
        ("child", "WARNING", "child.resume-refresh-deferred", dict(
            stage="query-usage", category="busy")),
        ("broker", "WARNING", "adapters.usage-query-failed", dict(category="busy")),
        ("child", "WARNING", "child.resume-refresh-failed", dict(
            stage="record-usage", category="timeout", active=True, limit_enabled=True,
            failures=1, retry=False, delay_ms=0)),
        ("child", "ERROR", "child.failure", dict(
            operation="resume-refresh", error_type="GLib.Error", category="timeout")),
        ("parent", "ERROR", "runtime.failure-gio", dict(depth=1, category="reboot-required")),
        ("kiosk", "WARNING", "kiosk.agent-preparation-failed", dict(stage="restart-reply")),
    ]
    writer = DailyLogWriter(tmp_path)
    for component, level, name, fields in observations:
        writer.write(component, level, encode(event(name, fields)),
                     source_uid=None if component == "broker" else 1098765)
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        logs, _ = read_report(archive)
        retained = {row["event"]: row["fields"] for rows in logs.values() for row in rows}
        assert retained == {name: fields for _, _, name, fields in observations}
        text = "".join(archive.read(name).decode() for name in archive.namelist())
        assert "1098765" not in text
        assert "placeholder RuntimeError" in text
        assert "active native countdown retained, no error report or late usage replay" in text


@pytest.mark.parametrize('component,name,fields', [
    ('child', 'child.failure', dict(operation='unlock-dispatch', error_type='TypeError', category='other')),
    ('kiosk', 'kiosk.logout-fallback', dict(stage='response-reply', outcome='failed', requested=True)),
    ('child', 'kiosk-selection-store.failure', dict(
        stage='replace', error_type='PermissionError', os_error='read-only')),
])
def test_native_recovery_and_local_fallback_evidence_survives_customer_export(
        tmp_path, component, name, fields):
    from common.oh_no_parent_control_ui.diagnostic_report import read_report

    writer = DailyLogWriter(tmp_path)
    writer.write(component, 'ERROR', encode(event(name, fields)), source_uid=1098765)
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        logs, _ = read_report(archive)
        retained = [row for rows in logs.values() for row in rows]
        assert [(row['event'], row['fields']) for row in retained] == [(name, fields)]
        text = ''.join(archive.read(path).decode() for path in archive.namelist())
        assert '1098765' not in text
    for key in fields:
        with pytest.raises(ValueError):
            event(name, dict(fields, **{key: 'PRIVATE /home/private'}))
    with pytest.raises(ValueError):
        event(name, dict(fields, message='PRIVATE'))


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
