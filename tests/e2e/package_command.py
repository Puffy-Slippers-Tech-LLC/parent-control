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
REMOVE = 'remove-current-package'
PURGE = 'purge-current-package'
REINSTALL = 'reinstall-staged-package'
FRESH_INSTALL = 'install-after-purge'
LIFECYCLE = (REMOVE, PURGE, REINSTALL, FRESH_INSTALL)
INSTALLATIONS = (BINDING, REINSTALL, FRESH_INSTALL)
REMOVAL_NOTICE = '*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***'
PURGE_COMPLETE = 'oh-no-parent-control: saved-state purge outcome=accepted'
BINDINGS = (BINDING, OLD_INSTALL, UPGRADE, *LIFECYCLE)


def guest_phase(binding, packages):
    """Finite public dpkg entry; no private product state or reboot guard."""
    import hashlib
    import re
    import stat
    import subprocess
    from pathlib import Path
    session_control.require(binding in (OLD_INSTALL, UPGRADE), 'package-binding')
    session_control.require(session_control.package_format() == 'deb', 'historical-release-ubuntu-only')
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
    fedora = session_control.package_format() == 'rpm'
    query = subprocess.run((['/usr/bin/rpm', '-q', '--queryformat',
                            '%{NAME}\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n%{ARCH}\n', 'oh-no-parent-control']
                           if fedora else ['/usr/bin/dpkg-query', '-W', '-f=${Status}\n${Version}\n',
                                           'oh-no-parent-control']), capture_output=True, timeout=30,
                           env={**os.environ, 'LC_ALL': 'C'})
    session_control.require(query.returncode in (0, 1), 'package-query')
    lines = query.stdout.decode().splitlines()
    retained_configuration = (not fedora and query.returncode == 0 and len(lines) == 2
                              and lines[0] == 'deinstall ok config-files')
    session_control.require(retained_configuration or (query.returncode == 1 and (lines == [
        'package oh-no-parent-control is not installed'] if fedora else not lines)) or
        (query.returncode == 0 and len(lines) == (3 if fedora else 2) and lines[0] == (
            'oh-no-parent-control' if fedora else 'install ok installed')
            and (not fedora or lines[2] == 'x86_64')), 'package-query')
    source = session_control.source_session(session_control.sessions(),
        pwd.getpwnam(session_control.ACCOUNTS['parent']).pw_uid)
    return {'version': lines[1] if query.returncode == 0 and not retained_configuration else None,
        'boot': hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest(),
        'preserved': {'accounts': values, 'system_locale': system_locale(), 'files': files,
                      'observer_locale': {key: value for key, value in os.environ.items()
                          if key in ('LANG', 'LANGUAGE') or key.startswith('LC_')}},
        'session': source, 'packages': {label: session_control.package_digest(label)
                                      for label in packages}}


def guest_lifecycle_phase(binding, packages):
    """Recheck the public native package phase immediately before consuming input."""
    import subprocess
    session_control.require(binding in LIFECYCLE and type(packages) is dict
                            and set(packages) == {'current'}, 'package-identities')
    item = packages['current']
    session_control.require(item['name'] == 'oh-no-parent-control'
                            and session_control.package_digest() == item['sha256'], 'package-identity')
    if session_control.package_format() == 'rpm':
        query = subprocess.run(['/usr/bin/rpm', '-q', '--queryformat',
            '%{NAME}\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n%{ARCH}\n', 'oh-no-parent-control'],
            capture_output=True, timeout=30, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        installed = query.returncode == 0 and query.stdout.decode().splitlines() == [
            item['name'], item['version'], item['architecture']]
        absent = query.returncode == 1 and query.stdout.decode().splitlines() == [
            'package oh-no-parent-control is not installed']
    else:
        query = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${Status}\n${Version}\n',
                                'oh-no-parent-control'], capture_output=True, timeout=30)
        lines = query.stdout.decode().splitlines()
        installed = query.returncode == 0 and lines == ['install ok installed', item['version']]
        absent = (query.returncode == 1 and not lines) or (
            query.returncode == 0 and lines == ['deinstall ok config-files', item['version']])
    session_control.require(installed if binding in (REMOVE, PURGE) else absent, 'package-phase')


