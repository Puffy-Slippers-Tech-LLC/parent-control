"""Bounded schema-validated diagnostic history; no free-form log storage."""

import logging
import os
from pathlib import Path
import stat
import threading
import time
from datetime import datetime, date, timezone
from collections import OrderedDict, deque
import uuid

from common.oh_no_parent_control_ui.diagnostic_events import (
    COMPONENTS, LEVELS, decode, encode, record_payload,
)

LOG_ROOT = Path("/var/log/oh-no-parent-control")
RETENTION_DAYS = 3
MAX_MESSAGE_LENGTH = 4096
MAX_FILE_BYTES = 262144
MAX_SEGMENTS = 3


class DailyLogWriter:
    def __init__(self, root=LOG_ROOT, *, now=lambda: datetime.now(timezone.utc),
                 monotonic=time.monotonic):
        self.root = Path(root)
        self._now = now
        self._clock = monotonic
        self._started = monotonic()
        self._segment = str(uuid.uuid4())
        self._sequence = 0
        self._lock = threading.RLock()
        self._recent = OrderedDict()
        self._suppressed = 0
        self._rotations = 0
        self._incidents = 0
        self._write_failures = 0
        self._storage_available = True
        self._history = {component: deque(maxlen=40) for component in COMPONENTS}
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in COMPONENTS:
                try:
                    os.mkdir(component, mode=0o750, dir_fd=root_fd)
                except FileExistsError:
                    pass
                fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=root_fd)
                os.close(fd)
        finally:
            os.close(root_fd)

    def _open_component(self, component):
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            return os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=root_fd)
        finally:
            os.close(root_fd)

    def _append(self, directory_fd, filename, record):
        data = (encode(record) + "\n").encode("ascii")
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(filename, flags, 0o640, dir_fd=directory_fd)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise ValueError("Unsupported diagnostic file")
            if meta.st_size + len(data) > MAX_FILE_BYTES:
                os.close(fd)
                fd = -1
                for suffix in range(MAX_SEGMENTS - 1, 0, -1):
                    previous = filename if suffix == 1 else f"{filename}.{suffix - 1}"
                    try:
                        os.rename(previous, f"{filename}.{suffix}",
                                  src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
                    except FileNotFoundError:
                        pass
                fd = os.open(filename, flags | os.O_EXCL, 0o640, dir_fd=directory_fd)
                self._rotations += 1
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if not written:
                    raise OSError("Diagnostic write failed")
                view = view[written:]
        finally:
            if fd >= 0:
                os.close(fd)

    def write(self, component, level, message, *, source_uid=None):
        if component not in COMPONENTS or component == "broker" and source_uid is not None:
            raise ValueError("Invalid diagnostic component")
        if level not in LEVELS:
            raise ValueError("Invalid diagnostic level")
        safe = decode(message, component=component)
        now = self._clock()
        with self._lock:
            key = (component, encode(safe))
            prior = self._recent.get(key)
            if prior is not None and now - prior < 60:
                self._suppressed += 1
                return
            self._recent[key] = now
            self._recent.move_to_end(key)
            while len(self._recent) > 256:
                self._recent.popitem(last=False)
            self._sequence += 1
            observed_at = self._now().astimezone(timezone.utc)
            record = {**safe, "component": component, "level": level,
                      "sequence": self._sequence, "segment": self._segment,
                      "timestamp": observed_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                      "elapsed_ms": max(0, int((now - self._started) * 1000))}
            self._history[component].append(record)
            directory_fd = self._open_component(component)
            try:
                filename = observed_at.date().isoformat() + ".events"
                self._append(directory_fd, filename, record)
                # Existing .log files are never read, imported or removed here.
                dated = sorted({name[:10] for name in os.listdir(directory_fd)
                                if _event_filename(name)})
                expired = set(dated[:-RETENTION_DAYS])
                for name in os.listdir(directory_fd):
                    if _event_filename(name) and name[:10] in expired:
                        os.unlink(name, dir_fd=directory_fd)
            finally:
                os.close(directory_fd)
            unexpected_increase = (
                safe["event"] in ("grant.observed", "grant.observed-timed")
                and safe["fields"]["source"] in ("unattributed", "external", "unknown")
                and safe["fields"]["remaining"] > safe["fields"]["previous"]
            )
            if (LEVELS[level] >= LEVELS["ERROR"] or unexpected_increase
                    or safe["event"] in ("errors.001", "child.error", "grant.invalid", "grant.clock-divergence")):
                self._incidents += 1
                self._capture_incident()
            self._storage_available = True

    def _capture_incident(self):
        """Keep the latest error context even if later polling rotates history."""
        for component, history in self._history.items():
            if not history:
                continue
            directory_fd = self._open_component(component)
            temporary = ".incident-" + str(uuid.uuid4())
            created = False
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o640, dir_fd=directory_fd)
                created = True
                try:
                    data = memoryview("".join(encode(item) + "\n" for item in history).encode("ascii"))
                    while data:
                        written = os.write(fd, data)
                        if not written:
                            raise OSError("Diagnostic incident write failed")
                        data = data[written:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.replace(temporary, self._now().astimezone(timezone.utc).date().isoformat() + ".incident.events",
                           src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            finally:
                try:
                    if created:
                        os.unlink(temporary, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                os.close(directory_fd)

    def summary(self):
        with self._lock:
            return {"suppressed": self._suppressed, "rotations": self._rotations,
                    "incidents": self._incidents, "write_failures": self._write_failures}

    def write_failed(self):
        with self._lock:
            self._write_failures += 1
            self._storage_available = False

    def storage_state(self):
        with self._lock:
            return "available" if self._storage_available else "unavailable"

    def snapshot(self, *, health=None):
        from .diagnostics import collect_logs
        with self._lock:
            return collect_logs(self.root, health=health, summary=self.summary())


def _event_filename(name):
    try:
        return (name[10:] in (".events", ".events.1", ".events.2", ".incident.events")
                and date.fromisoformat(name[:10]).isoformat() == name[:10])
    except ValueError:
        return False


class BrokerFileHandler(logging.Handler):
    def __init__(self, writer):
        super().__init__()
        self.writer = writer

    def emit(self, record):
        try:
            self.writer.write("broker", record.levelname, record_payload(record))
        except Exception:
            # handleError dumps the offending record and exception.
            try:
                self.writer.write_failed()
            except Exception:
                pass


def configure_broker_logging(writer):
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(BrokerFileHandler(writer))
    root.setLevel(logging.INFO)
