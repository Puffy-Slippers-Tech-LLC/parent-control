"""Read qualified product journal evidence and classify it for an installed case."""

from dataclasses import asdict, dataclass
from enum import StrEnum
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
ALLOWABLE_CATEGORIES = frozenset({
    "backend", "dependency", "operation", "presentation", "startup", "shell-extension-load",
})
SOURCES = {
    "broker": ("broker", "systemd"),
    "parent": ("gtk",),
    "child": ("gtk", "gnome-shell", "shell-log"),
    "kiosk": ("gtk", "systemd"),
}
BROKER_UNIT = "oh-no-parent-control-broker.service"
KIOSK_APP_UNIT = "oh-no-parent-control-app.service"
BROKER_STARTUP_FAILURE = "onpc.runtime bootstrap failed"
FENCE = "ONPC_FAILURE_FENCE"
PROBE = "ONPC_FAILURE_PROBE"
OCCURRENCE = "ONPC_OCCURRENCE_MONOTONIC_USEC"
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
BOOT_ORIGIN = "kernel-boot"
JOURNAL_SOCKET = "/run/systemd/journal/socket"
SETTLE_SECONDS = 1
# A busy desktop emits many supplemental Shell records over an entire boot.
# Keep the query bounded while still reading through an ordinary session exit.
MAX_OUTPUT = 4 * 1024 * 1024
MAX_ROWS = 4096
MAX_DIAGNOSTIC_EVENTS = 8
MAX_USEC = 10**19 - 1
CATEGORY = re.compile(r"[a-z][a-z0-9-]{0,47}")
FIELDS = (
    "__CURSOR,__MONOTONIC_TIMESTAMP,_BOOT_ID,_TRANSPORT,_UID,_PID,_EXE,_COMM,"
    "_CMDLINE,_SYSTEMD_UNIT,_SYSTEMD_USER_UNIT,MESSAGE,MESSAGE_ID,UNIT,JOB_RESULT,"
    "ONPC_FAILURE_VERSION,ONPC_COMPONENT,ONPC_FAILURE_CATEGORY,"
    f"{OCCURRENCE},{FENCE},{PROBE}"
)
REBOOT_REACHED = {
    "_TRANSPORT": "journal", "_UID": "0", "_PID": "1", "_SYSTEMD_UNIT": "init.scope",
    "MESSAGE_ID": "39f53479d3a045ac8e11786248231fbf", "UNIT": "reboot.target", "JOB_RESULT": "done",
}
JOURNAL_DRIVER = {
    "_TRANSPORT": "driver", "_UID": "0", "_SYSTEMD_UNIT": "systemd-journald.service",
}
JOURNAL_STARTED = "f77379a8490b408bbe5f6940505a777b"
JOURNAL_STOPPED = "d93fb3c9c24d451a97cea615ce59c00b"


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


@dataclass(frozen=True)
class Allowance:
    component: str
    category: str
    start_usec: int
    end_usec: int

    def __post_init__(self):
        if (self.component not in COMPONENTS or not isinstance(self.category, str)
                or self.category not in ALLOWABLE_CATEGORIES
                or not _valid_usec(self.start_usec) or not _valid_usec(self.end_usec)
                or self.start_usec >= self.end_usec):
            raise ValueError("invalid product fault allowance")

    def matches(self, event):
        return (event.component == self.component and event.category == self.category
                and self.start_usec <= event.monotonic_usec < self.end_usec)


class _Reason(StrEnum):
    AUTHORIZATION = "failure observation requires the authorized guest reader"
    QUERY = "journal query unavailable"
    BOUND = "journal output exceeded its bound"
    OUTPUT = "invalid journal output"
    SPAN = "invalid or changed journal span"
    OPEN = "opening journal boundary unavailable"
    CLOSE = "closing journal boundaries unavailable"
    DEPARTURE = "departing boot journal tail unavailable"
    BOOT = "unexpected journal boot"
    LOSS = "journal reported dropped records"
    TIME = "missing or malformed journal time"
    FORMAT = "unsupported failure record format"
    HEADER = "invalid failure record header"
    CATEGORY = "invalid failure category"
    OCCURRENCE = "invalid failure occurrence time"
    MALFORMED = "journal evidence unavailable or malformed"
    ALLOWANCE = "product fault allowance outside the case span"
    BOOT_ID = "invalid boot identity"
    FENCE_SEND = "journal boundary send failed"
    FENCE_TIMEOUT = "journal boundary confirmation timed out"
    FENCE_PROVENANCE = "invalid journal boundary provenance"


