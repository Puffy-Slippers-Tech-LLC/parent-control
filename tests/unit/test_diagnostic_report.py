"""Readable exports preserve evidence without admitting arbitrary log prose."""

from io import BytesIO
import json
from zipfile import ZipFile, ZipInfo

import pytest

from common.oh_no_parent_control_ui.diagnostic_bundle import build_bundle, validate_bundle, with_system_info
from common.oh_no_parent_control_ui.diagnostic_events import event
from common.oh_no_parent_control_ui.diagnostic_report import build_report, read_report
from tests.support.system_info import sample_info

SECRET = "private-person@example.test"
LOG_NAME = "broker/2026-09-12.log"


def record():
    return {**event("diagnostic.rejected"), "component": "broker", "level": "INFO",
            "sequence": 1, "segment": 1, "elapsed_ms": 100}


def report():
    return build_report({LOG_NAME: [record()]}, system_info=sample_info())


def rewrite(data, change):
    with ZipFile(BytesIO(data)) as archive:
        payload = {name: archive.read(name) for name in archive.namelist()}
    change(payload)
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, value in payload.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_dated_report_roundtrip_enrichment_and_fixed_metadata():
    data = report()
    assert validate_bundle(data) == data
    assert with_system_info(data, sample_info()) == data
    with ZipFile(BytesIO(data)) as archive:
        assert archive.namelist() == ["system-info.json", "broker/", "child/", "kiosk/", "parent/", LOG_NAME]
        logs, info = read_report(archive)
        assert logs == {LOG_NAME: [record()]}
        assert info["logs"] == {LOG_NAME: 1}
        assert all(entry.date_time == (1980, 1, 1, 0, 0, 0) for entry in archive.infolist())


def test_utc_and_older_records_roundtrip_together():
    current = {**record(), "timestamp": "2026-09-12T18:42:03.337Z"}
    logs = {LOG_NAME: [record(), current]}
    data = build_report(logs, system_info=sample_info())
    assert validate_bundle(data) == data
    assert with_system_info(data, sample_info()) == data
    with ZipFile(BytesIO(data)) as archive:
        assert read_report(archive)[0] == logs
        assert b"[INFO] 2026-09-12T18:42:03.337Z segment=" in archive.read(LOG_NAME)


@pytest.mark.parametrize("timestamp", [
    None, 123, "private@example.test", "2026-09-12T18:42:03.337+00:00",
    "2026-09-12T18:42:03.337", "2026-02-30T18:42:03.337Z",
    "2026-09-12T25:42:03.337Z", "2026-09-12 18:42:03.337Z",
    "2026-09-12T18:42:03.337Z\n",
])
def test_timestamp_is_strict_utc_calendar_time(timestamp):
    with pytest.raises(ValueError):
        build_report({LOG_NAME: [{**record(), "timestamp": timestamp}]})


@pytest.mark.parametrize("name", [
    "../2026-09-12.log", "broker/../../private.log", "private/2026-09-12.log",
    "broker/2026-02-30.log", "broker/20260912.log", "broker/2026-09-12.log/private",
    "broker/2026-09-12.log\n", "broker/2026-09-12.events",
])
def test_builder_and_reader_reject_unapproved_paths(name):
    with pytest.raises(ValueError):
        build_report({name: [record()]})

    def change(payload):
        payload[name] = payload.pop(LOG_NAME)
        info = json.loads(payload["system-info.json"])
        info["logs"] = {name: 1}
        payload["system-info.json"] = json.dumps(info).encode()
    with pytest.raises(ValueError):
        validate_bundle(rewrite(report(), change))


@pytest.mark.parametrize("name", [LOG_NAME, "system-info.json", "parent/", "private.txt"])
def test_altered_text_directory_contents_and_extra_files_are_rejected(name):
    data = rewrite(report(), lambda payload: payload.update({name: SECRET.encode()}))
    with pytest.raises(ValueError):
        validate_bundle(data)


@pytest.mark.parametrize("change", [
    lambda text: text.replace(" | ", " | " + SECRET),
    lambda text: text.replace("fields={}", 'fields={"private":"' + SECRET + '"}'),
    lambda text: text.replace("event=diagnostic.rejected", "event=private.unknown"),
    lambda text: text.replace("#1", "#-1"),
    lambda text: text + "\n",
])
def test_log_line_requires_valid_fields_and_exact_catalog_description(change):
    data = rewrite(report(), lambda payload: payload.update({LOG_NAME: change(payload[LOG_NAME].decode()).encode()}))
    with pytest.raises(ValueError):
        validate_bundle(data)


def test_private_system_field_and_incorrect_inventory_are_rejected():
    for path, value in ((["system", "kernel"], SECRET), (["logs", LOG_NAME], 2),
                        (["counts", "missing"], -1), (["health", "timer"], SECRET)):
        def change(payload):
            info = json.loads(payload["system-info.json"])
            target = info
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            payload["system-info.json"] = json.dumps(info).encode()
        with pytest.raises(ValueError):
            validate_bundle(rewrite(report(), change))


def test_report_metadata_and_trailing_bytes_are_stripped():
    clean = report()
    output = BytesIO()
    with ZipFile(BytesIO(clean)) as source, ZipFile(output, "w") as archive:
        archive.comment = SECRET.encode()
        for name in source.namelist():
            entry = ZipInfo(name, date_time=(2026, 9, 12, 12, 0, 0))
            entry.comment = SECRET.encode()
            archive.writestr(entry, source.read(name))
    assert validate_bundle(output.getvalue() + SECRET.encode()) == clean


def test_history_and_record_limits_and_component_binding(monkeypatch):
    with pytest.raises(ValueError):
        build_report({f"broker/2026-09-{day:02}.log": [] for day in range(1, 5)})
    with pytest.raises(ValueError):
        build_report({"parent/2026-09-12.log": [record()]})
    from common.oh_no_parent_control_ui import diagnostic_report
    monkeypatch.setattr(diagnostic_report, "MAX_RECORDS", 1)
    with pytest.raises(ValueError):
        build_report({LOG_NAME: [record(), record()]})


@pytest.mark.parametrize("system", [None, sample_info()])
def test_older_broker_records_remain_explicitly_undated(system):
    data = with_system_info(build_bundle([record()], system_info=system), sample_info())
    with ZipFile(BytesIO(validate_bundle(data))) as archive:
        logs, _ = read_report(archive)
        assert logs == {"broker/undated.log": [record()]}


def test_older_system_inventory_is_compacted_without_unknown_rows():
    system = sample_info()
    system["dependencies"]["packages"].extend(
        {"name": "[Dependency]", "version": "1.2", "architecture": "amd64", "status": "installed"}
        for _ in range(777))
    data = with_system_info(build_bundle([]), system)
    with ZipFile(BytesIO(validate_bundle(data))) as archive:
        info = archive.read("system-info.json")
        assert len(info) < 2000
        assert b"[Dependency]" not in info
