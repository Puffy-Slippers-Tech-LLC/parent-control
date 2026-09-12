"""Export only validated diagnostic records, never existing text logs or journals."""

from datetime import date, datetime, timezone
import json
import os
import stat
import uuid

from common.oh_no_parent_control_ui.diagnostic_bundle import validate_record, MAX_RECORDS
from common.oh_no_parent_control_ui.diagnostic_report import build_report
from .logs import _event_filename

LOG_ROOT = "/var/log/oh-no-parent-control"
MAX_BYTES = 16 * 1024 * 1024
COMPONENTS = ("broker", "parent", "child", "kiosk")


def collect_logs(root=LOG_ROOT, today=None, *, health=None, summary=None):
    today = today or datetime.now(timezone.utc).date()
    counts = dict(summary or {})
    counts.update(invalid=0, truncated=0, missing=0)
    records, segments, pinned = [], {}, set()
    record_files, logs = {}, {}
    total = 0
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(root, flags)
    try:
        dates = {}
        for component in COMPONENTS:
            try:
                fd = os.open(component, flags, dir_fd=root_fd)
            except FileNotFoundError:
                counts["missing"] += 1
                continue
            try:
                dates[component] = sorted({name[:10] for name in os.listdir(fd)
                    if _event_filename(name) and date.fromisoformat(name[:10]) <= today})[-3:]
            finally:
                os.close(fd)
        for day in sorted({day for days in dates.values() for day in days}):
            for component in COMPONENTS:
                if day not in dates.get(component, ()):
                    continue
                try:
                    fd = os.open(component, flags, dir_fd=root_fd)
                except FileNotFoundError:
                    continue
                try:
                    for suffix in (".incident.events", ".events.2", ".events.1", ".events"):
                        if total >= MAX_BYTES:
                            counts["truncated"] += 1
                            continue
                        name = day + suffix
                        try:
                            source_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                                dir_fd=fd)
                        except FileNotFoundError:
                            continue
                        with os.fdopen(source_fd, "rb") as source:
                            metadata = os.fstat(source.fileno())
                            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                                raise ValueError("Unsupported diagnostic file")
                            log_name = f"{component}/{day}.log"
                            logs.setdefault(log_name, [])
                            while True:
                                line = source.readline(8193)
                                if not line:
                                    break
                                total += len(line)
                                if total > MAX_BYTES:
                                    counts["truncated"] += 1
                                    break
                                if len(line) > 8192:
                                    counts["invalid"] += 1
                                    break
                                try:
                                    item = json.loads(line)
                                    # Segment references are generated afresh by the
                                    # writer, never an OS boot/session/device ID.
                                    segment = item["segment"]
                                    if (type(segment) is not str or len(segment) != 36
                                            or str(uuid.UUID(segment)) != segment
                                            or uuid.UUID(segment).version != 4):
                                        raise ValueError("Invalid diagnostic segment")
                                    item["segment"] = segments.setdefault(segment, len(segments) + 1)
                                    item = validate_record(item)
                                    if item["component"] != component:
                                        raise ValueError("Invalid diagnostic component")
                                except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
                                    counts["invalid"] += 1
                                    continue
                                records.append(item)
                                key = (item["segment"], item["sequence"])
                                # Normal history establishes the source date when
                                # a later incident duplicates an earlier record.
                                if suffix != ".incident.events" or key not in record_files:
                                    record_files[key] = log_name
                                if suffix == ".incident.events":
                                    pinned.add(key)
                finally:
                    os.close(fd)
    finally:
        os.close(root_fd)
    records = list({(item["segment"], item["sequence"]): item for item in records}.values())
    records.sort(key=lambda item: (item["segment"], item["sequence"]))

    def trim(discard):
        # Retain captured error context ahead of ordinary polling history.
        candidates = [item for item in records
                      if (item["segment"], item["sequence"]) not in pinned]
        candidates.extend(item for item in records
                          if (item["segment"], item["sequence"]) in pinned)
        removed = {(item["segment"], item["sequence"]) for item in candidates[:discard]}
        counts["truncated"] += len(removed)
        return [item for item in records if (item["segment"], item["sequence"]) not in removed]

    if len(records) > MAX_RECORDS:
        records = trim(len(records) - MAX_RECORDS)
    # Reserve room for a usable report even under an unusually busy history.
    while True:
        try:
            grouped = {name: [] for name in logs}
            for item in records:
                grouped[record_files[(item["segment"], item["sequence"])]].append(item)
            return build_report(grouped, health, counts)
        except ValueError as error:
            if str(error) != "Diagnostic attachment limit" or not records:
                raise
            discard = max(1, len(records) // 4)
            records = trim(discard)
