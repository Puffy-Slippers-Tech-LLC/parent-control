"""Scoped checkout advisory ownership for the maintained test launchers.

An inherited, locked descriptor permits the aggregate's own category children.
An environment variable without that descriptor cannot bypass a competing run.
This is coordination among trusted launchers, not a privilege boundary.
Host-only activity and retention are independent of VM-side operations.
"""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat

VARIABLE = 'ONPC_TEST_ACTIVITY_FD'
HOST_VARIABLE = 'ONPC_TEST_HOST_ACTIVITY_FD'
_descriptor = None
_host_descriptor = None
_host_only = False
_named_vm = False


def retention_path(root):
    from test_storage import directory, legacy_retention_guard
    from vm_selection import BATCH, selected
    vm = selected(required=False) if not _host_only else None
    suffix = ('-host' if _host_only else '-batch' if BATCH in os.environ else
              '-' + vm.name if vm else '')
    legacy = directory('state', root=root) / 'retention'
    if suffix and suffix != '-host':
        legacy_retention_guard(legacy)
    return legacy.with_name('retention' + suffix)


def descriptors():
    return tuple(fd for fd in (_descriptor, _host_descriptor) if fd is not None)


def environment():
    return {key: str(fd) for key, fd in ((VARIABLE, _descriptor), (HOST_VARIABLE, _host_descriptor))
            if fd is not None}


@contextmanager
def host_reservation(directory, required):
    """Mixed runs reserve the same host lock as independent host runs."""
    global _host_descriptor
    previous = _host_descriptor
    inherited = previous
    value = os.environ.get(HOST_VARIABLE)
    if inherited is None and value is not None:
        if not value.isdecimal() or int(value) < 3:
            raise ValueError('invalid inherited host activity descriptor')
        inherited = int(value)
    if not required and inherited is None:
        yield
        return
    opened = os.open(directory / 'host.lock',
                     os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(opened)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('unsafe host activity lock')
        if inherited is not None:
            other = os.fstat(inherited)
            if (info.st_dev, info.st_ino) != (other.st_dev, other.st_ino):
                raise ValueError('foreign host activity descriptor')
        descriptor = opened if inherited is None else inherited
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('another test launcher owns the host scope; wait for its cleanup') from error
        _host_descriptor = descriptor
        os.set_inheritable(descriptor, True)
        yield
    finally:
        _host_descriptor = previous
        os.close(opened)


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
    """Reuse a passed gate from the current inherited activity despite edits."""
    if _descriptor is None:
        return False
    payload = os.pread(_descriptor, 65, 0)
    if not payload:
        return False
    if len(payload) != 64 or any(char not in b'0123456789abcdef' for char in payload):
        raise ValueError('invalid aggregate cleanup coordination record')
    return True


@contextmanager
def activity(root, *, host_only=None, named_vm=None, includes_host=False):
    global _descriptor, _host_only, _named_vm
    directory = Path(root) / 'artifacts/test-activity'
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError('test activity path contains a symlink')
    directory.mkdir(parents=True, exist_ok=True)
    previous = _descriptor
    previous_host_only = _host_only
    previous_named_vm = _named_vm
    value = os.environ.get(VARIABLE)
    inherited = previous
    if inherited is None and value is not None:
        if not value.isdecimal() or int(value) < 3:
            raise ValueError('invalid inherited test activity descriptor')
        inherited = int(value)
    if host_only is None:
        host_only = previous_host_only if previous is not None else False
        if inherited is not None and previous is None:
            other = os.fstat(inherited)
            try:
                candidate = (directory / 'host.lock').lstat()
            except FileNotFoundError:
                pass
            else:
                host_only = (other.st_dev, other.st_ino) == (candidate.st_dev, candidate.st_ino)
    from vm_selection import selected
    vm = (selected(required=False) if not host_only and
          (named_vm or previous_named_vm or (inherited is not None and previous is None)) else None)
    if named_vm is None:
        named_vm = previous_named_vm if previous is not None else False
        if inherited is not None and previous is None and vm is not None:
            try:
                candidate = (directory / ('vm-' + vm.name + '.lock')).lstat()
            except FileNotFoundError:
                pass
            else:
                other = os.fstat(inherited)
                named_vm = (other.st_dev, other.st_ino) == (candidate.st_dev, candidate.st_ino)
    if named_vm and (host_only or vm is None):
        raise ValueError('named VM activity requires a selected VM')
    path = directory / ('host.lock' if host_only else
                        'vm-' + vm.name + '.lock' if named_vm else 'lock')
    compatibility = None
    opened = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        if named_vm:
            # Existing aggregate controllers retain exclusive checkout ownership;
            # independent named preparation owners may overlap each other only.
            compatibility = os.open(directory / 'lock',
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            info = os.fstat(compatibility)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise ValueError('unsafe test activity lock')
            try:
                fcntl.flock(compatibility, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('another test launcher owns this checkout; wait for its cleanup') from error
        identity = os.fstat(opened)
        if (not stat.S_ISREG(identity.st_mode) or identity.st_uid != os.geteuid()
                or stat.S_IMODE(identity.st_mode) != 0o600 or identity.st_nlink != 1):
            raise ValueError('unsafe test activity lock')
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
        _host_only = host_only
        _named_vm = named_vm
        os.set_inheritable(descriptor, True)
        with host_reservation(directory, includes_host and not host_only):
            yield
    finally:
        _descriptor = previous
        _host_only = previous_host_only
        _named_vm = previous_named_vm
        os.close(opened)
        if compatibility is not None:
            os.close(compatibility)
