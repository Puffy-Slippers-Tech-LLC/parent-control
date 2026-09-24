"""AUTH03/FILE02/FILE06: one fixed install and independent public output readback.

The administrator desktop authorizes the operation; the owned test transport
supplies system authority. No password, terminal, or private product probe is used.
"""

import inspect
from pathlib import Path
import re

from private_artifacts import require
import session_control
from watch_activity import operation

BINDING = 'install-staged-package'
ARGV = ('/usr/bin/apt-get', '-o', 'DPkg::Lock::Timeout=120', 'install',
        '--no-install-recommends', '-y',
        '/var/lib/onpc-e2e-assets/package.deb')
COMPLETE = 'PASS: Oh No! Parent Control package configuration completed successfully.'
NOTICE = '*** REBOOT REQUIRED: reboot before using the kiosk session. ***'
LIMIT = 1024 * 1024


def guest_submit(binding, expected):
    """Executed under vm_transport's guest marker guard; consume before exec."""
    import os
    import grp
    import pwd
    session_control.require(binding == BINDING and os.geteuid() == 0, 'package-binding')
    account = pwd.getpwnam(session_control.ACCOUNTS['parent'])
    session_control.require(account.pw_uid >= 1000 and grp.getgrnam('sudo').gr_gid
        in os.getgrouplist(account.pw_name, account.pw_gid), 'administrator-authority')
    source = session_control.source_session(session_control.sessions(), account.pw_uid)
    session_control.require(session_control.package_digest() == expected, 'package-changed')
    session_control.require(session_control.source_session(
        session_control.sessions(), account.pw_uid) == source, 'source-changed')
    # FIX04 owns this root-only parent. An uncertain exec leaves the marker in
    # place, and another controller object cannot replay it in this attempt.
    fd = os.open('/var/lib/onpc-e2e-assets/.package-install-used',
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    os.environ.clear()
    os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8',
                      DEBIAN_FRONTEND='noninteractive', TERM='dumb')
    # Retain stdout/stderr ordering in the guarded command's private transcript.
    os.dup2(1, 2)
    os.execv(ARGV[0], ARGV)


def guest_source():
    # Freeze both maintained leaves in this submission; no guest import path.
    return ("import types\n"
            "session_control = types.ModuleType('session_control')\n"
            "exec(" + repr(Path(session_control.__file__).read_text()) +
            ", session_control.__dict__)\n" +
            'import os, grp, pwd\n' +
            'BINDING = ' + repr(BINDING) + '\nARGV = ' + repr(ARGV) + '\n' +
            inspect.getsource(guest_submit) +
            '\nimport sys\nguest_submit(sys.argv[1], sys.argv[2])\n').encode()


class PackageCommand:
    def __init__(self, transport, verified):
        self.transport, self.verified = transport, verified
        self.identity = dict(transport.config)
        self.attempted = False
        self.receipt = None

    def validate_input(self, binding, digest, identity):
        require(binding == BINDING, 'package:unregistered-command')
        require(identity == self.identity == self.transport.config, 'package:wrong-attempt')
        require(not self.attempted, 'package:replay')
        self.verified.recheck()
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest)
                and digest == self.verified.inputs['package_sha256'], 'package:wrong-artifact')

    def submit(self, binding, digest, identity):
        self.validate_input(binding, digest, identity)
        with operation('Installing the verified package as the authorized administrator'):
            context = session_control.observe(self.transport, 'parent-command-context')
            require(context['package_sha256'] == digest, 'package:wrong-artifact')
            self.validate_input(binding, digest, identity)
            self.attempted = True  # Even transport failure is uncertain input.
            received = 0
            def bound(chunk):
                nonlocal received
                received += len(chunk)
                require(received <= LIMIT, 'package:output-bound')
            raw = self.transport.call(['/usr/bin/python3', '-I', '-', binding, digest],
                input=guest_source(), timeout=660, check=False, on_output=bound)
            status = self.transport.commands.last_returncode
            self.receipt = (raw, status)
        return {'submitted': True}

    def read_result(self):
        """Called at a later checkpoint; submission itself never asserts success."""
        require(self.transport.config == self.identity and self.receipt is not None,
                'package:missing-result')
        self.transport.guard(self.identity)
        self.verified.recheck()
        raw, status = self.receipt
        require(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'package:output-bound')
        require(type(status) is int and status == 0, 'package:command-failed')
        text = raw.decode('utf-8', errors='strict')
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        lines = text.splitlines()
        require(COMPLETE in lines and lines[-1] == NOTICE, 'package:completion-notice')
        # Retain actual matched public lines, never arbitrary package diagnostics.
        return {'operation': BINDING, 'outcome': 'passed', 'exit_status': status,
                'interface': 'SSH stdout/stderr', 'completion': lines[lines.index(COMPLETE)],
                'notice': lines[-1]}
