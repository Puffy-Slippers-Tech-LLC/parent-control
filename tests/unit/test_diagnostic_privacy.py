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
from oh_no_parent_control.extension_manager import _stderr_reason, ExtensionManager
from oh_no_parent_control.adapters import AccountsService
from oh_no_parent_control.service import Service, BUS_NAME
from gi.repository import GLib
from types import SimpleNamespace
from unittest.mock import Mock
from tests.support.broker import make_broker

SECRET = "Child Name /home/private-user/private-file private@example.test secret-token"


class PrivateError(Exception):
    def __str__(self):
        raise AssertionError("Exception text must not be inspected")


def test_pending_reboot_cause_survives_customer_export_without_machine_identity(tmp_path, caplog):
    writer = DailyLogWriter(tmp_path)
    handler = BrokerFileHandler(writer)
    with caplog.at_level('WARNING'):
        events.get_logger('service').warning('service.diagnostics-only')
    for record in caplog.records:
        handler.emit(record)
    data = writer.snapshot()
    validate_bundle(data)
    with ZipFile(BytesIO(data)) as archive:
        report = ''.join(archive.read(name).decode() for name in archive.namelist())
    assert 'product installation or upgrade requires reboot' in report
    assert 'only diagnostics and kiosk presentation reads are available' in report
    assert 'diagnostic.rejected' not in report
    with pytest.raises(ValueError):
        events.event('service.diagnostics-only', {'private': SECRET})


@pytest.mark.parametrize("marker,reason", [
    ("failed to commit changes to dconf: org.freedesktop.DBus.Error.ServiceUnknown", "dconf-service-missing"),
    ("failed to commit changes to dconf: org.freedesktop.DBus.Error.Spawn.ExecFailed", "dconf-service-start-failed"),
    ("failed to commit changes to dconf: Permission denied", "dconf-access-denied"),
    ("failed to commit changes to dconf: Read-only file system", "dconf-read-only"),
    ("failed to commit changes to dconf:", "dconf-commit-failed"),
    ("Using the 'memory' GSettings backend", "settings-memory-backend"),
    ("The key is not writable", "settings-not-writable"),
    ("No such schema", "settings-schema-missing"),
    ("dconf will not work properly", "dconf-runtime-unavailable"),
    ("dbus-daemon[987654]: Failed to start message bus: Cannot acquire AVC netlink fd: "
     "Address family not supported by protocol\n"
     "dbus-run-session: dbus-daemon exited with code 1\n"
     "failed to commit changes to dconf: Could not connect: No such file or directory", "dconf-commit-failed"),
    ("dbus-run-session: dbus-daemon exited with code 1", "other"),
    ("", "other"),
])
def test_gnome_warning_projection_never_exports_stderr(tmp_path, caplog, marker, reason):
    raw = marker + " " + SECRET
    assert _stderr_reason(raw) == reason
    assert _stderr_reason(None) is None
    assert _stderr_reason(" \n") is None
    writer = DailyLogWriter(tmp_path)
    handler = BrokerFileHandler(writer)
    with caplog.at_level("INFO"):
        ExtensionManager._log_stderr(raw, "set", "offline", {
            "tool": "gsettings", "key": "enabled-extensions"})
    for record in caplog.records:
        assert SECRET not in record.getMessage()
        assert SECRET not in events.record_payload(record)
        handler.emit(record)
    bundle = writer.snapshot()
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        exported = "".join(archive.read(name).decode() for name in archive.namelist())
    assert SECRET not in exported
    assert "reason=" + reason in exported
    assert "987654" not in exported
    if "dbus-run-session: dbus-daemon exited with code" in marker:
        cause = ("selinux-netlink-family-unavailable" if "Cannot acquire AVC netlink fd" in marker
                 else "startup-failed")
        assert "session bus startup failed" in exported
        assert "reason=" + cause in exported
    else:
        assert "session bus startup failed" not in exported


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


