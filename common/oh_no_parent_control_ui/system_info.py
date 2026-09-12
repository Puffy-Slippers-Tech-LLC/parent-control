"""Bounded system diagnostics collected locally, with no network or identity export.

The only textual outputs are shipped categories and numeric upstream versions.
Dependency collection is limited to a fixed troubleshooting list.
All external errors become fixed states without formatting their messages.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import platform
import time

from .diagnostic_privacy import account_counts, category, version

PACKAGE = "oh-no-parent-control"
# Keep the declared runtime roots synchronized with debian/control (tested).
RUNTIME_ROOTS = (
    "accountsservice", "adduser", "debconf", "dbus-user-session", "fapolicyd",
    "gdm3", "gir1.2-adw-1", "gir1.2-gstreamer-1.0", "gir1.2-gtk-4.0",
    "gir1.2-malcontent-0", "gir1.2-webkit-6.0", "gnome-kiosk", "gnome-shell",
    "gstreamer1.0-plugins-base", "gstreamer1.0-plugins-good", "gtk-update-icon-cache",
    "libglib2.0-bin", "libpam-malcontent", "libpam-runtime", "malcontent",
    "mate-polkit-bin", "polkitd", "python3", "python3-apt", "python3-gi",
    "python3-gi-cairo", "python3-requests", "sudo", "systemd-sysusers",
    "update-notifier", "update-notifier-common",
)
PACKAGE_NAMES = frozenset(RUNTIME_ROOTS) | frozenset((
    PACKAGE, "quill", "gjs", "mutter", "systemd", "dbus", "dbus-daemon",
    "libc6", "libgcc-s1", "libstdc++6", "libpam0g", "libpam-modules",
    "libpam-modules-bin", "libsystemd0", "libudev1", "libcap2", "libcap2-bin",
    "libglib2.0-0t64", "libglib2.0-data", "libgtk-4-1", "libgtk-4-common",
    "libadwaita-1-0", "libwebkitgtk-6.0-4", "libjavascriptcoregtk-6.0-1",
    "libmalcontent-0-0", "libmalcontent-ui-1-1", "libaccountsservice0",
    "libpolkit-gobject-1-0", "libpolkit-agent-1-0", "libgjs0g", "libmozjs-140-0",
    "libgstreamer1.0-0", "libgstreamer-plugins-base1.0-0", "libgstreamer-gl1.0-0",
    "libcairo2", "libcairo-gobject2", "libpango-1.0-0", "libpangocairo-1.0-0",
    "libgdk-pixbuf-2.0-0", "libgirepository-1.0-1", "libgirepository-2.0-0",
    "gir1.2-glib-2.0", "gir1.2-gdkpixbuf-2.0", "gir1.2-pango-1.0",
    "python3-minimal", "python3.14", "python3.14-minimal", "libpython3.14-stdlib",
    "libpython3.14-minimal", "libpython3-stdlib", "python3-cairo",
    "python3-certifi", "python3-charset-normalizer", "python3-idna",
    "python3-urllib3", "ca-certificates", "openssl", "tzdata", "dconf-service",
    "dconf-gsettings-backend", "gsettings-desktop-schemas", "gnome-session-bin",
    "gnome-session-common", "gnome-settings-daemon", "gnome-shell-common",
    "libwayland-client0", "libwayland-server0", "libx11-6", "libxkbcommon0",
    "libdrm2", "libegl1", "libgl1", "libgbm1", "libepoxy0", "libpipewire-0.3-0",
    "libpulse0", "libasound2t64", "zlib1g", "libssl3t64", "libapt-pkg7.0",
))
ARCHITECTURES = ("amd64", "arm64", "armhf", "i386", "ppc64el", "s390x", "riscv64", "all")
OS_IDS = ("ubuntu", "debian")
MAX_DEPENDENCIES = 2048
# These versions explain the application's principal integration boundaries.
# Do not walk their dependency closures or enumerate unrelated installed software.
DIAGNOSTIC_PACKAGES = (
    "accountsservice", "fapolicyd", "gdm3", "gnome-kiosk", "gnome-shell", "gjs",
    "malcontent", "polkitd", "systemd", "dbus", "libglib2.0-0t64", "libgtk-4-1",
    "libadwaita-1-0", "libwebkitgtk-6.0-4", "libmalcontent-0-0",
    "libpam-malcontent", "python3", "python3-apt", "python3-gi", "python3-requests",
)
STATES = ("complete", "partial", "unavailable")
ZONES = frozenset(json.loads(Path(__file__).with_name("diagnostic_timezones.json").read_text()))


def _bounded_read(path, limit=65536):
    with Path(path).open("r", encoding="utf-8") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Diagnostic source limit")
    return value


def timezone_info():
    """Resolve only an approved zone name; never export TZ or a symlink path."""
    name = "unknown"
    try:
        override = os.environ.get("TZ")
        if override is not None:
            candidate = override.removeprefix(":")
            candidate = candidate.removeprefix("/usr/share/zoneinfo/")
            name = category(candidate, ZONES)
        else:
            target = str(Path("/etc/localtime").resolve())
            name = category(target.removeprefix("/usr/share/zoneinfo/"), ZONES)
        # Numeric offset reflects the calling frontend's effective timezone,
        # including valid POSIX TZ overrides whose name is deliberately omitted.
        offset = datetime.now().astimezone().utcoffset()
        seconds = int(offset.total_seconds()) if offset is not None else None
    except (OSError, ValueError, OverflowError):
        seconds = None
    return {"name": name, "utc_offset_seconds": seconds}


def _dependency_row(name, raw_version, architecture, status="installed"):
    return {"name": category(name, PACKAGE_NAMES, "[Dependency]"),
            "version": version(raw_version),
            "architecture": category(architecture, ARCHITECTURES), "status": status}


def dependency_info(cache=None, *, deadline=None):
    """Read only key runtime versions from the local, in-memory APT cache."""
    rows = [_dependency_row("quill", "2.0.3", "all", "bundled")]
    status = "complete"
    deadline = time.monotonic() + 10 if deadline is None else deadline
    try:
        if cache is None:
            import apt
            cache = apt.Cache(memonly=True)
        for name in DIAGNOSTIC_PACKAGES:
            if time.monotonic() >= deadline:
                status = "partial"
                break
            installed = cache[name].installed if name in cache else None
            if installed is None:
                status = "partial"
                rows.append(_dependency_row(name, "", "unknown", "missing"))
            else:
                rows.append(_dependency_row(name, installed.version, installed.architecture))
        rows.sort(key=lambda row: tuple(row[key] for key in ("name", "architecture", "version", "status")))
    except Exception:
        # Includes missing APT bindings and malformed package metadata. Their
        # exception messages and package records must never reach diagnostics.
        status = "unavailable"
        rows = [_dependency_row("quill", "2.0.3", "all", "bundled")]
    return {"status": status, "packages": rows}


def account_info(connection):
    """Count local interactive human accounts through minimal property reads.

    /etc/passwd identities are used only to locate AccountsService objects and
    are immediately discarded. No GetAll, real names, icons, groups or homes.
    Root, system/service users and the reserved product kiosk are excluded.
    """
    from gi.repository import Gio, GLib

    roles = []
    complete = True
    deadline = time.monotonic() + 5
    try:
        lines = _bounded_read("/etc/passwd").splitlines()
        for line in lines:
            fields = line.split(":")
            if len(fields) != 7:
                complete = False
                continue
            if (not fields[2].isdigit() or int(fields[2]) < 1000 or
                    fields[0] == "oh-no-parent-control" or
                    fields[6] in ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false")):
                continue
            if time.monotonic() >= deadline:
                complete = False
                break
            try:
                reply = connection.call_sync(
                    "org.freedesktop.Accounts", "/org/freedesktop/Accounts",
                    "org.freedesktop.Accounts", "FindUserById",
                    GLib.Variant("(x)", (int(fields[2]),)), GLib.VariantType.new("(o)"),
                    Gio.DBusCallFlags.NONE, 250, None,
                )
                path, = reply.unpack()
                if path != f"/org/freedesktop/Accounts/User{int(fields[2])}":
                    complete = False
                    continue
                properties = {}
                for prop in ("LocalAccount", "SystemAccount", "AccountType"):
                    reply = connection.call_sync(
                        "org.freedesktop.Accounts", path, "org.freedesktop.DBus.Properties",
                        "Get", GLib.Variant("(ss)", ("org.freedesktop.Accounts.User", prop)),
                        GLib.VariantType.new("(v)"), Gio.DBusCallFlags.NONE, 250, None,
                    )
                    properties[prop], = reply.unpack()
                if any(type(properties[prop]) is not bool for prop in ("LocalAccount", "SystemAccount")):
                    complete = False
                elif properties["LocalAccount"] is not True or properties["SystemAccount"] is not False:
                    roles.append("excluded")
                elif type(properties["AccountType"]) is int and properties["AccountType"] in (0, 1):
                    roles.append("administrator" if properties["AccountType"] == 1 else "non-administrator")
                else:
                    complete = False
            except Exception:
                complete = False
    except (OSError, ValueError, UnicodeError):
        return {"administrators": 0, "non_administrators": 0, "status": "unavailable"}
    return account_counts(roles, complete=complete)


def collect_system_info(connection):
    os_info = {"id": "unknown", "version": "unknown"}
    try:
        # Select fields rather than serializing os-release (which may contain
        # support URLs, custom host branding and arbitrary vendor metadata).
        release = dict(line.split("=", 1) for line in _bounded_read("/etc/os-release").splitlines()
                       if "=" in line and not line.startswith("#"))
        os_info = {"id": category(release.get("ID", "").strip('"'), OS_IDS),
                   "version": version(release.get("VERSION_ID", "").strip('"'))}
    except (OSError, ValueError, UnicodeError):
        pass
    app_version = "unknown"
    try:
        data = Path("/usr/share/oh-no-parent-control/app.json")
        if not data.exists():
            data = Path(__file__).resolve().parents[2] / "data/app.json"
        app_version = version(json.loads(_bounded_read(data)).get("version"))
    except (OSError, ValueError, UnicodeError, AttributeError):
        pass
    return validate_system_info({
        "schema": 1, "app_version": app_version, "os": os_info, "kernel": version(platform.release()),
        "architecture": category(platform.machine(), ("x86_64", "aarch64", "armv7l", "i686", "ppc64le", "s390x", "riscv64")),
        "timezone": timezone_info(),
        "session_type": category(os.environ.get("XDG_SESSION_TYPE"), ("wayland", "x11", "tty")),
        "accounts": account_info(connection), "dependencies": dependency_info(),
    })


def validate_system_info(value):
    """Fail closed at construction, ZIP reading, and transport validation."""
    def mapping(item, keys):
        if type(item) is not dict or set(item) != set(keys.split()):
            raise ValueError("Invalid system diagnostic fields")

    def choice(item, allowed):
        if type(item) is not str or item not in allowed:
            raise ValueError("Invalid system diagnostic category")

    def numeric_version(item):
        if type(item) is not str or item != version(item):
            raise ValueError("Invalid system diagnostic version")

    mapping(value, "schema app_version os kernel architecture timezone session_type accounts dependencies")
    if type(value["schema"]) is not int or value["schema"] != 1:
        raise ValueError("Invalid system diagnostic schema")
    mapping(value["os"], "id version")
    numeric_version(value["app_version"])
    choice(value["os"]["id"], (*OS_IDS, "unknown"))
    numeric_version(value["os"]["version"])
    numeric_version(value["kernel"])
    choice(value["architecture"], ("x86_64", "aarch64", "armv7l", "i686", "ppc64le", "s390x", "riscv64", "unknown"))
    choice(value["session_type"], ("wayland", "x11", "tty", "unknown"))
    mapping(value["timezone"], "name utc_offset_seconds")
    choice(value["timezone"]["name"], ZONES | {"unknown"})
    offset = value["timezone"]["utc_offset_seconds"]
    if offset is not None and (type(offset) is not int or not -86400 < offset < 86400):
        raise ValueError("Invalid diagnostic timezone offset")
    mapping(value["accounts"], "administrators non_administrators status")
    choice(value["accounts"]["status"], STATES)
    for key in ("administrators", "non_administrators"):
        count = value["accounts"][key]
        if type(count) is not int or not 0 <= count <= 65536:
            raise ValueError("Invalid diagnostic account count")
    mapping(value["dependencies"], "status packages")
    choice(value["dependencies"]["status"], STATES)
    rows = value["dependencies"]["packages"]
    if type(rows) is not list or len(rows) > MAX_DEPENDENCIES:
        raise ValueError("Invalid diagnostic dependency count")
    for row in rows:
        mapping(row, "name version architecture status")
        choice(row["name"], PACKAGE_NAMES | {"[Dependency]"})
        numeric_version(row["version"])
        choice(row["architecture"], (*ARCHITECTURES, "unknown"))
        choice(row["status"], ("installed", "missing", "bundled"))
    return value
