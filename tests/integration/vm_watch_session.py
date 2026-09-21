"""Keep the existing display observer alive between maintenance commands.

Only an already guarded graphics FD is inherited. The keeper has no lifecycle
API, SSH connection, input channel, lease lock, or viewer-owned process. It exits
when the exact attested domain instance/configuration ends or changes.
"""

import argparse
import difflib
import os
from pathlib import Path
import select
import re
import signal
import socket
import subprocess

from e2e_watch import Observer, configuration_digest, require


def matches(connection, uuid, domain_id, xml_sha256, *, expected_xml=None):
    """Read-only revalidation; never discover or adopt a replacement instance."""
    from vm_config import URI
    require(connection.getURI() == URI, 'session-connection')
    domain = connection.lookupByUUIDString(uuid)
    if domain.UUIDString() != uuid or domain.ID() != domain_id:
        return False
    xml = domain.XMLDesc(0)
    if configuration_digest(xml) != xml_sha256:
        if expected_xml is not None:
            fields = {match.group(1) for line in difflib.ndiff(expected_xml.splitlines(), xml.splitlines())
                      if line.startswith(('- ', '+ '))
                      if (match := re.match(r'\s*</?([\w-]+)', line[2:]))}
            print('vm-watch: changed XML fields=' + ','.join(sorted(fields)), flush=True)
        return False
    return domain.ID() == domain_id


class Session:
    """Pinned, initially gated keeper; detach does not signal any process."""

    def __init__(self, adapter, uid):
        self.child = self.pidfd = self.control = None
        display = remote = None
        try:
            display = adapter.open_display(index=1)
            self.control, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            source = adapter.lease.source
            digest = configuration_digest(source.domain.XMLDesc(0))
            adapter.revalidate()
            argv = ['/usr/bin/python3', '-B', str(Path(__file__).resolve()),
                    '--control', str(remote.fileno()), '--display', str(display.fileno()),
                    '--uid', str(uid), '--run', adapter.run, '--uuid', source.uuid,
                    '--domain-id', str(adapter.lease.view.domain_id), '--xml-sha256', digest]
            log = adapter.lease.commands.directory / ('watch-' + adapter.run + '.log')
            with log.open('xb') as output:
                os.fchmod(output.fileno(), 0o600)
                self.child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                    pass_fds=(remote.fileno(), display.fileno()),
                    env={'PATH': '/usr/bin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'})
            self.pidfd = os.pidfd_open(self.child.pid)
            self.control.settimeout(10)
            self.control.sendall(b'start')
            require(self.control.recv(16) == b'ready', 'session-not-ready')
        except BaseException:
            self.close()
            raise
        finally:
            # close, not shutdown: the keeper owns the inherited display now.
            for peer in (display, remote):
                if peer is not None:
                    peer.close()

    def detach(self):
        if self.control is not None:
            self.control.sendall(b'detach')
            self.control.close()
            self.control = None
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None
        self.child = None

    def close(self):
        if self.control is not None:
            try:
                self.control.sendall(b'close')
            except OSError:
                pass
            self.control.close()
            self.control = None
        if self.child is not None:
            try:
                self.child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                require(self.pidfd is not None, 'unrecorded-session')
                try:
                    signal.pidfd_send_signal(self.pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.child.wait(timeout=2)
            self.child = None
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None


def follow(control, observer, guard):
    """Detach is explicit; controller loss before handoff revokes the observer."""
    detached = False
    while not observer.finished.is_set():
        if not guard():
            print('vm-watch: recorded domain ended or changed', flush=True)
            return
        if detached:
            observer.finished.wait(.25)
        elif select.select([control], [], [], .25)[0]:
            message = control.recv(16)
            if message == b'detach':
                detached = True
                print('vm-watch: maintenance controller detached', flush=True)
            else:
                print('vm-watch: controller closed the session', flush=True)
                break


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    for name in ('control', 'display', 'uid', 'domain-id'):
        parser.add_argument('--' + name, type=int, required=True)
    for name in ('run', 'uuid', 'xml-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0 and args.uid > 0 and args.domain_id >= 0, 'session-context')
    connection = observer = None
    display = socket.socket(fileno=args.display)
    with socket.socket(fileno=args.control) as control:
        control.settimeout(5)
        try:
            if control.recv(16) != b'start':
                return
            import libvirt
            from vm_config import URI
            connection = libvirt.openReadOnly(URI)
            expected_xml = connection.lookupByUUIDString(args.uuid).XMLDesc(0)
            def guard():
                return matches(connection, args.uuid, args.domain_id, args.xml_sha256,
                               expected_xml=expected_xml)
            require(guard(), 'session-identity')
            observer = Observer(display, args.uid, args.run)
            require(observer.ready.wait(6) and not observer.finished.is_set(), 'session-collector')
            control.sendall(b'ready')
            follow(control, observer, guard)
        finally:
            if observer is not None:
                observer.close()
            else:
                display.close()
            if connection is not None:
                connection.close()


if __name__ == '__main__':
    main()
