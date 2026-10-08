"""Read-only, closed-field observations of runtime dependencies for feedback.

Journal messages are inspected transiently, never attached or logged verbatim.
Invocation identifiers only relate journal entries to the observed service;
they are not emitted. Earlier attempts on this boot remain available after
automatic recovery or a manual restart.
"""

from datetime import datetime, timezone
import json
import os
import re
import selectors
import subprocess
import time

from common.oh_no_parent_control_ui.diagnostic_events import get_logger

LOG = get_logger("execution-policy")
MAX_OUTPUT = 256 * 1024
DEPENDENCIES = {"fapolicyd.service": "fapolicyd",
                "accounts-daemon.service": "accounts-service",
                "polkit.service": "polkit", "systemd-logind.service": "logind"}
PROPERTIES = ("Id", "LoadState", "ActiveState", "Result", "ExecMainCode", "ExecMainStatus",
              "Restart", "NRestarts", "InvocationID")


def _run_bounded(command, timeout):
    """Cap both pipes while reading; always reap the command we launched."""
    deadline = time.monotonic() + timeout
    output, errors = bytearray(), bytearray()
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, bufsize=0,
                          env={**os.environ, "LC_ALL": "C"}) as process:
        try:
            with selectors.DefaultSelector() as selector:
                for stream, buffer in ((process.stdout, output), (process.stderr, errors)):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, buffer)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    for key, _events in selector.select(remaining):
                        chunk = os.read(key.fd, min(65536, MAX_OUTPUT + 1 - len(output) - len(errors)))
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        key.data.extend(chunk)
                        if len(output) + len(errors) > MAX_OUTPUT:
                            raise ValueError()
            status = process.wait(timeout=max(0, deadline - time.monotonic()))
        except BaseException:
            process.kill()
            process.wait()
            raise
    return subprocess.CompletedProcess(command, status, output.decode("utf-8"), errors.decode("utf-8"))


def _query(command, deadline, *, empty_match=False):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    result = _run_bounded(command, min(3, remaining))
    no_matches = empty_match and result.returncode == 1 and not result.stdout and not result.stderr
    if (result.returncode != 0 and not no_matches) or len(result.stdout) > MAX_OUTPUT:
        raise ValueError()
    return result.stdout


def _category(value, choices):
    return value if value in choices else "unknown"


def _number(value, maximum):
    if type(value) is str and re.fullmatch(r"[0-9]{1,10}", value):
        number = int(value)
        if number <= maximum:
            return number
    return maximum + 1


def _journal_event(message):
    # Exact shipped-daemon markers only. No generic error/path extraction.
    if message == "Updating trust database":
        return "trust-update-started", 0
    if message == "Cannot update trust database!":
        return "trust-update-failed", 0
    if message == "db_max_size needs to be increased":
        return "trust-capacity-exhausted", 0
    if type(message) is str:
        match = re.fullmatch(r"Cannot delete database \(([1-4])\)", message)
        if match:
            return "trust-delete-failed", int(match[1])
    return None


def _service_states(output):
    states = {}
    for block in output.strip().split("\n\n"):
        properties = {}
        for line in block.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in PROPERTIES and key not in properties:
                properties[key] = value
            else:
                raise ValueError()
        if properties.keys() != set(PROPERTIES):
            raise ValueError()
        unit = properties["Id"]
        if unit not in DEPENDENCIES or unit in states:
            raise ValueError()
        states[unit] = properties
    if states.keys() != DEPENDENCIES.keys():
        raise ValueError()
    return states


