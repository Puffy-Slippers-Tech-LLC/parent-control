#!/usr/bin/python3
"""Read-only allocation inventory for explicit temporary-storage cleanup."""

import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import test_retention as retention


def size(fd):
    total = 0
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        total += info.st_blocks * 512
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                if retention.mount_id(child) != retention.mount_id(fd):
                    raise ValueError('mounted storage')
                total += size(child)
            finally:
                os.close(child)
    return total


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise ValueError('root dispatcher required')
    for path in sorted(Path('/tmp').iterdir()):
        if not path.name.startswith(('onpc-graphical-smoke-', 'onpc-e2e-evidence-',
                                     'onpc-e2e-watch-check-', 'onpc-system-recovery-')):
            continue
        fd = retention.directory(path)
        try:
            info = os.fstat(fd)
            retention.allocation_identity(info, 0o700)
            record = dict(path=str(path), device=info.st_dev, inode=info.st_ino,
                          mode=0o700, bytes=size(fd), mtime_ns=info.st_mtime_ns)
            print(json.dumps(record), flush=True)
        finally:
            os.close(fd)
    return 0


if __name__ == '__main__':
    sys.exit(main())
