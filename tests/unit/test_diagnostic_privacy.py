"""Exercise the privacy boundary before storage and again before transport."""

import ast
from datetime import datetime, timedelta
from io import BytesIO
import json
import logging
from pathlib import Path
from zipfile import ZipFile, ZipInfo
from zoneinfo import ZoneInfo

import pytest

from common.oh_no_parent_control_ui import diagnostic_events as events
from common.oh_no_parent_control_ui.diagnostic_bundle import build_bundle, validate_bundle
from common.oh_no_parent_control_ui.errors import ErrorReport
from oh_no_parent_control.logs import DailyLogWriter, BrokerFileHandler
from oh_no_parent_control.grant_diagnostics import GrantDiagnostics
from tests.support.broker import make_broker

SECRET = "Child Name /home/private-user/private-file private@example.test secret-token"


class PrivateError(Exception):
    def __str__(self):
        raise AssertionError("Exception text must not be inspected")


def test_unknown_values_never_enter_a_logrecord(caplog):
    caplog.set_level(logging.INFO)
    logger = events.get_logger("parent")
    logger.info(SECRET)
    logger.info("parent.022", private=SECRET)
    logger.warning("parent.004", error_type=SECRET)
    for record in caplog.records:
        assert SECRET not in record.getMessage()
        assert not record.args
        assert not record.exc_info
        assert SECRET not in events.record_payload(record)
    assert events.error_code(PrivateError()) == "other"
    report = ErrorReport.capture("Parent App", PrivateError(), SECRET, SECRET)
    assert SECRET not in repr(report)
    assert "other" in report.message


@pytest.mark.parametrize("event_id,definition", list(events.CATALOG.items()))
def test_every_catalog_field_rejects_arbitrary_text(event_id, definition):
    def example(spec):
        return {"bool": False, "int": spec.get("min", 0), "number": 0,
                "enum": "other", "version": "1.2", "request": "e17d2f81-4a96-47cd-a0aa-1b4b871bdd72",
                "local-timestamp": "2026-09-11T16:16:21.123-07:00"}[spec["type"]]
    values = {key: example(spec) for key, spec in definition["fields"].items()}
    events.decode(events.encode(events.event(event_id, values)))
    assert events.describe(events.event(event_id, values)).isascii()
    with pytest.raises(ValueError):
        events.event(event_id, {**values, "private": SECRET})
    for key in values:
        with pytest.raises(ValueError):
            events.event(event_id, {**values, key: SECRET})


def test_foreign_logging_tracebacks_and_formatters_are_never_used(tmp_path):
    writer = DailyLogWriter(tmp_path)
    handler = BrokerFileHandler(writer)
    record = logging.LogRecord(SECRET, logging.ERROR, SECRET, 1, SECRET, (SECRET,),
                               (PrivateError, PrivateError(), None))
    handler.emit(record)
    bundle = writer.snapshot()
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        assert SECRET not in "".join(archive.read(name).decode() for name in archive.namelist())
        assert "Unclassified runtime log suppressed" in "".join(
            archive.read(name).decode() for name in archive.namelist() if name.endswith(".log"))


def test_bundle_rejects_extra_fields_text_and_raw_logs():
    valid = build_bundle([])
    with ZipFile(BytesIO(valid)) as archive:
        payload = {name: archive.read(name) for name in archive.namelist()}
    for name in ("report.txt", "manifest.json", "events.jsonl", "private.log"):
        changed = {**payload, name: SECRET.encode()}
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for member, data in changed.items():
                archive.writestr(member, data)
        with pytest.raises(ValueError):
            validate_bundle(output.getvalue())


@pytest.mark.parametrize("health", (["timer"], [], "timer", 1))
def test_manifest_rejects_non_mapping_health(health):
    with pytest.raises(ValueError):
        build_bundle([], health=health)


@pytest.mark.parametrize("value", (10**1000, float("inf"), float("nan"), True))
def test_numeric_validation_cannot_raise_unbounded_conversion_errors(value):
    with pytest.raises(ValueError):
        events._field({"type": "number", "min": 0, "max": 100}, value)


def test_zip_metadata_and_trailing_bytes_are_never_forwarded():
    clean = build_bundle([])
    with ZipFile(BytesIO(clean)) as archive:
        payload = {name: archive.read(name) for name in archive.namelist()}
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.comment = SECRET.encode()
        for name, data in payload.items():
            entry = ZipInfo(name, date_time=(2026, 9, 11, 20, 0, 44))
            entry.comment = SECRET.encode()
            entry.extra = b"\x99\x99" + len(SECRET).to_bytes(2, "little") + SECRET.encode()
            archive.writestr(entry, data)
    annotated = output.getvalue() + SECRET.encode()
    assert validate_bundle(annotated) == clean