def collect_dependency_diagnostics():
    """Best effort, five-second budget; no service/database/policy mutations.

    Always runs during feedback collection, including diagnostics-only mode. A
    failed source is explicit and cannot prevent the customer report from opening.
    """
    deadline = time.monotonic() + 5
    invocation = None
    try:
        output = _query([
            "/usr/bin/systemctl", "show", *DEPENDENCIES, "--no-pager",
            "--property=" + ",".join(PROPERTIES),
        ], deadline)
        states = _service_states(output)
        candidate = states["fapolicyd.service"]["InvocationID"]
        if re.fullmatch(r"[0-9a-f]{32}", candidate):
            invocation = candidate
        for unit, properties in states.items():
            LOG.info(
                "execution-policy.backend-state",
                dependency=DEPENDENCIES[unit],
                loaded=_category(properties["LoadState"], (
                    "loaded", "not-found", "masked", "error", "bad-setting")),
                active=_category(properties["ActiveState"], (
                    "active", "inactive", "failed", "activating", "deactivating", "reloading")),
                result=_category(properties["Result"], (
                    "success", "exit-code", "signal", "core-dump", "timeout", "oom-kill",
                    "start-limit-hit", "resources", "protocol", "watchdog")),
                restart=_category(properties["Restart"], (
                    "no", "always", "on-success", "on-failure", "on-abnormal", "on-abort", "on-watchdog")),
                exit_kind={"0": "none", "1": "exited", "2": "killed", "3": "dumped"}.get(
                    properties["ExecMainCode"], "unknown"),
                exit_status=_number(properties["ExecMainStatus"], 255),
                restarts=_number(properties["NRestarts"], 2147483646),
            )
    except Exception:
        LOG.warning("execution-policy.backend-observation", source="service", outcome="unavailable", count=0)
    try:
        output = _query([
            "/usr/bin/journalctl", "--unit=fapolicyd.service", "--no-pager", "--quiet",
            "--output=json", "--lines=200", "--since=-24hours", "--boot=0",
            "--output-fields=MESSAGE,__REALTIME_TIMESTAMP,_SYSTEMD_INVOCATION_ID,_EXE",
            "--grep=^(Updating trust database|Cannot update trust database!|"
            "Cannot delete database \\([1-4]\\)|db_max_size needs to be increased)$",
        ], deadline, empty_match=True)
        selected = []
        partial = invocation is None
        lines = output.splitlines()
        for line in lines:
            try:
                item = json.loads(line)
                if (type(item) is not dict or
                        item.get("_EXE") not in ("/usr/sbin/fapolicyd", "/usr/bin/fapolicyd")):
                    continue
                source_invocation = item.get("_SYSTEMD_INVOCATION_ID")
                if (type(source_invocation) is not str or
                        not re.fullmatch(r"[0-9a-f]{32}", source_invocation)):
                    partial = True
                    continue
                marker = _journal_event(item.get("MESSAGE"))
                if marker is None:
                    continue
                stamp = item.get("__REALTIME_TIMESTAMP")
                if type(stamp) is not str or not re.fullmatch(r"[0-9]{1,17}", stamp):
                    raise ValueError()
                occurred = datetime.fromtimestamp(int(stamp) / 1000000, timezone.utc)
                selected.append((marker, occurred.isoformat(timespec="milliseconds"),
                                 ("other" if invocation is None else
                                  "current" if source_invocation == invocation else "previous")))
            except (ValueError, TypeError, OverflowError, OSError):
                partial = True
        # A full tail may have omitted earlier evidence. Never claim completeness.
        partial = partial or len(lines) >= 200 or len(selected) > 20
        for (reason, code), occurred, relation in selected[-20:]:
            LOG.info("execution-policy.backend-journal", reason=reason,
                     diagnostic_code=code, occurred_at=occurred, invocation_relation=relation)
        LOG.info("execution-policy.backend-observation", source="journal",
                 outcome="partial" if partial else "complete", count=min(len(selected), 20))
    except Exception:
        LOG.warning("execution-policy.backend-observation", source="journal", outcome="unavailable", count=0)


def notification_error_reason(stderr):
    """Reduce the CLI's C-locale FIFO errors to closed categories."""
    if type(stderr) is not str or len(stderr) > 8192:
        return "other"
    for reason, suffix in (("notification-endpoint-missing", "No such file or directory"),
                           ("notification-permission-denied", "Permission denied"),
                           ("notification-reader-missing", "No such device or address")):
        if stderr.strip() == "Open: /run/fapolicyd/fapolicyd.fifo -> " + suffix:
            return reason
    return "other"
