#!/usr/bin/python3
"""Guarded installed-package smoke; imported by host tests without side effects."""

from __future__ import annotations

import hashlib
import grp
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET

from owned_commands import Commands, CommandError

PAYLOAD = Path('/var/tmp/onpc-system-input')
MARKER = Path('/etc/onpc-system-test.json')
BASELINE = Path('/etc/oh-no-parent-control-test-baseline.json')
BUS = 'com.puffyslippers.OhNoParentControl1'
BROKER = 'oh-no-parent-control-broker.service'
commands = Commands()


class GuestError(RuntimeError):
    """Only fixed categories, never command output or account data."""


def require(condition, category):
    if not condition:
        raise GuestError(category)


def run(argv, timeout=120):
    return commands.run(argv, timeout=timeout, merge_stderr=False).decode('utf-8').strip()


def enable_diagnostics():
    if commands.directory is None:
        directory = PAYLOAD / 'private'
        directory.mkdir(mode=0o700, exist_ok=True)
        commands.directory = Path(tempfile.mkdtemp(prefix='stage-', dir=directory))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_marker(marker, expected, machine, domain, mounts):
    require(isinstance(marker, dict) and marker.get('purpose') == 'onpc-system-test', 'marker-purpose')
    require(re.fullmatch(r'[0-9a-f]{32}', expected or '') and marker.get('run') == expected, 'run-identity')
    require(marker.get('machine_id') == machine and machine != marker.get('host_machine_id'), 'machine-identity')
    require(marker.get('domain_uuid') == domain.lower(), 'domain-identity')
    require(not any(kind in {'virtiofs', '9p', 'nfs', 'nfs4', 'cifs', 'fuse.sshfs'}
                    for kind in mounts), 'host-filesystem-exposed')
    for key in ('baseline_sha256', 'preparation_sha256', 'package_sha256'):
        require(isinstance(marker.get(key), str) and re.fullmatch(r'[0-9a-f]{64}', marker[key]), 'marker-digest')


def guard():
    require(os.geteuid() == 0, 'root-required')
    info = MARKER.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
            stat.S_IMODE(info.st_mode) == 0o600, 'marker-permissions')
    marker = json.loads(MARKER.read_text())
    mounts = [line.split(' - ', 1)[1].split()[0]
              for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    validate_marker(marker, os.environ.get('ONPC_EXPECTED_RUN'),
                    Path('/etc/machine-id').read_text().strip(),
                    Path('/sys/class/dmi/id/product_uuid').read_text().strip(), mounts)
    require(run(['systemd-detect-virt', '--vm']) in {'kvm', 'qemu'}, 'virtualization')
    require(Path('/etc/hostname').read_text().strip() == 'ubuntu26.04', 'hostname')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                   if '=' in line)
    require(release.get('ID', '').strip('"') == 'ubuntu' and
            release.get('VERSION_ID', '').strip('"') == '26.04', 'release')
    require(sha(BASELINE) == marker['preparation_sha256'], 'preparation-digest')
    package = PAYLOAD / 'package.deb'
    require(sha(package) == marker['package_sha256'], 'package-digest')
    inventory = json.loads((PAYLOAD / 'transfer-sha256.json').read_text())
    for relative, expected in inventory.items():
        path = PAYLOAD / relative
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and
                not path.is_symlink() and path.is_file() and sha(path) == expected, 'transfer-digest')
    return marker


def before_install():
    marker = guard()
    status = run(['dpkg-query', '-W', '-f=${Package}\t${db:Status-Abbrev}\n'])
    require(not any(line.split('\t')[0] == 'oh-no-parent-control' for line in status.splitlines()),
            'baseline-product-present')
    require(not Path('/etc/oh-no-parent-control').exists() and
            not Path('/var/lib/oh-no-parent-control').exists(), 'baseline-product-residue')
    (PAYLOAD / 'before.json').write_text(json.dumps({
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'package_sha256': marker['package_sha256'], 'baseline_sha256': marker['baseline_sha256'],
    }))
    print('onpc-system: stage=pre-install outcome=passed', flush=True)


def install():
    before_install()
    enable_diagnostics()
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    run(['apt-get', 'update'], timeout=600)
    guard()
    run(['apt-get', '-o', 'DPkg::Lock::Timeout=120', 'install', '--no-install-recommends',
         '-y', str(PAYLOAD / 'package.deb')], timeout=1800)
    print('onpc-system: stage=package-install outcome=passed', flush=True)


def installed_group(path):
    groups = {
        '/usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop': 'sudo',
        # The dependency's fapolicyd.conf tmpfiles Z rule recursively applies
        # root:fapolicyd when the newly installed dependency is configured.
        '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules': 'fapolicyd',
    }
    return grp.getgrnam(groups.get(str(path), 'root')).gr_gid


def activate_broker():
    # The static Type=dbus broker starts on demand. Use the explicitly allowed
    # public product interface, not an introspection interface its bus policy
    # does not expose. Suppress account labels returned by the read-only method.
    run(['systemctl', 'stop', BROKER])
    run(['busctl', '--system', 'call', 'org.freedesktop.DBus', '/org/freedesktop/DBus',
         'org.freedesktop.DBus', 'StartServiceByName', 'su', BUS, '0'])
    require(run(['systemctl', 'is-active', BROKER]) == 'active', 'dbus-activation')
    run(['busctl', '--system', '--quiet', 'call', BUS,
         '/com/puffyslippers/OhNoParentControl1', BUS, 'ListManagedUsers'])


