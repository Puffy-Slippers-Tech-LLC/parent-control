"""Daily, component-separated troubleshooting logs owned by the broker."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path

LOG_ROOT = Path("/var/log/oh-no-parent-control")
COMPONENTS = frozenset({"parent", "child", "kiosk", "broker"})
LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
RETENTION_DAYS = 10
MAX_MESSAGE_LENGTH = 4096


class DailyLogWriter:
    def __init__(self, root=LOG_ROOT, *, now=lambda: datetime.now().astimezone()):
        self.root = Path(root)
        self._now = now
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
        for component in COMPONENTS:
            (self.root / component).mkdir(mode=0o750, exist_ok=True)

    def write(self, component: str, level: str, message: str, *, source_uid=None) -> None:
        if component not in COMPONENTS or component == "broker" and source_uid is not None:
            raise ValueError("invalid log component")
        if level not in LEVELS:
            raise ValueError("invalid log level")
        if not isinstance(message, str) or not message or len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError("invalid log message")

        now = self._now()
        date = now.date().isoformat()
        directory = self.root / component
        path = directory / f"{date}.log"
        clean_message = message.replace("\r", "\\r").replace("\n", "\\n")
        source = f" uid={source_uid}" if source_uid is not None else ""
        line = f"{now.isoformat(timespec='seconds')} {level}{source} {clean_message}\n"

        with self._lock:
            created = False
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL, 0o640)
                created = True
            except FileExistsError:
                descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            try:
                os.write(descriptor, line.encode("utf-8", errors="replace"))
            finally:
                os.close(descriptor)
            if created:
                self._prune(directory)

    @staticmethod
    def _prune(directory: Path) -> None:
        dated = []
        for path in directory.iterdir():
            if path.is_file() and path.suffix == ".log":
                try:
                    datetime.strptime(path.stem, "%Y-%m-%d")
                except ValueError:
                    continue
                dated.append(path)
        for path in sorted(dated, reverse=True)[RETENTION_DAYS:]:
            path.unlink()


class BrokerFileHandler(logging.Handler):
    def __init__(self, writer: DailyLogWriter):
        super().__init__()
        self.writer = writer

    def emit(self, record):
        try:
            self.writer.write("broker", record.levelname, self.format(record))
        except Exception:
            self.handleError(record)


def configure_broker_logging(writer: DailyLogWriter) -> None:
    handler = BrokerFileHandler(writer)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
