"""AUTH03/FILE02/FILE06: finite install/upgrade and independent public readback.

The administrator desktop authorizes the operation; the owned test transport
supplies system authority. No password, terminal, or private product probe is used.
"""

import inspect
import json
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
OLD_INSTALL = 'install-previous-release'
UPGRADE = 'upgrade-staged-package'
BINDINGS = (BINDING, OLD_INSTALL, UPGRADE)


def guest_phase(binding, packages):
    """Finite public dpkg entry; no private product state or reboot guard."""
    import hashlib
    import re
    import stat
    import subprocess
    from pathlib import Path
    session_control.require(binding in (OLD_INSTALL, UPGRADE), 'package-binding')
    session_control.require(type(packages) is dict and set(packages) == {'previous', 'current'},
                            'package-identities')
    for label in ('previous', 'current'):
        path = '/var/lib/onpc-e2e-assets/' + ('previous/' if label == 'previous' else '') + 'package.deb'
        raw = subprocess.check_output(['/usr/bin/dpkg-deb', '-f', path,
                                       'Package', 'Version', 'Architecture'], timeout=30).decode()
        item = packages[label]
        session_control.require(item == {'name': 'oh-no-parent-control',
            'architecture': 'amd64', 'version': item['version'], 'sha256': item['sha256']}
            and raw.splitlines() == ['Package: ' + item['name'], 'Version: ' + item['version'],
                                    'Architecture: ' + item['architecture']]
            and session_control.package_digest(label) == item['sha256'], 'package-identity')
    subprocess.run(['/usr/bin/dpkg', '--compare-versions', packages['current']['version'],
                    'gt', packages['previous']['version']], check=True, timeout=30)
    query = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${Status}\n${Version}\n',
                            'oh-no-parent-control'], capture_output=True, timeout=30)
    boot = hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
    if binding == OLD_INSTALL:
        session_control.require(query.returncode == 1 and not query.stdout, 'package-phase')
    else:
        session_control.require(query.returncode == 0 and query.stdout.decode().splitlines() ==
            ['install ok installed', packages['previous']['version']], 'package-phase')
        marker = Path('/var/lib/onpc-e2e-assets/.previous-install-used')
        info = marker.lstat()
        session_control.require(marker.resolve() == marker and info.st_uid == 0
            and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_mode & 0o7777 == 0o600,
            'package-activation-reboot')
        previous_boot = marker.read_text()
        session_control.require(re.fullmatch('[0-9a-f]{64}', previous_boot)
            and previous_boot != boot, 'package-activation-reboot')
    return boot


def guest_read(packages):
    """Public installed identity and engineering preservation, never product internals."""
    import hashlib
    import os
    import pwd
    import subprocess
    from pathlib import Path
    from account_language_guest import AccountsAPI, accounts, system_locale
    api = AccountsAPI()
    values = {}
    users = accounts()
    for account in users:
        name = account.pw_name
        _, language = api.resolve(account)
        values[str(account.pw_uid)] = {'identity': list(account), 'groups': os.getgrouplist(name, account.pw_gid),
                        'language': language}
    session_control.require(accounts() == users,
                            'package-accounts-changed')
    files = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
             for name in ('/etc/hostname', '/etc/machine-id')}
    # Some supported baselines have no static MOTD. Preserve that absence too:
    # creation/removal must differ from the entry, and other read errors refuse.
    try:
        files['/etc/motd'] = hashlib.sha256(Path('/etc/motd').read_bytes()).hexdigest()
    except FileNotFoundError:
        files['/etc/motd'] = None
    query = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${Status}\n${Version}\n',
                            'oh-no-parent-control'], capture_output=True, timeout=30)
    session_control.require(query.returncode in (0, 1), 'package-query')
    lines = query.stdout.decode().splitlines()
    session_control.require((query.returncode == 1 and not lines) or
        (len(lines) == 2 and lines[0] == 'install ok installed'), 'package-query')
    source = session_control.source_session(session_control.sessions(),
        pwd.getpwnam(session_control.ACCOUNTS['parent']).pw_uid)
    return {'version': lines[1] if lines else None,
        'boot': hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest(),
        'preserved': {'accounts': values, 'system_locale': system_locale(), 'files': files,
                      'observer_locale': {key: value for key, value in os.environ.items()
                          if key in ('LANG', 'LANGUAGE') or key.startswith('LC_')}},
        'session': source, 'packages': {label: session_control.package_digest(label)
                                      for label in packages}}


