"""Automatic system attachments never serialize identities or arbitrary metadata."""

from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from gi.repository import GLib

from common.oh_no_parent_control_ui import system_info as info
from common.oh_no_parent_control_ui.diagnostic_privacy import version
from common.oh_no_parent_control_ui.diagnostic_bundle import build_bundle, validate_bundle, with_system_info
from tests.support.system_info import sample_info

SECRET = "private-person@example.test"


@pytest.mark.parametrize("source,expected", [
    ("2:3.14.2-1ubuntu3", "3.14.2"), ("6.17.0-" + SECRET, "6.17.0"),
    ("1.2+" + SECRET, "1.2"), (SECRET, "unknown"),
    ("/home/12345/1.2", "unknown"), ("9" * 400, "unknown"),
    ("2026-09-11", "2026"), (None, "unknown"), (True, "unknown"),
])
def test_version_projection_discards_custom_text(source, expected):
    assert version(source) == expected


def test_readable_report_roundtrip_and_schema_one_compatibility():
    old = build_bundle([])
    assert validate_bundle(old) == old
    new = with_system_info(old, sample_info())
    assert validate_bundle(new) == new
    with ZipFile(BytesIO(new)) as archive:
        assert archive.namelist() == ["system-info.json", "broker/", "child/", "kiosk/", "parent/"]
        document = json.loads(archive.read("system-info.json"))
        assert document["schema"] == 3
        assert document["system"] == sample_info()
        assert all(entry.date_time == (1980, 1, 1, 0, 0, 0) for entry in archive.infolist())


@pytest.mark.parametrize("path", [
    ("app_version",), ("kernel",), ("architecture",), ("session_type",),
    ("os", "id"), ("os", "version"), ("timezone", "name"),
    ("timezone", "utc_offset_seconds"), ("accounts", "administrators"),
    ("accounts", "non_administrators"), ("accounts", "status"),
    ("dependencies", "status"), ("dependencies", "packages", 0, "name"),
    ("dependencies", "packages", 0, "version"),
    ("dependencies", "packages", 0, "architecture"),
    ("dependencies", "packages", 0, "status"),
])
def test_every_system_field_rejects_identity_at_archive_boundary(path):
    value = sample_info()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = SECRET
    with pytest.raises(ValueError):
        with_system_info(build_bundle([]), value)
    # Also exercise an attacker bypassing construction and editing the ZIP.
    clean = with_system_info(build_bundle([]), sample_info())
    output = BytesIO()
    with ZipFile(BytesIO(clean)) as source, ZipFile(output, "w") as archive:
        for name in source.namelist():
            data = source.read(name)
            if name == "system-info.json":
                document = json.loads(data)
                document["system"] = value
                data = json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True).encode() + b"\n"
            archive.writestr(name, data)
    with pytest.raises(ValueError):
        validate_bundle(output.getvalue())


def test_extra_system_fields_and_identity_hashes_are_rejected():
    for extra in ("username", "uid", "hostname", "machine_id", "username_hash", "mapping"):
        value = sample_info()
        value[extra] = "a" * 64
        with pytest.raises(ValueError):
            info.validate_system_info(value)
    for label in ("[Dependency 1]", "[Admin User 1]", "a" * 64):
        value = sample_info()
        value["dependencies"]["packages"][0]["name"] = label
        with pytest.raises(ValueError):
            info.validate_system_info(value)


def installed(name, raw_version="1.2-" + SECRET, dependencies=(), architecture="amd64"):
    return SimpleNamespace(package=SimpleNamespace(name=name), version=raw_version,
                           architecture=architecture, get_dependencies=lambda *_: dependencies)


def test_dependency_collection_reads_only_named_runtime_versions():
    cache = {name: SimpleNamespace(installed=installed(name)) for name in info.DIAGNOSTIC_PACKAGES}
    cache[SECRET] = Mock()
    for package in cache.values():
        if isinstance(package, SimpleNamespace):
            package.installed.get_dependencies = Mock(side_effect=AssertionError("No traversal"))
    cache["python3-gi"].installed = None
    result = info.dependency_info(cache)
    assert result["status"] == "partial"
    text = json.dumps(result)
    assert SECRET not in text and "[Dependency]" not in text
    assert any(row["name"] == "python3-gi" and row["status"] == "missing" for row in result["packages"])
    assert {row["name"] for row in result["packages"]} == set(info.DIAGNOSTIC_PACKAGES) | {"quill"}
    assert len(result["packages"]) == 21
    assert len(text) < 2500
    cache[SECRET].assert_not_called()