_READER_REASONS = frozenset(_Reason)


class FailureDisposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class FailureEvaluation:
    complete: bool
    unexpected: tuple[Event, ...]
    reason: str
    unattributed: int

    def disposition(self, *, case_failed=False):
        if case_failed or self.unexpected:
            return FailureDisposition.FAIL
        return FailureDisposition.PASS if self.complete else FailureDisposition.BLOCKED

    @property
    def diagnostics(self):
        lines = [
            f"Unexpected product fault {event.component}/{event.category} "
            f"from {event.source} at guest monotonic {event.monotonic_usec} us"
            for event in self.unexpected[:MAX_DIAGNOSTIC_EVENTS]
        ]
        remaining = len(self.unexpected) - len(lines)
        if remaining:
            lines.append(f"{remaining} additional unexpected product faults")
        if not self.complete:
            lines.append(f"Product fault observation incomplete ({self.reason})")
        return tuple(lines)


class EvidenceUnavailable(ValueError):
    """The observed span cannot support a complete result."""


def evidence_reason(detail, fallback):
    return detail if isinstance(detail, str) and detail in _READER_REASONS else fallback


def _boot():
    try:
        boot = BOOT_ID.read_text(encoding="ascii").strip().replace("-", "")
    except (OSError, UnicodeError) as error:
        raise EvidenceUnavailable(_Reason.BOOT_ID) from error
    if not re.fullmatch(r"[0-9a-f]{32}", boot):
        raise EvidenceUnavailable(_Reason.BOOT_ID)
    return boot


def _usec(record, field):
    value = record.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,19}", value):
        raise EvidenceUnavailable(_Reason.TIME)
    return int(value)


def _valid_usec(value):
    return type(value) is int and 0 < value <= MAX_USEC


def action_time():
    """Date an action in its own guest, independently of journal delivery."""
    occurred = time.monotonic_ns() // 1000
    return {"boot_id": _boot(), "monotonic_usec": occurred}


def decode_action_time(value):
    if (isinstance(value, dict) and value.keys() == {"boot_id", "monotonic_usec"}
            and isinstance(value["boot_id"], str) and re.fullmatch(r"[0-9a-f]{32}", value["boot_id"])
            and _valid_usec(value["monotonic_usec"])):
        return value["boot_id"], value["monotonic_usec"]
    return None, None


def _valid_span(start, end):
    return (isinstance(start, Boundary) and isinstance(end, Boundary)
            and isinstance(start.boot_id, str) and re.fullmatch(r"[0-9a-f]{32}", start.boot_id)
            and start.boot_id == end.boot_id and _valid_usec(start.monotonic_usec)
            and _valid_usec(end.monotonic_usec) and start.monotonic_usec < end.monotonic_usec
            and isinstance(start.token, str) and bool(start.token)
            and isinstance(end.token, str) and bool(end.token) and start.token != end.token)


def _span_identity(start, end, *, departed):
    span = [start.boot_id, start.token, start.monotonic_usec, end.token, end.monotonic_usec]
    return ["departed", *span] if departed else span


def _send(**fields):
    payload = "".join(f"{key}={value}\n" for key, value in fields.items())
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as journal:
        journal.settimeout(1)
        journal.sendto(payload.encode("ascii"), JOURNAL_SOCKET)


def _records(boot, *matches, cursor=None, awaiting_marker=False, limit=MAX_ROWS, timeout=3):
    # Read forward from the cursor. journalctl caps the row count and its JSON
    # output bounds individual fields. A clipped span cannot contain its seal.
    command = [
        "/usr/bin/journalctl", "--quiet", "--no-pager", f"--lines=+{limit}", f"--boot={boot}",
        "--output=json", f"--output-fields={FIELDS}",
    ]
    if cursor is not None:
        command.append(f"--cursor={cursor}")
    reason = ""
    try:
        result = subprocess.run([*command, *matches], stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=timeout,
                                env={**os.environ, "LC_ALL": "C"})
        stdout, stderr = result.stdout, result.stderr
        empty = result.returncode == 1 and not stdout and not stderr
        if (result.returncode != 0 or stderr) and not (awaiting_marker and empty):
            reason = _Reason.QUERY
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.output or b"", error.stderr or b""
        reason = _Reason.QUERY
    except (OSError, subprocess.SubprocessError):
        return [], _Reason.QUERY
    if len(stdout) + len(stderr) > MAX_OUTPUT:
        reason = _Reason.BOUND
    records = []
    for line in stdout[:MAX_OUTPUT].splitlines():
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            record = None
        if not isinstance(record, dict):
            record = None
        records.append(record)
    return records, reason


