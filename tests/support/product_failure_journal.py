"""Guest-side qualification reader for the product's native failure journal."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time

MESSAGE = "Oh No! Parent Control product failure"
COMPONENTS = ("broker", "parent", "child", "kiosk")
BROKER_UNIT = "oh-no-parent-control-broker.service"
KIOSK_APP_UNIT = "oh-no-parent-control-app.service"
BROKER_STARTUP_FAILURE = "onpc.runtime bootstrap failed"
FENCE = "ONPC_FAILURE_FENCE"
PROBE = "ONPC_FAILURE_PROBE"
OCCURRENCE = "ONPC_OCCURRENCE_MONOTONIC_USEC"
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
JOURNAL_SOCKET = "/run/systemd/journal/socket"
SETTLE_SECONDS = 1
MAX_OUTPUT = 256 * 1024
FIELDS = (
    "__CURSOR,__MONOTONIC_TIMESTAMP,_BOOT_ID,_TRANSPORT,_UID,_PID,_EXE,_COMM,"
    "_CMDLINE,_SYSTEMD_UNIT,_SYSTEMD_USER_UNIT,MESSAGE,"
    "ONPC_FAILURE_VERSION,ONPC_COMPONENT,ONPC_FAILURE_CATEGORY,"
    f"{OCCURRENCE},{FENCE},{PROBE}"
)


@dataclass(frozen=True)
class Boundary:
    boot_id: str
    monotonic_usec: int
    cursor: str
    token: str


@dataclass(frozen=True)
class Event:
    component: str
    category: str
    monotonic_usec: int
    source: str


class EvidenceUnavailable(ValueError):
    """The observed span cannot support a complete result."""


def _boot():
    boot = BOOT_ID.read_text(encoding="ascii").strip().replace("-", "")
    if not re.fullmatch(r"[0-9a-f]{32}", boot):
        raise EvidenceUnavailable("invalid boot identity")
    return boot


def _usec(record, field):
    value = record.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,19}", value):
        raise EvidenceUnavailable("missing or malformed journal time")
    return int(value)


def _send(**fields):
    payload = "".join(f"{key}={value}\n" for key, value in fields.items())
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as journal:
        journal.settimeout(1)
        journal.sendto(payload.encode("ascii"), JOURNAL_SOCKET)


def _records(boot, *matches, cursor=None, awaiting_marker=False):
    # Read forward from the cursor. journalctl caps the row count and its JSON
    # output bounds individual fields. A clipped span cannot contain its seal.
    command = [
        "/usr/bin/journalctl", "--quiet", "--no-pager", "--lines=+512", f"--boot={boot}",
        "--output=json", f"--output-fields={FIELDS}",
    ]
    if cursor is not None:
        command.append(f"--cursor={cursor}")
    try:
        result = subprocess.run([*command, *matches], stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=3,
                                env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError):
        raise EvidenceUnavailable("journal command unavailable") from None
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT:
        raise EvidenceUnavailable("journal output exceeded its bound")
    empty = result.returncode == 1 and not result.stdout and not result.stderr
    if (result.returncode != 0 or result.stderr) and not (awaiting_marker and empty):
        raise EvidenceUnavailable("journal query unavailable")
    records = [json.loads(line) for line in result.stdout.splitlines()]
    if any(not isinstance(item, dict) for item in records):
        raise EvidenceUnavailable("invalid journal output")
    return records


def capture_boundary():
    if os.geteuid() != 0:
        raise EvidenceUnavailable("failure observation requires the authorized guest reader")
    boot = _boot()
    token = secrets.token_hex(16)
    _send(MESSAGE="Oh No! Parent Control test boundary", **{FENCE: token})
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        records = _records(boot, "_TRANSPORT=journal", "_UID=0", f"{FENCE}={token}",
                           awaiting_marker=True)
        if records:
            record, = records
            cursor = record.get("__CURSOR")
            if (record.get("_PID") != str(os.getpid()) or record.get("_BOOT_ID") != boot
                    or not isinstance(cursor, str) or not cursor):
                raise EvidenceUnavailable("test boundary provenance changed")
            return Boundary(boot, _usec(record, "__MONOTONIC_TIMESTAMP"), cursor, token)
        time.sleep(0.05)
    raise EvidenceUnavailable("test boundary did not reach the journal")


def _is_boundary(record, boundary):
    return (
        record.get("__CURSOR") == boundary.cursor
        and record.get(FENCE) == boundary.token
        and record.get("_BOOT_ID") == boundary.boot_id
        and record.get("_TRANSPORT") == "journal"
        and record.get("_UID") == "0"
        and _usec(record, "__MONOTONIC_TIMESTAMP") == boundary.monotonic_usec
    )


def _matches(*groups):
    matches = []
    for group in groups:
        if matches:
            matches.append("+")
        matches.extend(group)
    return matches


def _closed_span(start, end, settle, *groups):
    if (start.boot_id != _boot() or end.boot_id != start.boot_id
            or settle.boot_id != start.boot_id
            or not start.monotonic_usec < end.monotonic_usec < settle.monotonic_usec):
        raise EvidenceUnavailable("invalid or changed journal span")
    fences = tuple(("_TRANSPORT=journal", "_UID=0", f"{FENCE}={marker.token}")
                   for marker in (start, end, settle))
    records = _records(start.boot_id, *_matches(*fences, *groups), cursor=start.cursor)
    if not records or not _is_boundary(records[0], start):
        raise EvidenceUnavailable("opening journal boundary unavailable")
    inside, found_end = [], False
    for record in records[1:]:
        if record.get("_BOOT_ID") != start.boot_id:
            raise EvidenceUnavailable("unexpected journal boot")
        if _is_boundary(record, end):
            found_end = True
        elif _is_boundary(record, settle):
            if not found_end:
                break
            return inside
        else:
            inside.append(record)
    raise EvidenceUnavailable("closing journal boundaries unavailable")


def _python_script(record, script):
    exe, command = record.get("_EXE"), record.get("_CMDLINE")
    if not isinstance(exe, str) or not re.fullmatch(r"/usr/bin/python3(?:\.[0-9]{1,2})?", exe):
        return False
    arguments = command.split() if isinstance(command, str) else []
    if not arguments:
        return False
    python, *args = arguments
    if python not in {exe, "/usr/bin/python3"}:
        return False
    if args[:1] == ["-I"]:
        args = args[1:]
    return args[:1] == [script]


def _from_broker(record):
    return (
        record.get("_UID") == "0" and record.get("_SYSTEMD_UNIT") == BROKER_UNIT
        and _python_script(record, "/usr/libexec/oh-no-parent-control-broker")
    )


def _source(record, parent_uid, child_uid, kiosk_uid):
    uid = record.get("_UID")
    user_unit = record.get("_SYSTEMD_USER_UNIT")
    if _from_broker(record):
        return "broker", "broker"
    if uid == parent_uid and _python_script(record, "/usr/bin/oh-no-parent-control-parent"):
        return "parent", "gtk"
    if (uid == kiosk_uid and user_unit == KIOSK_APP_UNIT
            and _python_script(record, "/usr/bin/oh-no-parent-control")):
        return "kiosk", "gtk"
    if uid == child_uid:
        if (record.get("_EXE") == "/usr/bin/gnome-shell" and isinstance(user_unit, str)
                and re.fullmatch(r"org\.gnome\.Shell(?:@[A-Za-z0-9_.-]+)?\.service", user_unit)):
            return "child", "gnome-shell"
        if _python_script(record, "/usr/bin/oh-no-parent-control-child"):
            return "child", "gtk"
    return None


def _os_event(record, received, child_uid, kiosk_uid):
    if (record.get("_TRANSPORT") == "stdout" and record.get("MESSAGE") == BROKER_STARTUP_FAILURE
            and _from_broker(record)):
        return Event("broker", "startup", received, "systemd")
    if record.get("_UID") not in {child_uid, kiosk_uid}:
        return None
    try:
        # These supplemental projections use the existing support observer
        # when installed. Native reads and the bootstrap marker stand alone.
        from oh_no_parent_control.dependency_diagnostics import _gnome_shell_event, _kiosk_session_event

        kiosk = _kiosk_session_event(record, int(kiosk_uid))
        if kiosk is not None and kiosk[0] == "app-exit" and kiosk[2] != 0:
            return Event("kiosk", "unexpected", received, "systemd")
        shell = _gnome_shell_event(record, int(child_uid))
        if (shell is not None and shell[0] == "extension-manager.shell-journal"
                and shell[1]["candidate"] == "our-extension"):
            return Event("child", "unexpected", received, "shell-log")
    except (ImportError, OSError, ValueError):
        return None
    return None


def _in_span(start, end, occurred):
    return start.monotonic_usec <= occurred < end.monotonic_usec


def read_failures(start, end, *, parent_uid, child_uid, kiosk_uid):
    parent_uid, child_uid, kiosk_uid = (str(int(uid)) for uid in (parent_uid, child_uid, kiosk_uid))
    events = []
    unattributed = 0
    try:
        time.sleep(SETTLE_SECONDS)
        settle = capture_boundary()
        records = _closed_span(
            start, end, settle,
            ("_TRANSPORT=journal", f"MESSAGE={MESSAGE}"),
            ("_TRANSPORT=journal", "ONPC_FAILURE_VERSION=1"),
            ("_TRANSPORT=journal", *(f"ONPC_COMPONENT={component}" for component in COMPONENTS)),
            ("_TRANSPORT=stdout", "_UID=0", f"_SYSTEMD_UNIT={BROKER_UNIT}",
             f"MESSAGE={BROKER_STARTUP_FAILURE}"),
            ("_UID=" + kiosk_uid, "_COMM=systemd"),
            ("_UID=" + child_uid, "_EXE=/usr/bin/gnome-shell"),
            ("_UID=0", "_COMM=systemd-journal"),
        )
        for record in records:
            received = _usec(record, "__MONOTONIC_TIMESTAMP")
            message = record.get("MESSAGE")
            if (record.get("_UID") == "0" and record.get("_COMM") == "systemd-journal"
                    and isinstance(message, str) and message.startswith(("Suppressed ", "Missed "))
                    and start.monotonic_usec <= received):
                raise EvidenceUnavailable("journal reported dropped records")
            if record.get("_TRANSPORT") == "journal" and (
                    "ONPC_FAILURE_VERSION" in record or "ONPC_COMPONENT" in record
                    or message == MESSAGE):
                producer = _source(record, parent_uid, child_uid, kiosk_uid)
                if producer is None:
                    unattributed += 1
                    continue
                component, source = producer
                if (record.get("ONPC_FAILURE_VERSION") != "1"
                        or record.get("ONPC_COMPONENT") != component):
                    raise EvidenceUnavailable("invalid failure record header")
                category = record.get("ONPC_FAILURE_CATEGORY")
                if not isinstance(category, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", category):
                    raise EvidenceUnavailable("invalid failure category")
                occurred = _usec(record, OCCURRENCE)
                if not 0 < occurred <= received:
                    raise EvidenceUnavailable("invalid failure occurrence time")
                if _in_span(start, end, occurred):
                    events.append(Event(component, category, occurred, source))
            elif _in_span(start, end, received):
                event = _os_event(record, received, child_uid, kiosk_uid)
                if event is not None:
                    events.append(event)
    except EvidenceUnavailable as error:
        return {"complete": False, "events": [], "unattributed": unattributed, "reason": str(error)}
    except (OSError, ValueError, KeyError, TypeError):
        return {"complete": False, "events": [], "unattributed": unattributed,
                "reason": "journal evidence unavailable or malformed"}
    return {"complete": True, "events": [asdict(event) for event in sorted(
        events, key=lambda event: event.monotonic_usec)], "unattributed": unattributed, "reason": ""}


def _exercise():
    start = capture_boundary()
    occurred = time.monotonic_ns() // 1000
    end = capture_boundary()
    token = secrets.token_hex(16)
    # Exercise late arrival with a separate engineering marker, never a
    # forged product record.
    _send(MESSAGE="Oh No! Parent Control test delivery probe", **{
        PROBE: token, OCCURRENCE: occurred,
    })
    settle = capture_boundary()
    rows = _closed_span(start, end, settle, ("_UID=0", "_TRANSPORT=journal", f"{PROBE}={token}"))
    if (len(rows) != 1 or _usec(rows[0], "__MONOTONIC_TIMESTAMP") < end.monotonic_usec
            or not _in_span(start, end, _usec(rows[0], OCCURRENCE))):
        raise ValueError("late arrival lost its original case position")
    missing = Boundary(start.boot_id, start.monotonic_usec, start.cursor, secrets.token_hex(16))
    if read_failures(missing, end, parent_uid=0, child_uid=0, kiosk_uid=0)["complete"]:
        raise ValueError("missing journal span became a complete read")


def main():
    # The qualification stages this reader alongside other guest-only support.
    sys.path[:0] = ["/usr/lib/oh-no-parent-control/broker", "/usr/lib/oh-no-parent-control"]
    match sys.argv[1:]:
        case ["boundary"]:
            print(json.dumps(asdict(capture_boundary())))
        case ["read", start, end, parent, child, kiosk]:
            result = read_failures(
                Boundary(**json.loads(start)), Boundary(**json.loads(end)),
                parent_uid=parent, child_uid=child, kiosk_uid=kiosk,
            )
            print(json.dumps(result))
        case ["exercise"]:
            _exercise()
        case _:
            raise SystemExit("expected boundary, read or exercise")


if __name__ == "__main__":
    main()