def test_dependency_deadline_and_source_preview_are_explicitly_partial():
    cache = {info.PACKAGE: SimpleNamespace(installed=installed(info.PACKAGE))}
    assert info.dependency_info(cache, deadline=0)["status"] == "partial"
    result = info.dependency_info({})
    assert result["status"] == "partial"
    assert {row["name"] for row in result["packages"] if row["status"] == "missing"} == set(info.DIAGNOSTIC_PACKAGES)


def test_dependency_failure_does_not_format_exception():
    class PrivateFailure(Exception):
        def __str__(self):
            raise AssertionError("Never format private exceptions")
    class BrokenCache:
        def __contains__(self, name):
            raise PrivateFailure()
    assert info.dependency_info(BrokenCache())["status"] == "unavailable"


def test_runtime_roots_track_declared_dependencies():
    control = (Path(__file__).resolve().parents[2] / "debian/control").read_text()
    depends = next(line for line in control.splitlines() if line.startswith("Depends: "))
    declared = {part.strip() for part in depends.removeprefix("Depends: ").split(",") if "${" not in part}
    assert set(info.RUNTIME_ROOTS) == declared


def test_bundled_quill_version_matches_shipped_notice():
    notice = Path(info.__file__).with_name("rich_editor") / "quill.js.LICENSE.txt"
    assert "Quill Editor v2.0.3" in notice.read_text()


def test_account_counts_request_only_role_properties(monkeypatch):
    passwd = "\n".join([
        "root:x:0:0:private:/root:/bin/bash",
        "oh-no-parent-control:x:1000:1000:private:/private:/bin/bash",
        "private-admin:x:1001:1001:Secret Name:/private:/bin/bash",
        "private-child:x:1002:1002:Secret Name:/private:/bin/bash",
        "private-service:x:1003:1003:Secret Name:/private:/usr/sbin/nologin",
        "private-other:x:1004:1004:Secret Name:/private:/bin/bash",
    ])
    monkeypatch.setattr(info, "_bounded_read", lambda _: passwd)

    def call(*args):
        method = args[3]
        if method == "FindUserById":
            uid, = args[4].unpack()
            return GLib.Variant("(o)", (f"/org/freedesktop/Accounts/User{uid}",))
        assert method == "Get"
        prop = args[4].unpack()[1]
        if prop == "LocalAccount":
            value = GLib.Variant("b", not args[1].endswith("1004"))
        elif prop == "SystemAccount":
            value = GLib.Variant("b", False)
        else:
            assert prop == "AccountType"
            value = GLib.Variant("i", 1 if args[1].endswith("1001") else 0)
        return GLib.Variant("(v)", (value,))

    connection = Mock(call_sync=Mock(side_effect=call))
    result = info.account_info(connection)
    assert result == {"administrators": 1, "non_administrators": 1, "status": "complete"}
    assert "private" not in json.dumps(result)
    connection.call_sync.side_effect = OSError(SECRET)
    assert info.account_info(connection)["status"] == "partial"


@pytest.mark.parametrize("override,name", [
    ("America/Los_Angeles", "America/Los_Angeles"),
    (":/usr/share/zoneinfo/Europe/London", "Europe/London"),
    ("/home/" + SECRET + "/timezone", "unknown"), (SECRET, "unknown"),
])
def test_timezone_never_exports_raw_override(monkeypatch, override, name):
    monkeypatch.setenv("TZ", override)
    result = info.timezone_info()
    assert result["name"] == name
    assert SECRET not in json.dumps(result)


def test_collector_discards_os_branding_and_environment(monkeypatch):
    def read(path, limit=65536):
        if str(path) == "/etc/os-release":
            return 'ID=ubuntu\nVERSION_ID="26.04"\nPRETTY_NAME=' + SECRET
        return '{"version":"1.2+private-person"}'
    monkeypatch.setattr(info, "_bounded_read", read)
    monkeypatch.setattr(info, "account_info", lambda _: sample_info()["accounts"])
    monkeypatch.setattr(info, "dependency_info", lambda: sample_info()["dependencies"])
    monkeypatch.setattr(info.platform, "release", lambda: "6.17.0-" + SECRET)
    monkeypatch.setenv("XDG_SESSION_TYPE", SECRET)
    monkeypatch.setenv("TZ", SECRET)
    result = info.collect_system_info(Mock())
    assert result["os"] == {"id": "ubuntu", "version": "26.04"}
    assert result["kernel"] == "6.17.0"
    assert result["session_type"] == "unknown"
    assert SECRET not in json.dumps(result)
