"""Bounded, read-only export of dated product logs."""

from datetime import date, timedelta
from io import BytesIO
import os
from pathlib import Path
import stat
from zipfile import ZIP_DEFLATED, ZipFile

LOG_ROOT = Path("/var/log/oh-no-parent-control")
MAX_BYTES = 16 * 1024 * 1024
COMPONENTS = ("broker", "child", "parent", "kiosk")


def collect_logs(root=LOG_ROOT, today=None):
    """Return a ZIP containing only regular logs from three local calendar days."""
    today = today or date.today()
    output = BytesIO()
    total = 0
    count = 0
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        root_fd = os.open(root, directory_flags)
        try:
            for component in COMPONENTS:
                try:
                    component_fd = os.open(component, directory_flags, dir_fd=root_fd)
                except FileNotFoundError:
                    continue
                try:
                    for offset in range(3):
                        name = f"{today - timedelta(days=offset):%Y-%m-%d}.log"
                        try:
                            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                         dir_fd=component_fd)
                        except FileNotFoundError:
                            continue
                        with os.fdopen(fd, "rb") as source:
                            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                                raise ValueError("Unsupported log file")
                            content = source.read(MAX_BYTES - total + 1)
                        total += len(content)
                        if total > MAX_BYTES:
                            raise ValueError("Logs exceed export limit")
                        archive.writestr(f"{component}/{name}", content)
                        count += 1
                finally:
                    os.close(component_fd)
        finally:
            os.close(root_fd)
    if not count:
        raise ValueError("No recent logs available")
    if output.tell() > MAX_BYTES:
        raise ValueError("Archive exceeds export limit")
    return output.getvalue()