@pytest.mark.parametrize("stage", ["find-user", "get-all"])
@pytest.mark.parametrize("greeter", [False, True])
def test_account_identity_mismatch_is_diagnosable_without_private_data(
        tmp_path, monkeypatch, caplog, stage, greeter):
    """A bad ordinary NSS candidate must still abort both public list methods."""
    accounts = AccountsService(object())
    candidate_uid = 60577
    monkeypatch.setattr("oh_no_parent_control.adapters.pwd.getpwall", lambda: [
        SimpleNamespace(pw_uid=candidate_uid, pw_shell="/bin/bash",
                        pw_name="gdm-greeter" if greeter else SECRET,
                        pw_dir=SECRET, pw_gecos=SECRET)])

    def call(_connection, _name, _path, _interface, method, *_args, **_kwargs):
        if method == "FindUserById":
            # Return the wrong object in the first variant, or contradictory
            # UID metadata in the second. Neither identity may enter logs.
            return GLib.Variant("(o)", (
                "/org/freedesktop/Accounts/User42" if stage == "find-user"
                else "/org/freedesktop/Accounts/User60577",))
        assert method == "GetAll"
        return GLib.Variant("(a{sv})", ({
            "Uid": GLib.Variant("t", 61234),
            "UserName": GLib.Variant("s", "gdm-greeter" if greeter else SECRET),
            "RealName": GLib.Variant("s", SECRET),
            "IconFile": GLib.Variant("s", SECRET),
        },))

    monkeypatch.setattr("oh_no_parent_control.adapters._call", call)
    service = Service.__new__(Service)
    service.credentials = SimpleNamespace(uid=lambda _sender: 0)
    service.broker = SimpleNamespace(
        list_managed_users=lambda _uid: accounts.list_users(),
        list_approvers=lambda _uid: accounts.list_users())
    caplog.set_level(logging.INFO)
    for method in ("ListManagedUsers", "ListApprovers"):
        invocation = Mock()
        service._method_call(None, SECRET, None, None, method, None, invocation)
        invocation.return_value.assert_not_called()
        invocation.return_dbus_error.assert_called_once_with(
            BUS_NAME + ".Error.Failed", "service failure")

    decoded = [events.decode(record.onpc_payload) for record in caplog.records]
    mismatches = [e for e in decoded if e["event"] == "adapters.account-object-mismatch"]
    assert [e["fields"] for e in mismatches] == [{"stage": stage}] * 2
    contexts = [e for e in decoded if e["event"] == "adapters.account-object-context"]
    if stage == "find-user":
        assert [e["fields"] for e in contexts] == [{
            "object_shape": "uid-path", "requested_uid_match": "mismatch",
            "object_uid_match": "mismatch",
            "account_role": "display-manager-greeter" if greeter else "other"}] * 2
    else:
        assert contexts == []
    failures = [e for e in decoded if e["event"] == "adapters.account-enumeration-failed"]
    assert [e["fields"] for e in failures] == [{
        "stage": "account-lookup", "error_type": "RuntimeError",
        "candidate": "display-manager-greeter" if greeter else "other"}] * 2
    faults = [e for e in decoded if e["event"] == "runtime.fault"]
    assert all(e["fields"]["source"] == "adapters" and e["fields"]["line"] > 0
               for e in faults)
    assert len(faults) == 2
    # Each failure shares its dispatch operation, without a person/session key.
    for method in ("ListManagedUsers", "ListApprovers"):
        dispatch = next(e for e in decoded if e["event"] == "service.006"
                        and e["fields"]["method"] == method)
        grouped = [e["event"] for e in decoded if e["operation"] == dispatch["operation"]]
        assert "adapters.account-object-mismatch" in grouped
        assert "adapters.account-enumeration-failed" in grouped
        assert "runtime.fault" in grouped

    writer = DailyLogWriter(tmp_path)
    handler = BrokerFileHandler(writer)
    for record in caplog.records:
        handler.emit(record)
    bundle = writer.snapshot()
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        exported = "".join(archive.read(name).decode() for name in archive.namelist())
    assert "object-path-uid-mismatch" in exported
    assert "stage=" + stage in exported
    expected_candidate = "display-manager-greeter" if greeter else "other"
    assert "candidate=" + expected_candidate in exported
    for private in (SECRET, "60577", "61234", "User42", "gdm-greeter"):
        assert private not in exported
        assert private not in caplog.text