def guest_submit(binding, expected, packages=None):
    """Executed under vm_transport's guest marker guard; consume before exec."""
    import os
    import grp
    import pwd
    session_control.require(binding in BINDINGS and os.geteuid() == 0, 'package-binding')
    account = pwd.getpwnam(session_control.ACCOUNTS['parent'])
    session_control.require(account.pw_uid >= 1000 and grp.getgrnam('sudo').gr_gid
        in os.getgrouplist(account.pw_name, account.pw_gid), 'administrator-authority')
    source = session_control.source_session(session_control.sessions(), account.pw_uid)
    label = 'previous' if binding == OLD_INSTALL else 'current'
    actual = session_control.package_digest() if binding == BINDING else session_control.package_digest(label)
    session_control.require(actual == expected, 'package-changed')
    boot = guest_phase(binding, packages) if binding != BINDING else None
    session_control.require(session_control.source_session(
        session_control.sessions(), account.pw_uid) == source, 'source-changed')
    # FIX04 owns this root-only parent. An uncertain exec leaves the marker in
    # place, and another controller object cannot replay it in this attempt.
    marker = {BINDING: '.package-install-used', OLD_INSTALL: '.previous-install-used',
              UPGRADE: '.package-upgrade-used'}[binding]
    fd = os.open('/var/lib/onpc-e2e-assets/' + marker,
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    if boot is not None:
        os.write(fd, boot.encode())
        os.fsync(fd)
    os.close(fd)
    os.environ.clear()
    os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8',
                      DEBIAN_FRONTEND='noninteractive', TERM='dumb')
    # Retain stdout/stderr ordering in the guarded command's private transcript.
    os.dup2(1, 2)
    argv = (*ARGV[:-1], '/var/lib/onpc-e2e-assets/previous/package.deb') if binding == OLD_INSTALL else ARGV
    os.execv(argv[0], argv)


def guest_source(*, read=False):
    # Freeze both maintained leaves in this submission; no guest import path.
    return ("import types, sys\n"
            "session_control = types.ModuleType('session_control')\n"
            "sys.modules['session_control'] = session_control\n"
            "exec(" + repr(Path(session_control.__file__).read_text()) +
            ", session_control.__dict__)\n" +
            "account_language_guest = types.ModuleType('account_language_guest')\n"
            "sys.modules['account_language_guest'] = account_language_guest\n"
            "exec(" + repr(Path(__file__).with_name('account_language_guest.py').read_text()) +
            ", account_language_guest.__dict__)\n" +
            'import os, grp, pwd\n' +
            'BINDING = ' + repr(BINDING) + '\nARGV = ' + repr(ARGV) + '\n' +
            'OLD_INSTALL = ' + repr(OLD_INSTALL) + '\nUPGRADE = ' + repr(UPGRADE) + '\n' +
            'BINDINGS = ' + repr(BINDINGS) + '\n' +
            inspect.getsource(guest_phase) + inspect.getsource(guest_read) +
            inspect.getsource(guest_submit) +
            '\nimport sys, json\n' + (
                'print(json.dumps(guest_read(json.loads(sys.argv[1])), sort_keys=True))\n' if read else
                'guest_submit(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) == 4 else None)\n')).encode()