def guest_submit(binding, expected, packages=None):
    """Executed under vm_transport's guest marker guard; consume before exec."""
    import os
    import grp
    import pwd
    session_control.require(binding in BINDINGS and os.geteuid() == 0, 'package-binding')
    account = pwd.getpwnam(session_control.ACCOUNTS['parent'])
    session_control.require(account.pw_uid >= 1000 and grp.getgrnam(session_control.administrator_group()).gr_gid
        in os.getgrouplist(account.pw_name, account.pw_gid), 'administrator-authority')
    source = session_control.source_session(session_control.sessions(), account.pw_uid)
    label = 'previous' if binding == OLD_INSTALL else 'current'
    actual = session_control.package_digest() if binding in (BINDING, *LIFECYCLE) else session_control.package_digest(label)
    session_control.require(actual == expected, 'package-changed')
    boot = guest_phase(binding, packages) if binding in (OLD_INSTALL, UPGRADE) else None
    if binding in LIFECYCLE:
        guest_lifecycle_phase(binding, packages)
    session_control.require(session_control.source_session(
        session_control.sessions(), account.pw_uid) == source, 'source-changed')
    if session_control.package_format() == 'rpm':
        session_control.require(binding in (BINDING, *LIFECYCLE), 'historical-release-ubuntu-only')
        argv = (('/usr/bin/dnf', '--quiet', 'remove', '--no-autoremove', '-y', 'oh-no-parent-control')
                if binding == REMOVE else
                ('/usr/bin/dnf', '--quiet', 'install', '-y', str(session_control.package_path())))
    else:
        argv = (('/usr/bin/apt-get', '-o', 'DPkg::Lock::Timeout=120', 'remove', '-y',
                 'oh-no-parent-control') if binding == REMOVE else
                (*ARGV[:-1], '/var/lib/onpc-e2e-assets/previous/package.deb') if binding == OLD_INSTALL else ARGV)
    if binding == PURGE:
        argv = ('/usr/bin/oh-no-parent-control-purge', '--yes')
    # FIX04 owns this root-only parent. An uncertain exec leaves the marker in
    # place, and another controller object cannot replay it in this attempt.
    marker = {BINDING: '.package-install-used', OLD_INSTALL: '.previous-install-used',
              UPGRADE: '.package-upgrade-used', REMOVE: '.package-remove-used',
              PURGE: '.package-purge-used', REINSTALL: '.package-reinstall-used',
              FRESH_INSTALL: '.package-fresh-install-used'}[binding]
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
            'LIFECYCLE = ' + repr(LIFECYCLE) + '\nREMOVE = ' + repr(REMOVE) + '\n' +
            'PURGE = ' + repr(PURGE) + '\nREINSTALL = ' + repr(REINSTALL) + '\n' +
            'FRESH_INSTALL = ' + repr(FRESH_INSTALL) + '\n' +
            inspect.getsource(guest_phase) + inspect.getsource(guest_read) + inspect.getsource(guest_lifecycle_phase) +
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
        self.entry = None
        # Transport belongs to one attempt. A second controller cannot replay
        # an uncertain submission before it reaches the exclusive guest marker.
        if not hasattr(transport, 'package_attempts'):
            transport.package_attempts = set()

    def validate_input(self, binding, digest, identity):
        require(binding in BINDINGS, 'package:unregistered-command')
        require(identity == self.identity == self.transport.config, 'package:wrong-attempt')
        require(not self.attempted and binding not in self.transport.package_attempts, 'package:replay')
        self.verified.recheck()
        if binding in (OLD_INSTALL, UPGRADE):
            require(self.verified.upgrade_inputs is not None, 'package:upgrade-inputs-required')
        if binding in LIFECYCLE:
            require(self.verified.upgrade_inputs is None, 'package:lifecycle-current-only')
        expected = (self.verified.inputs['package_sha256'] if binding in (BINDING, *LIFECYCLE) else
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
            if binding in (OLD_INSTALL, UPGRADE):
                arguments.append(json.dumps(self.verified.upgrade_inputs['packages'], sort_keys=True))
                entry = self.read_identity()
                require(entry['version'] == (None if binding == OLD_INSTALL else
                        self.verified.upgrade_inputs['packages']['previous']['version']), 'package:wrong-phase')
            elif binding in LIFECYCLE:
                arguments.append(json.dumps(self.package_identities(), sort_keys=True))
                self.entry = self.read_identity()
                require(self.entry['version'] == (self.package_identities()['current']['version']
                        if binding in (REMOVE, PURGE) else None), 'package:wrong-phase')
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
        from provenance import package_filename
        filename = package_filename(self.verified.asset_files)
        current = package_identity(self.verified.assets / filename)
        require(current['name'] == 'oh-no-parent-control' and current['architecture'] == (
                'x86_64' if filename == 'package.rpm' else 'amd64')
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
        removing = self.binding in (REMOVE, PURGE)
        if removing:
            require((lines[-1] == REMOVAL_NOTICE if self.binding == REMOVE else
                    REMOVAL_NOTICE in lines and PURGE_COMPLETE in lines), 'package:completion-notice')
        else:
            require(COMPLETE in lines and (lines[-1] == NOTICE if self.binding != OLD_INSTALL else
                    lines[-1] in (COMPLETE, NOTICE)), 'package:completion-notice')
        if removing or self.binding in LIFECYCLE or 'package.rpm' in self.verified.asset_files:
            identity = self.read_identity()
            require(identity['version'] == (None if removing else self.package_identities()['current']['version']),
                    'package:installed-version')
        # Retain actual matched public lines, never arbitrary package diagnostics.
        return {'operation': self.binding, 'outcome': 'passed', 'exit_status': status,
                'interface': 'SSH stdout/stderr', 'completion': (PURGE_COMPLETE if self.binding == PURGE
                    else None if removing else lines[lines.index(COMPLETE)]),
                'notice': REMOVAL_NOTICE if removing else NOTICE if lines[-1] == NOTICE else None}