def wait_for_boot():
    # SSH can be ready while fapolicyd still builds its trust database. Wait
    # for systemd's startup-complete event before exercising D-Bus activation.
    # A degraded boot is terminal too; the assertions below still require each
    # product dependency to be active. Do not restart services or retry tests.
    print('onpc-system: stage=boot-readiness outcome=waiting', flush=True)
    state = commands.run(['systemctl', 'is-system-running', '--wait'],
                         timeout=600, check=False, merge_stderr=False).decode().strip()
    require((commands.last_returncode, state) in {(0, 'running'), (1, 'degraded')},
            'boot-not-complete')
    print(f'onpc-system: stage=boot-readiness outcome=complete state={state}', flush=True)


def installed():
    wait_for_boot()
    require(run(['dpkg-query', '-W', '-f=${Status}', 'oh-no-parent-control']) == 'install ok installed',
            'package-status')
    version = run(['dpkg-deb', '-f', str(PAYLOAD / 'package.deb'), 'Version'])
    require(run(['dpkg-query', '-W', '-f=${Version}', 'oh-no-parent-control']) == version, 'package-version')
    require(not run(['dpkg', '--verify', 'oh-no-parent-control']), 'package-file-digests')
    expectations = json.loads((PAYLOAD / 'installed-files.json').read_text())
    for entry in expectations:
        path = Path(entry['path'])
        info = path.lstat()
        require(info.st_uid == 0, 'installed-owner')
        if entry['kind'] == 'symlink':
            require(path.is_symlink() and os.readlink(path) == entry['target'], 'installed-symlink')
        else:
            require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == entry['mode'], 'installed-mode')
            if info.st_gid != installed_group(path):
                # Package inventory paths are static integration names, not user data.
                print(f'onpc-system: installed-group path={path} gid={info.st_gid}', flush=True)
            require(info.st_gid == installed_group(path), 'installed-group')
    private = Path('/etc/oh-no-parent-control/config.json').stat()
    require(private.st_uid == 0 and stat.S_IMODE(private.st_mode) == 0o600, 'configuration-permissions')
    activate_broker()
    for unit in (BROKER, 'accounts-daemon.service', 'fapolicyd.service', 'display-manager.service'):
        require(run(['systemctl', 'is-active', unit]) == 'active', 'service-ready')
    require('pam_oh_no_parent_control.so' in Path('/etc/pam.d/common-auth').read_text(), 'pam-auth')
    require('pam_malcontent.so' in Path('/etc/pam.d/common-account').read_text(), 'pam-account')
    require('oh-no-parent-control-clear-session-runtime-max' in
            Path('/etc/pam.d/common-session').read_text(), 'pam-session')
    for name in ('child.request-own-access', 'kiosk.request-access'):
        path = Path('/usr/share/polkit-1/actions') / f'tech.puffyslippers.com.ohnoparentcontrol.{name}.policy'
        root = ET.parse(path).getroot()
        require(bool(root.findall('action')), 'polkit-action')
    for path in ('/usr/share/wayland-sessions/oh-no-parent-control.desktop',
                 '/usr/share/gnome-session/sessions/oh-no-parent-control.session',
                 '/etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules'):
        require(Path(path).is_file(), 'session-or-polkit-registration')
    rules = Path('/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
    require(rules.is_file() and rules.stat().st_uid == 0, 'generated-execution-rules')
    require(bool(run(['fapolicyd-cli', '--list'])), 'loaded-execution-rules')


def collect(marker, outcome):
    """Copy only text diagnostics, redacting copies using the existing collector helper."""
    sys.path.insert(0, str(Path(__file__).parent / 'guest'))
    from redact import redact_text
    output = PAYLOAD / 'results'
    output.mkdir(parents=True, exist_ok=True)
    # Account names, home paths and host names are additional PII beyond secrets.
    import pwd
    identities = [(p.pw_name, p.pw_gecos, p.pw_dir) for p in pwd.getpwall() if p.pw_uid >= 1000]

    def redacted(contents):
        contents = redact_text(contents, marker['run'])
        for name, full, home in identities:
            for value in (home, full, name):
                if value and value != '/':
                    contents = contents.replace(value, '[Test user]')
        return contents.replace('ubuntu26.04', '[Test VM]')

    result = Commands().run(['journalctl', '--no-pager', '--utc', '-b', '-u', BROKER,
                             '-u', 'fapolicyd.service', '-u', 'accounts-daemon.service'],
                            timeout=60, check=False, merge_stderr=False)
    (output / 'service-journal.txt').write_text(redacted(result.decode(errors='replace')))
    logs = Path('/var/log/oh-no-parent-control')
    for source in sorted(logs.glob('*/*.log')):
        require(source.is_file() and not source.is_symlink(), 'log-file-type')
        (output / f'{source.parent.name}-{source.name}').write_text(redacted(source.read_text(errors='replace')))
    for source in sorted((PAYLOAD / 'private').glob('*/*.txt')):
        require(not source.is_symlink(), 'diagnostic-file-type')
        (output / f'{source.parent.name}-{source.name}').write_text(redacted(source.read_text(errors='replace')))
    (output / 'result.json').write_text(json.dumps({
        'schema_version': 1, 'test': 'install-smoke', 'outcome': outcome,
        'package_sha256': marker['package_sha256'], 'baseline_sha256': marker['baseline_sha256'],
    }, sort_keys=True) + '\n')
    for source in output.glob('*.xml'):
        source.write_text(redacted(source.read_text()))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) == 2 and argv[0] == 'collect' and argv[1] in {'passed', 'failed', 'installed'}:
            collect(guard(), argv[1])
        else:
            require(argv in (['guard'], ['before-install'], ['install']), 'invalid-command')
            {'guard': guard, 'before-install': before_install, 'install': install}[argv[0]]()
        return 0
    except Exception as error:
        category = str(error) if isinstance(error, (GuestError, CommandError)) else 'unexpected-failure'
        print(f'onpc-system: outcome=failed category={category}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