class PackageCommand:
    def __init__(self, transport, verified):
        self.transport, self.verified = transport, verified
        self.identity = dict(transport.config)
        self.attempted = False
        self.receipt = None
        self.binding = None
        # Transport belongs to one attempt. A second controller cannot replay
        # an uncertain submission before it reaches the exclusive guest marker.
        if not hasattr(transport, 'package_attempts'):
            transport.package_attempts = set()

    def validate_input(self, binding, digest, identity):
        require(binding in BINDINGS, 'package:unregistered-command')
        require(identity == self.identity == self.transport.config, 'package:wrong-attempt')
        require(not self.attempted and binding not in self.transport.package_attempts, 'package:replay')
        self.verified.recheck()
        if binding != BINDING:
            require(self.verified.upgrade_inputs is not None, 'package:upgrade-inputs-required')
        expected = (self.verified.inputs['package_sha256'] if binding == BINDING else
                    self.verified.upgrade_inputs['packages'][
                        'previous' if binding == OLD_INSTALL else 'current']['sha256'])
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest)
                and digest == expected, 'package:wrong-artifact')

    def submit(self, binding, digest, identity):
        self.validate_input(binding, digest, identity)
        with operation('Installing the verified package as the authorized administrator'):
            context = session_control.observe(self.transport, 'parent-command-context')
            require(context['package_sha256'] == self.verified.inputs['package_sha256'], 'package:wrong-artifact')
            self.validate_input(binding, digest, identity)
            arguments = [binding, digest]
            if binding != BINDING:
                arguments.append(json.dumps(self.verified.upgrade_inputs['packages'], sort_keys=True))
                entry = self.read_identity()
                require(entry['version'] == (None if binding == OLD_INSTALL else
                        self.verified.upgrade_inputs['packages']['previous']['version']), 'package:wrong-phase')
            self.attempted = True  # Even transport failure is uncertain input.
            self.binding = binding
            self.transport.package_attempts.add(binding)
            received = 0
            def bound(chunk):
                nonlocal received
                received += len(chunk)
                require(received <= LIMIT, 'package:output-bound')
            raw = self.transport.call(['/usr/bin/python3', '-I', '-', *arguments],
                input=guest_source(), timeout=660, check=False, on_output=bound)
            status = self.transport.commands.last_returncode
            self.receipt = (raw, status)
        return {'submitted': True}

    def read_identity(self):
        require(self.transport.config == self.identity, 'package:wrong-attempt')
        self.transport.guard(self.identity)
        self.verified.recheck()
        packages = self.package_identities()
        with operation('Reading installed package version, immutable inputs and preserved account languages'):
            raw = self.transport.call(['/usr/bin/python3', '-I', '-', json.dumps(packages, sort_keys=True)],
                input=guest_source(read=True), timeout=90)
        self.transport.guard(self.identity)
        self.verified.recheck()
        require(type(raw) is bytes and 0 < len(raw) <= 65536, 'package:identity-bound')
        value = json.loads(raw)
        require(type(value) is dict and set(value) == {'version', 'boot', 'preserved', 'session', 'packages'}
            and raw == (json.dumps(value, sort_keys=True) + '\n').encode()
            and type(value['boot']) is str and re.fullmatch('[0-9a-f]{64}', value['boot'])
            and value['packages'] == {label: item['sha256'] for label, item in packages.items()}
            and type(value['preserved']) is dict and type(value['session']) is str,
            'package:identity-schema')
        return value

    def package_identities(self):
        """Bind either the historical pair or the sole verified current package."""
        self.verified.recheck()
        if self.verified.upgrade_inputs is not None:
            return self.verified.upgrade_inputs['packages']
        from build_test_artifacts import package_identity
        current = package_identity(self.verified.assets / 'package.deb')
        require(current['name'] == 'oh-no-parent-control' and current['architecture'] == 'amd64'
                and current['sha256'] == self.verified.inputs['package_sha256'],
                'package:current-identity')
        self.verified.recheck()
        return {'current': current}

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
        require(COMPLETE in lines and (lines[-1] == NOTICE if self.binding != OLD_INSTALL else
                lines[-1] in (COMPLETE, NOTICE)), 'package:completion-notice')
        # Retain actual matched public lines, never arbitrary package diagnostics.
        return {'operation': self.binding, 'outcome': 'passed', 'exit_status': status,
                'interface': 'SSH stdout/stderr', 'completion': lines[lines.index(COMPLETE)],
                'notice': NOTICE if lines[-1] == NOTICE else None}