def test_fault_locations_do_not_use_traceback_paths_or_unknown_modules(caplog):
    try:
        raise PrivateError(SECRET)
    except PrivateError as error:
        events.record_exception(error)
    record = events.decode(caplog.records[-1].onpc_payload)
    assert record["fields"] == {"error_type": "other", "source": "other", "line": 0}
    assert SECRET not in caplog.text


def test_noop_write_cannot_explain_a_later_external_change(caplog):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-11T16:16:21-07:00")
    grant = (int(now.timestamp()), 300)
    tracker.observe(1, grant, now, 0)
    tracker.wrote(1, grant)
    tracker.observe(1, grant, now, 0)
    tracker.observe(1, (0, 0), now, 0)
    tracker.observe(1, grant, now, 0)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["source"] == "external"


def test_clock_divergence_reports_direction_without_wall_time(caplog):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-11T16:16:21-07:00")
    tracker.observe(1, (0, 0), now, 10)
    tracker.observe(1, (0, 0), now + timedelta(seconds=301), 11)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"] == {
        "direction": "forward", "seconds": 300}
    assert str(int(now.timestamp())) not in caplog.text


def test_background_observation_does_not_lock_approvals_or_publish_stale_reads(monkeypatch, caplog):
    broker = make_broker()
    reads = []

    def read_grant(uid):
        reads.append(uid)
        # A real transaction can start and finish while diagnostics wait for
        # AccountsService. Its revision makes the old reply unusable.
        assert broker._acquire_request_lock()
        broker._request_lock.release()
        return (0, 0)

    monkeypatch.setattr(broker._accounts, "get_extension", read_grant)
    with caplog.at_level("INFO"):
        broker.observe_grants()
    assert reads
    assert not any('"grant.observed-timed"' in record.onpc_payload for record in caplog.records)


def test_background_observation_skips_an_active_transaction(monkeypatch):
    broker = make_broker()
    reads = []
    monkeypatch.setattr(broker._accounts, "list_users", lambda: reads.append(True) or [])
    assert broker._acquire_request_lock()
    try:
        broker.observe_grants()
    finally:
        broker._request_lock.release()
    assert not reads


def test_external_grant_and_verified_write_have_distinct_evidence(caplog):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-11T16:16:21-07:00")
    uid = 1098765
    tracker.observe(uid, (0, 0), now, 0)
    later = now + timedelta(seconds=8)
    until_midnight = 27811
    grant = (int(later.timestamp()), until_midnight)
    tracker.observe(uid, grant, later, 8)
    extension = (grant[0], grant[1] + 6)
    tracker.wrote(uid, extension)
    tracker.observe(uid, extension, later, 8)
    observed = [events.decode(record.onpc_payload) for record in caplog.records
                if record.onpc_payload and '"grant.observed-timed"' in record.onpc_payload]
    assert [record["fields"]["source"] for record in observed] == [
        "unknown", "external", "our-app"]
    assert observed[1]["fields"]["ends_at_midnight"] is True
    assert observed[2]["fields"]["remaining"] == 27817
    assert str(uid) not in caplog.text
    assert str(grant[0]) not in caplog.text
    assert observed[1]["fields"]["observed_at"] == later.astimezone().isoformat(timespec="milliseconds")


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("microsecond", [0, 349000, 999999])
def test_external_midnight_expiry_uses_absolute_seconds(caplog, offset, microsecond):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-12T12:48:10-07:00").replace(microsecond=microsecond)
    tracker.observe(1, (0, 0), now, 0)
    grant = (int(now.timestamp()), 40310 + offset)
    tracker.observe(1, grant, now, 0)
    tracker.observe(1, grant, now + timedelta(seconds=2), 2)
    records = [events.decode(record.onpc_payload) for record in caplog.records]
    assert records[-1]["fields"]["ends_at_midnight"] is (offset == 0)
    summaries = [record for record in records if record["event"] == "grant.external-rest-of-day"]
    assert len(summaries) == int(offset == 0)
    if summaries:
        assert summaries[0]["fields"]["remaining"] == 40310
        assert "click and authentication not observed" in events.describe(summaries[0])


