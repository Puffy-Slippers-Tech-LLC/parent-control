"""Checkout-wide advisory ownership for the maintained test launchers.

An inherited, locked descriptor permits the aggregate's own category children.
An environment variable without that descriptor cannot bypass a competing run.
This is coordination among trusted launchers, not a privilege boundary.
"""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat

VARIABLE = 'ONPC_TEST_ACTIVITY_FD'
_descriptor = None


def descriptors():
    return () if _descriptor is None else (_descriptor,)


def environment():
    return {} if _descriptor is None else {VARIABLE: str(_descriptor)}


def record_cleanup(source):
    """Publish a passed aggregate cleanup gate to this lock's own children.

    This is an ephemeral coordination record, not durable evidence or a
    privileged-run authorization. A new independent activity clears it.
    """
    if _descriptor is None:
        return
    if len(source) != 64 or any(char not in '0123456789abcdef' for char in source):
        raise ValueError('invalid cleanup source identity')
    payload = source.encode('ascii')
    if os.pwrite(_descriptor, payload, 0) != len(payload):
        raise OSError('incomplete cleanup coordination record')
    os.ftruncate(_descriptor, len(payload))


def cleanup_verified(root):
    """Reuse only a gate from the current inherited activity and same inputs."""
    if _descriptor is None:
        return False
    payload = os.pread(_descriptor, 65, 0)
    if not payload:
        return False
    # Ordinary and privileged launcher startup only needs activity ownership;
    # load aggregate provenance support when a reusable host gate exists.
    from regression_inputs import identity as source_identity
    if (len(payload) != 64 or any(char not in b'0123456789abcdef' for char in payload)
            or payload.decode('ascii') != source_identity(root)):
        raise ValueError('aggregate cleanup prerequisites no longer match source inputs')
    return True


@contextmanager
def activity(root):
    global _descriptor
    directory = Path(root) / 'artifacts/test-activity'
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError('test activity path contains a symlink')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'lock'
    opened = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    inherited = None
    previous = _descriptor
    try:
        identity = os.fstat(opened)
        if (not stat.S_ISREG(identity.st_mode) or identity.st_uid != os.geteuid()
                or stat.S_IMODE(identity.st_mode) != 0o600 or identity.st_nlink != 1):
            raise ValueError('unsafe test activity lock')
        value = os.environ.get(VARIABLE)
        if previous is not None:
            inherited = previous
        elif value is not None:
            if not value.isdecimal() or int(value) < 3:
                raise ValueError('invalid inherited test activity descriptor')
            inherited = int(value)
        if inherited is not None:
            other = os.fstat(inherited)
            if (other.st_dev, other.st_ino) != (identity.st_dev, identity.st_ino):
                raise ValueError('foreign test activity descriptor')
        descriptor = opened if inherited is None else inherited
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('another test launcher owns this checkout; wait for its cleanup') from error
        if inherited is None:
            # Never reuse a previous invocation's passing gate, including after
            # an interrupted/crashed aggregate that left its lock file behind.
            os.ftruncate(descriptor, 0)
        _descriptor = descriptor
        os.set_inheritable(descriptor, True)
        yield
    finally:
        _descriptor = previous
        os.close(opened)