def capture_boundary():
    if os.geteuid() != 0:
        raise EvidenceUnavailable(_Reason.AUTHORIZATION)
    boot = _boot()
    token = secrets.token_hex(16)
    deadline = time.monotonic() + 4
    try:
        _send(MESSAGE="Oh No! Parent Control test boundary", **{FENCE: token})
    except OSError as error:
        raise EvidenceUnavailable(_Reason.FENCE_SEND) from error
    while (remaining := deadline - time.monotonic()) > 0:
        records, reason = _records(boot, "_TRANSPORT=journal", "_UID=0", f"{FENCE}={token}",
                                   awaiting_marker=True, timeout=min(3, remaining))
        if reason:
            raise EvidenceUnavailable(reason)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if records:
            if any(record is None for record in records):
                raise EvidenceUnavailable(_Reason.OUTPUT)
            if len(records) != 1:
                raise EvidenceUnavailable(_Reason.FENCE_PROVENANCE)
            record = records[0]
            cursor = record.get("__CURSOR")
            if (record.get("_PID") != str(os.getpid()) or record.get("_BOOT_ID") != boot
                    or record.get(FENCE) != token or record.get("_UID") != "0"
                    or record.get("_TRANSPORT") != "journal"
                    or not isinstance(cursor, str) or not cursor):
                raise EvidenceUnavailable(_Reason.FENCE_PROVENANCE)
            occurred = _usec(record, "__MONOTONIC_TIMESTAMP")
            if not _valid_usec(occurred):
                raise EvidenceUnavailable(_Reason.TIME)
            return Boundary(boot, occurred, cursor, token)
        time.sleep(min(0.05, remaining))
    raise EvidenceUnavailable(_Reason.FENCE_TIMEOUT)


def capture_boot_origin():
    """Require the kernel's first startup record on a newly owned boot."""
    if os.geteuid() != 0:
        raise EvidenceUnavailable(_Reason.AUTHORIZATION)
    return _boot_origin(_boot())


def _boot_origin(boot):
    records, reason = _records(boot, "_TRANSPORT=kernel", limit=16)
    if reason:
        raise EvidenceUnavailable(reason)
    for record in records:
        if not isinstance(record, dict) or record.get("_BOOT_ID") != boot:
            raise EvidenceUnavailable(_Reason.OPEN)
        message, cursor = record.get("MESSAGE"), record.get("__CURSOR")
        if (record.get("_TRANSPORT") == "kernel" and isinstance(message, str)
                and message.startswith("Linux version ") and isinstance(cursor, str) and cursor):
            # Kernel startup messages can be imported later. Include product
            # events whose occurrence precedes that import on this boot.
            return Boundary(boot, 1, cursor, BOOT_ORIGIN)
    raise EvidenceUnavailable(_Reason.OPEN)


def _is_boundary(record, boundary):
    return (
        record.get("__CURSOR") == boundary.cursor
        and record.get(FENCE) == boundary.token
        and record.get("_BOOT_ID") == boundary.boot_id
        and record.get("_TRANSPORT") == "journal"
        and record.get("_UID") == "0"
        and record.get("__MONOTONIC_TIMESTAMP") == str(boundary.monotonic_usec)
    )


def _matches(*groups):
    matches = []
    for group in groups:
        if matches:
            matches.append("+")
        matches.extend(group)
    return matches


def _records_from_start(start, *groups, fences, require_exhausted=False):
    boot_origin = start.token == BOOT_ORIGIN
    fences = [("_TRANSPORT=journal", "_UID=0", f"{FENCE}={marker.token}")
              for marker in (start, *fences) if marker is not None and marker.token != BOOT_ORIGIN]
    # Read from the start of this boot rather than from the kernel cursor:
    # kernel startup records can be imported after the first product record.
    records, reason = _records(start.boot_id, *_matches(*fences, *groups),
                               cursor=None if boot_origin else start.cursor,
                               limit=MAX_ROWS + int(require_exhausted))
    if require_exhausted and len(records) > MAX_ROWS:
        reason = reason or _Reason.BOUND
    if boot_origin:
        try:
            if _boot_origin(start.boot_id) != start:
                reason = reason or _Reason.OPEN
        except EvidenceUnavailable as error:
            reason = reason or str(error)
    elif records and records[0] is not None and _is_boundary(records[0], start):
        records = records[1:]
    else:
        reason = reason or _Reason.OPEN
    return records, reason