@pytest.mark.parametrize("source", ["initial", "our-app", "uncertain"])
def test_midnight_grant_does_not_invent_external_approval(caplog, source):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-12T12:48:10.349-07:00")
    grant = (int(now.timestamp()), 40310)
    if source != "initial":
        tracker.observe(1, (0, 0), now, 0)
    if source == "our-app":
        tracker.wrote(1, grant)
    elif source == "uncertain":
        tracker.write_started(1)
    tracker.observe(1, grant, now, 0)
    assert not any('"grant.external-rest-of-day"' in record.onpc_payload for record in caplog.records)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["ends_at_midnight"] is True


@pytest.mark.parametrize("day,hours", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_midnight_observation_across_daylight_saving_transition(caplog, day, hours):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("America/Los_Angeles"), microsecond=349000)
    tracker.observe(1, (0, 0), now, 0)
    grant = (int(now.timestamp()), hours * 3600)
    tracker.observe(1, grant, now, 0)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["ends_at_midnight"] is True
    tracker.observe(1, (0, 0), now + timedelta(days=1), hours * 3600)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["ends_at_midnight"] is False


def test_ambiguous_write_never_becomes_external_and_verified_write_recovers(caplog):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-11T16:16:21-07:00")
    tracker.observe(1, (0, 0), now, 0)
    tracker.write_started(1)
    # The call timed out, but the service can still apply its write later.
    tracker.observe(1, (1, 300), now, 0)
    tracker.observe(1, (2, 300), now, 0)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["source"] == "unknown"
    tracker.wrote(1, (2, 300))
    tracker.observe(1, (2, 300), now, 0)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["source"] == "our-app"


def test_evicted_or_restarted_baseline_is_unknown(caplog):
    caplog.set_level(logging.INFO)
    tracker = GrantDiagnostics()
    now = datetime.fromisoformat("2026-09-11T16:16:21-07:00")
    for uid in range(129):
        tracker.observe(uid, (0, 0), now, 0)
    tracker.observe(0, (1, 300), now, 0)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["source"] == "unknown"
    assert len(tracker._observed) == 128


def test_broker_write_logs_our_app_only_after_readback(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    broker = make_broker()
    broker._write_extension(1001, (1, 300))
    fields = events.decode(caplog.records[-1].onpc_payload)["fields"]
    assert fields["source"] == "our-app"
    monkeypatch.setattr(broker._accounts, "get_extension", lambda uid: (2, 300))
    with pytest.raises(Exception, match="extension verification failed"):
        broker._write_extension(1001, (3, 300))
    broker._observe_grant(1001, 2, 300)
    assert events.decode(caplog.records[-1].onpc_payload)["fields"]["source"] == "unknown"


@pytest.mark.parametrize("value", [
    "2026-09-11T16:16:21.123", "2026-09-11T16:16:21.123Z",
    "2026-02-30T16:16:21.123-07:00", SECRET,
])
def test_local_timestamp_rejects_missing_offset_and_invalid_text(value):
    with pytest.raises(ValueError):
        events._field({"type": "local-timestamp"}, value)


def test_product_log_calls_use_catalog_events():
    root = Path(__file__).resolve().parents[2]
    files = []
    for directory in ("broker/oh_no_parent_control", "parent/oh_no_parent_control_parent",
                      "kiosk/oh_no_parent_control_kiosk", "common/oh_no_parent_control_ui"):
        files.extend((root / directory).glob("*.py"))
    checked = 0
    for path in files:
        if path.name == "diagnostic_events.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if (node.func.attr == "getLogger" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "logging"):
                # Root handlers are configured at process entry; named logger
                # creation belongs exclusively to the validating event API.
                assert not node.args and not node.keywords, path
            if node.func.attr not in {"debug", "info", "warning", "error", "critical", "exception"}:
                continue
            direct = (isinstance(node.func.value, ast.Call)
                      and isinstance(node.func.value.func, ast.Name)
                      and node.func.value.func.id == "get_logger")
            named = isinstance(node.func.value, ast.Name) and node.func.value.id in {"LOG", "logging"}
            if not direct and not named:
                continue
            assert direct or node.func.value.id == "LOG", path
            assert node.func.attr != "exception", path
            assert isinstance(node.args[0], ast.Constant), path
            definition = events.CATALOG[node.args[0].value]
            assert len(node.args) == 1, path
            assert {item.arg for item in node.keywords} == set(definition["fields"]), path
            checked += 1
    assert checked > 250
