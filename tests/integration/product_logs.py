"""One bounded, private product-log snapshot per finished VM case.

Also a guest pytest plugin. This module uses only the standard library so the
controller can run the same reader over the existing guarded SSH transport.
"""

import hashlib
import os
from pathlib import Path
import re
import stat
import sys

COMPONENTS = ('broker', 'parent', 'child', 'kiosk')
_failed_cases = set()


def read_component(component):
    """Read regular root-owned event files without following guest links."""
    assert component in COMPONENTS
    output = []
    directory = None
    try:
        directory = os.open('/var/log/oh-no-parent-control',
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory)
        os.close(directory)
        directory = child
        names = os.listdir(directory)
        # Newest days first; include both ordinary rotations and incident
        # context. Total capture is bounded even if the guest tree is damaged.
        names = sorted((name for name in names if re.fullmatch(
            r'\d{4}-\d{2}-\d{2}(?:\.incident)?\.events(?:\.[12])?', name)),
            key=lambda name: (name[:10], '.incident.' in name,
                              -int(name[-1]) if name[-2:] in ('.1', '.2') else 0),
            reverse=True)[:12]
        if not names:
            output.append('product-log: missing\n')
        remaining = 1024 * 1024
        for name in names:
            if remaining <= 0:
                output.append('product-log: truncated\n')
                break
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
                try:
                    info = os.fstat(fd)
                    if not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                            and info.st_uid == 0):
                        raise OSError('unsafe product log')
                    offset = max(0, info.st_size - min(262144, remaining))
                    os.lseek(fd, offset, os.SEEK_SET)
                    data = os.read(fd, min(262144, remaining))
                    remaining -= len(data)
                    if offset:
                        data = data.partition(b'\n')[2]
                    output.append('product-log: ' + name +
                                  (' truncated' if offset else '') + '\n' +
                                  data.decode('utf-8', errors='replace') + '\n')
                finally:
                    os.close(fd)
            except OSError:
                output.append('product-log: ' + name + ' unavailable\n')
    except OSError:
        output.append('product-log: directory missing or unavailable\n')
    finally:
        if directory is not None:
            os.close(directory)
    # Put the freshest incident/ordinary files at the end for bounded readers.
    return ''.join(reversed(output))


def pytest_runtest_logreport(report):
    """Snapshot once after teardown, including setup/call/teardown failures."""
    if report.outcome != 'passed':
        _failed_cases.add(report.nodeid)
    if report.when != 'teardown':
        return
    import system_guest
    system_guest.guard()
    phase = os.environ['ONPC_SYSTEM_PHASE']
    key = hashlib.sha256((phase + ':' + report.nodeid).encode()).hexdigest()
    directory = system_guest.PAYLOAD / 'private' / 'product-logs' / key
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    # Fixed names replace the same case's snapshot, never append generations.
    for component in COMPONENTS:
        path = directory / (component + '.log')
        with path.open('w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(read_component(component))
    (directory / 'case.txt').write_text(phase + ':' + report.nodeid + '\n')
    (directory / 'outcome.txt').write_text(
        'failed\n' if report.nodeid in _failed_cases else 'passed\n')
    _failed_cases.discard(report.nodeid)


def capture(transport):
    """Host-owned capture before shutdown/restoration; no public log output."""
    from vm_transport import extract, transfer_diagnostic
    directory = Path(transport.commands.directory) / 'product-logs'
    directory.mkdir(mode=0o700, exist_ok=True)
    if hasattr(transport, 'product_logs_per_case'):
        # Guest pytest captured each case, including cases sharing one area VM.
        # Transfer independently of the larger collector, which may itself fail.
        from owned_commands import CommandError
        try:
            raw = transport.call(['tar', '-C', '/var/tmp/onpc-system-input/private/product-logs',
                                  '-cf', '-', '.'], timeout=60,
                                 diagnostic_stdout=transfer_diagnostic)
        except CommandError:
            # Pytest/SSH may have failed before the first teardown. Preserve
            # the live guest's logs rather than depending on a missing payload.
            pass
        else:
            # Archive safety refusals are collection failures, never a reason
            # to silently replace the completed cases' evidence with live logs.
            extract(raw, directory)
            if transport.product_logs_per_case:
                return
    program = Path(__file__).read_text()
    for component in COMPONENTS:
        raw = transport.call(['/usr/bin/python3', '-I', '-c', program, component],
                             timeout=20, diagnostic_stdout=transfer_diagnostic)
        fd = os.open(directory / (component + '.log'),
                     os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            info = os.fstat(stream.fileno())
            if not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and info.st_uid == os.geteuid()):
                raise OSError('unsafe product log destination')
            stream.truncate()
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)


if __name__ == '__main__':
    sys.stdout.write(read_component(sys.argv[1]))