def _closed_span(start, end, settle, *groups):
    if os.geteuid() != 0:
        return [], _Reason.AUTHORIZATION
    if not _valid_span(start, end) or start.boot_id != _boot():
        return [], _Reason.SPAN
    if settle is not None and not _valid_span(end, settle):
        settle = None
    records, reason = _records_from_start(start, *groups, fences=(end, settle))
    inside, found_end = [], False
    for record in records:
        if record is None:
            reason = reason or _Reason.OUTPUT
            continue
        if record.get("_BOOT_ID") != start.boot_id:
            reason = reason or _Reason.BOOT
            continue
        if _is_boundary(record, end):
            found_end = True
        elif settle is not None and _is_boundary(record, settle):
            return inside, reason or ("" if found_end else _Reason.CLOSE)
        elif not _is_boundary(record, start):
            inside.append(record)
    return inside, reason or _Reason.CLOSE


def _departed_span(start, fence, *groups):
    if os.geteuid() != 0:
        return [], _Reason.AUTHORIZATION
    if not _valid_span(start, fence) or start.boot_id == _boot():
        return [], _Reason.SPAN
    records, reason = _records_from_start(
        start, *groups, tuple(f"{key}={value}" for key, value in REBOOT_REACHED.items()),
        (*(f"{key}={value}" for key, value in JOURNAL_DRIVER.items()),
         f"MESSAGE_ID={JOURNAL_STARTED}", f"MESSAGE_ID={JOURNAL_STOPPED}"),
        fences=(fence,), require_exhausted=True,
    )
    # Authenticate the pre-request fence, PID 1's completed reboot job and the
    # journal's last orderly stop, in order. Keep projecting verified product
    # records across the whole old boot even when its closing proof is missing.
    inside, found_fence, reached_reboot, stopped = [], False, False, False
    for record in records:
        if record is None:
            reason = reason or _Reason.OUTPUT
            continue
        if record.get("_BOOT_ID") != start.boot_id:
            reason = reason or _Reason.BOOT
            continue
        stopped = (reached_reboot and record.get("MESSAGE_ID") == JOURNAL_STOPPED
                   and all(record.get(key) == value for key, value in JOURNAL_DRIVER.items()))
        if _is_boundary(record, fence):
            found_fence = True
        elif all(record.get(key) == value for key, value in REBOOT_REACHED.items()):
            reached_reboot = found_fence
        elif not _is_boundary(record, start):
            inside.append(record)
    return inside, reason or ("" if stopped else _Reason.DEPARTURE)


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


def _role_uid(record, expected):
    uid = record.get("_UID")
    if expected is not None:
        return uid == expected
    return isinstance(uid, str) and re.fullmatch(r"[1-9][0-9]{0,9}", uid) is not None


def _source(record, parent_uid, child_uid, kiosk_uid):
    user_unit = record.get("_SYSTEMD_USER_UNIT")
    if _from_broker(record):
        return "broker", "broker"
    if _role_uid(record, parent_uid) and _python_script(record, "/usr/bin/oh-no-parent-control-parent"):
        return "parent", "gtk"
    if (_role_uid(record, kiosk_uid) and user_unit == KIOSK_APP_UNIT
            and _python_script(record, "/usr/bin/oh-no-parent-control")):
        return "kiosk", "gtk"
    if _role_uid(record, child_uid):
        if (record.get("_EXE") == "/usr/bin/gnome-shell" and isinstance(user_unit, str)
                and re.fullmatch(r"org\.gnome\.Shell(?:@[A-Za-z0-9_.-]+)?\.service", user_unit)):
            return "child", "gnome-shell"
        if _python_script(record, "/usr/bin/oh-no-parent-control-child"):
            return "child", "gtk"
    return None


def _os_fault(record, child_uid, kiosk_uid):
    if (record.get("_TRANSPORT") == "stdout" and record.get("MESSAGE") == BROKER_STARTUP_FAILURE
            and _from_broker(record)):
        return "broker", "startup", "systemd"
    child = _role_uid(record, child_uid)
    kiosk = _role_uid(record, kiosk_uid)
    if not (child or kiosk):
        return None
    try:
        # These supplemental projections use the existing support observer
        # when installed. Native reads and the bootstrap marker stand alone.
        from oh_no_parent_control.dependency_diagnostics import _gnome_shell_event, _kiosk_session_event

        uid = int(record["_UID"])
        session = _kiosk_session_event(record, uid) if kiosk else None
        if session is not None and session[0] == "app-exit" and session[2] != 0:
            return "kiosk", "unexpected", "systemd"
        shell = _gnome_shell_event(record, uid) if child else None
        if (shell is not None and shell[0] == "extension-manager.shell-journal"
                and shell[1]["candidate"] == "our-extension"):
            return "child", "shell-extension-load", "shell-log"
    except (ImportError, OSError, ValueError):
        return None
    return None


