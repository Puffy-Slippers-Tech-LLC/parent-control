"""Automatic system attachments never serialize identities or arbitrary metadata."""

from io import BytesIO
import json
import subprocess
import sys
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


def test_display_collection_uses_live_session_modes_and_discards_identities(monkeypatch):
    from gi.repository import Gio
    signature = "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})"
    spec = (SECRET, SECRET, SECRET, SECRET)
    inactive = ("disabled", SECRET, SECRET, SECRET)
    def state(width, height, scale):
        mode = (SECRET, width, height, 60.0, 1.0, [1.0, 1.25], {"is-current": GLib.Variant("b", True)})
        return GLib.Variant(signature, (1, [(spec, [mode], {"display-name": GLib.Variant("s", SECRET)}),
                                            (inactive, [mode], {})],
                                      [(0, 0, scale, 0, True, [spec], {})], {}))
    connection = Mock(call_sync=Mock(side_effect=[state(2560, 1440, 1.0), state(3840, 2160, 1.25)]))
    buses = []
    monkeypatch.setattr(Gio, "bus_get_sync", lambda bus, _: buses.append(bus) or connection)
    monkeypatch.setattr(Gio.Settings, "new", lambda _: SimpleNamespace(get_double=lambda _: 1.0))
    first, second = info.display_info(), info.display_info()
    assert first == {"status": "complete", "monitors": [
        {"width": 2560, "height": 1440, "scale": 1.0, "primary": True}], "text_scale": 1.0}
    assert second["monitors"] == [{"width": 3840, "height": 2160, "scale": 1.25, "primary": True}]
    assert buses == [Gio.BusType.SESSION, Gio.BusType.SESSION]
    for call in connection.call_sync.call_args_list:
        assert call.args[:5] == ("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
                                "org.gnome.Mutter.DisplayConfig", "GetCurrentState", None)
        assert call.args[6:8] == (Gio.DBusCallFlags.NO_AUTO_START, 2000)
    assert SECRET not in json.dumps((first, second))


def test_display_probe_failure_is_private_and_does_not_block_report():
    class PrivateFailure(Exception):
        def __str__(self):
            raise AssertionError("Never format display errors")
    result = info.display_info(Mock(call_sync=Mock(side_effect=PrivateFailure())))
    assert result == {"status": "unavailable", "monitors": [], "text_scale": None}
    report = with_system_info(build_bundle([]), {**sample_info(), "displays": result})
    assert validate_bundle(report) == report


@pytest.mark.parametrize("key,invalid", [
    ("width", SECRET), ("height", True), ("width", 0), ("height", 65537),
    ("scale", SECRET), ("scale", float("nan")), ("scale", float("inf")),
    ("scale", 0), ("scale", 17), ("primary", SECRET), ("serial", SECRET),
])
def test_display_fields_fail_closed_at_archive_boundary(key, invalid):
    row = {"width": 2560, "height": 1440, "scale": 1.0, "primary": True, key: invalid}
    system = {**sample_info(), "displays": {"status": "complete", "monitors": [row], "text_scale": 1.0}}
    with pytest.raises(ValueError):
        with_system_info(build_bundle([]), system)


@pytest.mark.parametrize("key,invalid", [
    ("status", SECRET), ("text_scale", SECRET), ("text_scale", float("nan")),
    ("monitors", [{}] * 33), ("connector", SECRET),
])
def test_display_summary_fail_closed_at_archive_boundary(key, invalid):
    displays = {"status": "complete", "monitors": [], "text_scale": 1.0, key: invalid}
    with pytest.raises(ValueError):
        with_system_info(build_bundle([]), {**sample_info(), "displays": displays})


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


