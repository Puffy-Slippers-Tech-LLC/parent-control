"""Bounded read of a child's saved Mutter monitor layout for the kiosk."""

from __future__ import annotations

import os
import pwd
import stat

MAX_MONITORS_CONFIG_BYTES = 64 * 1024
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
_NO_FOLLOW = os.O_NOFOLLOW | os.O_NONBLOCK


def _owned(descriptor: int, uid: int, kind) -> os.stat_result:
    status = os.fstat(descriptor)
    if status.st_uid != uid or not kind(status.st_mode):
        raise PermissionError("monitor configuration is not owned by the child")
    return status


def read_monitors_config(uid: int, account_lookup=pwd.getpwuid) -> str:
    """Return the child's ``~/.config/monitors.xml`` text, or "" when absent.

    The broker reads as root, so components below the account's home are opened
    without following links and must be owned by the child. A planted link or
    foreign file is refused rather than disclosed to the kiosk.
    """
    descriptors = []
    try:
        try:
            descriptors.append(os.open(account_lookup(uid).pw_dir, _DIRECTORY))
            _owned(descriptors[-1], uid, stat.S_ISDIR)
            descriptors.append(os.open(".config", _DIRECTORY | _NO_FOLLOW, dir_fd=descriptors[-1]))
            _owned(descriptors[-1], uid, stat.S_ISDIR)
            descriptors.append(os.open("monitors.xml", os.O_RDONLY | os.O_CLOEXEC | _NO_FOLLOW,
                                       dir_fd=descriptors[-1]))
        except FileNotFoundError:
            return ""
        status = _owned(descriptors[-1], uid, stat.S_ISREG)
        if status.st_size > MAX_MONITORS_CONFIG_BYTES:
            raise ValueError("monitor configuration is too large")
        data = b""
        while chunk := os.read(descriptors[-1], MAX_MONITORS_CONFIG_BYTES + 1 - len(data)):
            data += chunk
            if len(data) > MAX_MONITORS_CONFIG_BYTES:
                raise ValueError("monitor configuration is too large")
        return data.decode("utf-8")
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