@pytest.mark.parametrize("stage", ["nss", "account-lookup"])
def test_account_enumeration_never_formats_errors(monkeypatch, caplog, stage):
    accounts = AccountsService(object())

    def fail(*_args):
        raise PrivateError(SECRET)

    monkeypatch.setattr("oh_no_parent_control.adapters.pwd.getpwall", fail if stage == "nss"
                        else lambda: [SimpleNamespace(pw_uid=1001, pw_shell="/bin/bash",
                                                      pw_name=SECRET)])
    monkeypatch.setattr(accounts, "get_user", fail)
    with pytest.raises(PrivateError):
        accounts.list_users()
    value = events.decode(caplog.records[-1].onpc_payload)
    assert value["fields"] == {"stage": stage, "candidate": "other", "error_type": "other"}
    assert SECRET not in caplog.text


def test_deleted_account_remains_skipped_with_safe_evidence(monkeypatch, caplog):
    accounts = AccountsService(object())
    monkeypatch.setattr("oh_no_parent_control.adapters.pwd.getpwall", lambda: [
        SimpleNamespace(pw_uid=1001, pw_shell="/bin/bash", pw_name=SECRET)])

    def deleted(_uid):
        raise GLib.Error(SECRET)

    monkeypatch.setattr(accounts, "get_user", deleted)
    assert accounts.list_users() == ()
    value = events.decode(caplog.records[-1].onpc_payload)
    assert value["event"] == "adapters.account-enumeration-skipped"
    assert value["fields"] == {"candidate": "other", "error_type": "Error"}
    assert SECRET not in caplog.text


def test_greeter_exclusion_exports_role_only(tmp_path, monkeypatch, caplog):
    accounts = AccountsService(object())
    monkeypatch.setattr("oh_no_parent_control.adapters.pwd.getpwall", lambda: [
        SimpleNamespace(pw_uid=60578, pw_shell="/bin/bash", pw_name=SECRET,
                        pw_dir=SECRET, pw_gecos=SECRET)])
    lookup = Mock(side_effect=AssertionError("Greeter lookup must not be reached"))
    monkeypatch.setattr(accounts, "get_user", lookup)
    caplog.set_level(logging.INFO)
    assert accounts.list_users() == ()
    lookup.assert_not_called()
    decoded = [events.decode(record.onpc_payload) for record in caplog.records]
    assert [(value["event"], value["fields"]) for value in decoded] == [
        ("adapters.greeter-candidates-excluded", {})]
    writer = DailyLogWriter(tmp_path)
    handler = BrokerFileHandler(writer)
    for record in caplog.records:
        handler.emit(record)
    bundle = writer.snapshot()
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        exported = "".join(archive.read(name).decode() for name in archive.namelist())
    assert "reserved greeter UID range" in exported
    for private in (SECRET, "60578", "gdm-greeter"):
        assert private not in exported
        assert private not in caplog.text


@pytest.mark.parametrize("reply", [None, {}, {"Uid": "private"}, {"Uid": -1}])
def test_rejected_account_context_is_bounded_and_unknown_on_read_failure(
        monkeypatch, caplog, reply):
    accounts = AccountsService(object())
    calls = []

    def call(*_args, **kwargs):
        calls.append(kwargs)
        if reply is None:
            raise PrivateError(SECRET)
        return SimpleNamespace(unpack=lambda: (reply,))

    monkeypatch.setattr("oh_no_parent_control.adapters._call", call)
    accounts._log_account_object_context(1001, "/org/freedesktop/Accounts/private")
    assert calls == [{"timeout": 1000}]
    value = events.decode(caplog.records[-1].onpc_payload)
    assert value["fields"] == {
        "object_shape": "other", "requested_uid_match": "unknown",
        "object_uid_match": "unknown", "account_role": "unknown"}
    assert SECRET not in caplog.text


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