def test_rpm_dependency_query_is_bounded_and_survives_archive_projection(monkeypatch):
    monkeypatch.setitem(sys.modules, "apt", None)
    def query(command, **kwargs):
        assert command == ["/usr/bin/rpm", "--query", "--queryformat",
                           "%{NAME}\t%{VERSION}\t%{ARCH}\n", "--", *info.RPM_DIAGNOSTIC_PACKAGES]
        assert 0 < kwargs["timeout"] <= 10
        assert kwargs["env"]["LC_ALL"] == "C"
        rows = [f"{name}\t1.2-{SECRET}\tx86_64" for name in info.RPM_DIAGNOSTIC_PACKAGES
                if name != "dconf"]
        return subprocess.CompletedProcess(command, 1, "\n".join(rows) + "\npackage dconf is not installed\n", SECRET)
    monkeypatch.setattr(info.subprocess, "run", query)
    dependencies = info.dependency_info()
    assert dependencies["status"] == "partial"
    assert {row["name"] for row in dependencies["packages"]} == set(info.RPM_DIAGNOSTIC_PACKAGES) | {"quill"}
    assert SECRET not in json.dumps(dependencies)
    assert next(row for row in dependencies["packages"] if row["name"] == "dconf")["status"] == "missing"
    system = sample_info()
    system["os"] = {"id": "fedora", "version": "44"}
    system["dependencies"] = dependencies
    archive_bytes = with_system_info(build_bundle([]), system)
    assert validate_bundle(archive_bytes) == archive_bytes
    with ZipFile(BytesIO(archive_bytes)) as archive:
        assert json.loads(archive.read("system-info.json"))["system"] == system


@pytest.mark.parametrize("failure", [OSError(SECRET), subprocess.TimeoutExpired([], 10),
                                     subprocess.CompletedProcess([], 2, SECRET, SECRET),
                                     subprocess.CompletedProcess([], 0, SECRET, SECRET)])
def test_rpm_query_failures_are_explicit_and_private(monkeypatch, failure):
    monkeypatch.setitem(sys.modules, "apt", None)
    def query(*args, **kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure
    monkeypatch.setattr(info.subprocess, "run", query)
    result = info.dependency_info()
    assert result["status"] == "unavailable"
    assert SECRET not in json.dumps(result)


def test_rpm_dependency_deadline_does_not_launch_rpm(monkeypatch):
    monkeypatch.setitem(sys.modules, "apt", None)
    query = Mock(side_effect=AssertionError("Expired budget"))
    monkeypatch.setattr(info.subprocess, "run", query)
    assert info.dependency_info(deadline=0)["status"] == "partial"
    query.assert_not_called()


def test_available_apt_backend_never_launches_rpm(monkeypatch):
    query = Mock(side_effect=AssertionError("Available APT must use APT"))
    monkeypatch.setattr(info.subprocess, "run", query)
    cache = {name: SimpleNamespace(installed=installed(name)) for name in info.DIAGNOSTIC_PACKAGES}
    monkeypatch.setitem(sys.modules, "apt", SimpleNamespace(Cache=Mock(return_value=cache)))
    result = info.dependency_info()
    assert result["status"] == "complete"
    assert {row["name"] for row in result["packages"]} == set(info.DIAGNOSTIC_PACKAGES) | {"quill"}
    query.assert_not_called()


@pytest.mark.parametrize("os_id", ["fedora", "opensuse-tumbleweed", "rocky", "private-brand"])
def test_rpm_collection_does_not_depend_on_distribution_identity(monkeypatch, os_id):
    monkeypatch.setitem(sys.modules, "apt", None)
    monkeypatch.setattr(info, "_bounded_read", lambda path: (
        f'ID={os_id}\nVERSION_ID="44"' if str(path) == "/etc/os-release"
        else '{"version":"1.2"}'))
    monkeypatch.setattr(info, "account_info", lambda _: sample_info()["accounts"])
    monkeypatch.setattr(info, "display_info", lambda: {"status": "unavailable", "monitors": [], "text_scale": None})
    query = Mock(return_value=subprocess.CompletedProcess([], 0, "\n".join(
        f"{name}\t1.2\tx86_64" for name in info.RPM_DIAGNOSTIC_PACKAGES), ""))
    monkeypatch.setattr(info.subprocess, "run", query)
    result = info.collect_system_info(Mock())
    assert result["dependencies"]["status"] == "complete"
    assert result["os"]["id"] == (os_id if os_id in info.OS_IDS else "unknown")
    query.assert_called_once()

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
    monkeypatch.setattr(info, "display_info", lambda: {"status": "unavailable", "monitors": [], "text_scale": None})
    monkeypatch.setattr(info, "dependency_info", lambda **_: sample_info()["dependencies"])
    monkeypatch.setattr(info.platform, "release", lambda: "6.17.0-" + SECRET)
    monkeypatch.setenv("XDG_SESSION_TYPE", SECRET)
    monkeypatch.setenv("TZ", SECRET)
    result = info.collect_system_info(Mock())
    assert result["os"] == {"id": "ubuntu", "version": "26.04"}
    assert result["kernel"] == "6.17.0"
    assert result["session_type"] == "unknown"
    assert SECRET not in json.dumps(result)