def _in_span(start, end, occurred):
    return start.monotonic_usec <= occurred and (end is None or occurred < end.monotonic_usec)


def _record_failure(record, start, end, *, parent_uid, child_uid, kiosk_uid):
    message = record.get("MESSAGE")
    if (record.get("_UID") == "0" and record.get("_COMM") == "systemd-journal"
            and isinstance(message, str) and message.startswith(("Suppressed ", "Missed "))
            and start.monotonic_usec <= _usec(record, "__MONOTONIC_TIMESTAMP")):
        raise EvidenceUnavailable(_Reason.LOSS)
    if record.get("_TRANSPORT") == "journal" and (
            "ONPC_FAILURE_VERSION" in record or "ONPC_COMPONENT" in record or message == MESSAGE):
        producer = _source(record, parent_uid, child_uid, kiosk_uid)
        if producer is None:
            return None, True
        component, source = producer
        occurred = _usec(record, OCCURRENCE)
        if not 0 < occurred <= _usec(record, "__MONOTONIC_TIMESTAMP"):
            raise EvidenceUnavailable(_Reason.OCCURRENCE)
        if not _in_span(start, end, occurred):
            return None, False
        if record.get("ONPC_FAILURE_VERSION") != "1":
            raise EvidenceUnavailable(_Reason.FORMAT)
        if record.get("ONPC_COMPONENT") != component:
            raise EvidenceUnavailable(_Reason.HEADER)
        category = record.get("ONPC_FAILURE_CATEGORY")
        if not isinstance(category, str) or CATEGORY.fullmatch(category) is None:
            raise EvidenceUnavailable(_Reason.CATEGORY)
        return Event(component, category, occurred, source), False
    fault = _os_fault(record, child_uid, kiosk_uid)
    if fault is not None:
        received = _usec(record, "__MONOTONIC_TIMESTAMP")
        if _in_span(start, end, received):
            component, category, source = fault
            return Event(component, category, received, source), False
    return None, False


def read_failures(start, end, *, parent_uid=None, child_uid=None, kiosk_uid=None, departed=False):
    parent_uid, child_uid, kiosk_uid = (
        None if uid is None else str(int(uid)) for uid in (parent_uid, child_uid, kiosk_uid)
    )
    groups = (
        ("_TRANSPORT=journal", f"MESSAGE={MESSAGE}"),
        ("_TRANSPORT=journal", "ONPC_FAILURE_VERSION=1"),
        ("_TRANSPORT=journal", *(f"ONPC_COMPONENT={component}" for component in COMPONENTS)),
        ("_TRANSPORT=stdout", "_UID=0", f"_SYSTEMD_UNIT={BROKER_UNIT}",
         f"MESSAGE={BROKER_STARTUP_FAILURE}"),
        ("_COMM=systemd", f"USER_UNIT={KIOSK_APP_UNIT}") if kiosk_uid is None
        else ("_UID=" + kiosk_uid, "_COMM=systemd"),
        ("_EXE=/usr/bin/gnome-shell",) if child_uid is None
        else ("_UID=" + child_uid, "_EXE=/usr/bin/gnome-shell"),
        ("_UID=0", "_COMM=systemd-journal"),
    )
    records, reason = [], ""
    try:
        if departed:
            records, reason = _departed_span(start, end, *groups)
        else:
            time.sleep(SETTLE_SECONDS)
            try:
                settle = capture_boundary()
            except EvidenceUnavailable as error:
                reason = evidence_reason(str(error), _Reason.CLOSE)
                settle = None
            except OSError:
                reason = _Reason.CLOSE
                settle = None
            records, span_reason = _closed_span(start, end, settle, *groups)
            reason = reason or span_reason
    except EvidenceUnavailable as error:
        reason = reason or str(error)
    except (OSError, ValueError, KeyError, TypeError):
        reason = reason or _Reason.MALFORMED
    events, unattributed = [], 0
    for record in records:
        try:
            event, missing_source = _record_failure(
                record, start, None if departed else end,
                parent_uid=parent_uid, child_uid=child_uid, kiosk_uid=kiosk_uid)
        except EvidenceUnavailable as error:
            reason = reason or str(error)
        except (ValueError, KeyError, TypeError):
            reason = reason or _Reason.MALFORMED
        else:
            if event is not None:
                events.append(event)
            unattributed += missing_source
    events.sort(key=lambda event: event.monotonic_usec)
    return {"complete": not reason, "events": [asdict(event) for event in events],
            "span": _span_identity(start, end, departed=departed) if _valid_span(start, end) else None,
            "unattributed": unattributed, "reason": str(reason)}


