"""One fixed nonsecret keyboard round trip, bound to the observed VT6 shell.

The controller supplies no arbitrary command/path. Guest programs only read;
the visible shell creates one private marker, removed by outer baseline restore.
This does not authorize password input or prove readiness from process state.
"""

import json
import secrets

from guest_observations import VT6_SHELL_LINEAGE
from private_artifacts import EvidenceError, require


def keyboard_command(challenge):
    """Fixed grammar also enforced independently by the worker before typing."""
    import re
    require(type(challenge) is str and re.fullmatch(r'[0-9a-f]{64}', challenge),
            'vt6-command:challenge')
    return ("(umask 077; set -C; builtin printf '%s\\n' '" + challenge +
            "' \"$$\" > /tmp/onpc-vt6-command-" + challenge + ")")


# Wait only for the nonsecret command's file and for its subshell to exit. The
# complete pinned lineage is checked afterwards; waiting cannot repin identity.
# No /proc scan, signal, terminal read, input or guest-side cleanup is performed.
WAIT_MARKER = '''import os,pathlib,time
deadline = time.monotonic() + 30
while True:
    if os.path.lexists(marker):
        leader = int(subprocess.run(['systemctl','show','getty@tty6.service',
            '--property=MainPID','--value'],capture_output=True,text=True,
            check=True,timeout=10).stdout.strip())
        children = (pathlib.Path('/proc')/str(leader)/'task'/str(leader)/'children').read_text().split()
        assert len(children) == 1
        if not (pathlib.Path('/proc')/children[0]/'task'/children[0]/'children').read_text().split():
            break
    assert time.monotonic() < deadline
    time.sleep(0.1)
'''

READ_MARKER = '''
def marker_identity(info):
    # Same stable fields as provenance.identity plus ownership. This guest
    # reader must not reject the access-time update caused by its own read.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_uid, info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
marker_fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
try:
    before = os.fstat(marker_fd)
    assert stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o600
    assert before.st_uid == uid and before.st_nlink == 1
    assert 0 < before.st_size <= 96
    content = os.read(marker_fd, 97)
    assert content == (challenge + '\\n' + str(shell_pid) + '\\n').encode('ascii')
    after = os.fstat(marker_fd)
    assert marker_identity(before) == marker_identity(after)
    assert marker_identity(os.stat(marker, follow_symlinks=False)) == marker_identity(before)
    snapshot()
    assert read_boot() == recipient_boot
    check_active_terminal()
finally:
    os.close(marker_fd)
'''


class CommandRoundTrip:
    def __init__(self, observer, recipient, shell):
        self.observer = observer
        self.recipient, self.shell = recipient, shell
        self.challenge = secrets.token_hex(32)
        self.stage = 0

    def _read(self, complete):
        reader = self.observer
        require(not reader._failed, 'observation:previous-failure')
        try:
            require(self.stage == int(complete), 'vt6-command:order')
            self.stage += 1  # Consume before transport, including partial failures.
            marker = '/tmp/onpc-vt6-command-' + self.challenge
            prefix = ('import subprocess\nchallenge = ' + repr(self.challenge) +
                      '\nmarker = ' + repr(marker) + '\n')
            program = prefix + (WAIT_MARKER if complete else '') + VT6_SHELL_LINEAGE
            program += (READ_MARKER if complete else '\nassert not os.path.lexists(marker)\n')
            program += "print(json.dumps({'boot': recipient_boot, 'recipient': recipient_digest, 'shell': shell_digest}, sort_keys=True))\n"
            reader._guard()
            raw = reader._transport.call(['/usr/bin/python3', '-c', program], timeout=90 if complete else 45)
            reader._guard()
            expected = (json.dumps(dict(boot=self.recipient[0], recipient=self.recipient[1],
                                        shell=self.shell), sort_keys=True) + '\n').encode()
            require(type(raw) is bytes and raw == expected and reader._boot == self.recipient[0],
                    'vt6-command:identity')
            return {'boot_sha256': self.recipient[0], 'active_vt6_verified': True,
                    'vt6_login_continuity_verified': True,
                    ('vt6_shell_ready_verified' if complete else 'vt6_command_input_authorized'): True}
        except BaseException as error:
            reader._failed = True
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise KeyboardInterrupt('vt6-command:interrupted') from None
            raise EvidenceError('vt6-command:refused') from None

    def prepare(self):
        return {**self._read(False), 'command_challenge': self.challenge}

    def complete(self):
        return self._read(True)