def evaluate_failures(observation, *, start, end, allowances=(), departed=False):
    """Apply case allowances to the reader's verified projection without I/O."""
    if not _valid_span(start, end):
        return FailureEvaluation(False, (), _Reason.SPAN, 0)
    if not isinstance(observation, dict):
        return FailureEvaluation(False, (), _Reason.MALFORMED, 0)
    if observation.get("span") != _span_identity(start, end, departed=departed):
        return FailureEvaluation(False, (), _Reason.SPAN, 0)
    reason = ""
    if observation.get("complete") is not True or observation.get("reason") != "":
        detail = observation.get("reason")
        reason = evidence_reason(detail, _Reason.MALFORMED)
    unattributed = observation.get("unattributed")
    if type(unattributed) is not int or unattributed < 0:
        reason = reason or _Reason.MALFORMED
        unattributed = 0
    events = observation.get("events")
    if not isinstance(events, list):
        return FailureEvaluation(False, (), reason or _Reason.MALFORMED, unattributed)
    windows = []
    for allowance in allowances:
        if (isinstance(allowance, Allowance) and start.monotonic_usec <= allowance.start_usec
                and allowance.end_usec <= end.monotonic_usec):
            windows.append(allowance)
        else:
            reason = reason or _Reason.ALLOWANCE
    unexpected = []
    for item in events:
        occurred = item.get("monotonic_usec") if isinstance(item, dict) else None
        if not _valid_usec(occurred):
            reason = reason or _Reason.OCCURRENCE
            continue
        if not _in_span(start, None if departed else end, occurred):
            continue
        component, category, source = (item.get(key) for key in ("component", "category", "source"))
        if (not isinstance(component, str) or source not in SOURCES.get(component, ())
                or not isinstance(category, str) or CATEGORY.fullmatch(category) is None):
            reason = reason or _Reason.MALFORMED
            continue
        event = Event(component, category, occurred, source)
        if not any(allowance.matches(event) for allowance in windows):
            unexpected.append(event)
    unexpected.sort(key=lambda event: event.monotonic_usec)
    return FailureEvaluation(not reason, tuple(unexpected), str(reason), unattributed)


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
    rows, reason = _closed_span(start, end, settle, ("_UID=0", "_TRANSPORT=journal", f"{PROBE}={token}"))
    if (reason or len(rows) != 1 or _usec(rows[0], "__MONOTONIC_TIMESTAMP") < end.monotonic_usec
            or not _in_span(start, end, _usec(rows[0], OCCURRENCE))):
        raise ValueError("late arrival lost its original case position")
    missing = Boundary(start.boot_id, start.monotonic_usec, start.cursor, secrets.token_hex(16))
    if read_failures(missing, end, parent_uid=0, child_uid=0, kiosk_uid=0)["complete"]:
        raise ValueError("missing journal span became a complete read")


def main():
    # The qualification stages this reader alongside other guest-only support.
    sys.path[:0] = ["/usr/lib/oh-no-parent-control/broker", "/usr/lib/oh-no-parent-control"]
    match sys.argv[1:]:
        case ["boundary" | "boot-origin" as mode, "report"]:
            try:
                capture = capture_boundary if mode == "boundary" else capture_boot_origin
                result = asdict(capture())
            except EvidenceUnavailable as error:
                result = {"reason": evidence_reason(str(error), _Reason.MALFORMED)}
            except OSError:
                result = {"reason": _Reason.QUERY}
            print(json.dumps(result))
        case ["boundary"]:
            print(json.dumps(asdict(capture_boundary())))
        case ["boot-origin"]:
            print(json.dumps(asdict(capture_boot_origin())))
        case ["read" | "read-departed" as mode, start, end]:
            result = read_failures(Boundary(**json.loads(start)), Boundary(**json.loads(end)),
                                   departed=mode == "read-departed")
            print(json.dumps(result))
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
