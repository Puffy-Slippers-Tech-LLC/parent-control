#!/usr/bin/python3
"""Guarded installed-package smoke; imported by host tests without side effects."""

from __future__ import annotations

import hashlib
import grp
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from owned_commands import Commands, CommandError

PAYLOAD = Path('/var/tmp/onpc-system-input')
MARKER = Path('/etc/onpc-system-test.json')
BASELINE = Path('/etc/oh-no-parent-control-test-baseline.json')
BUS = 'com.puffyslippers.OhNoParentControl1'
BROKER = 'oh-no-parent-control-broker.service'
EXPIRY_DIAGNOSTICS = Path('/var/lib/onpc-test-graphical-expiry')
commands = Commands()


class GuestError(RuntimeError):
    """Only fixed categories, never command output or account data."""


def require(condition, category):
    if not condition:
        raise GuestError(category)


def run(argv, timeout=120, *, diagnostic_stdout=None):
    if argv[0] not in ('apt-get', 'dnf'):
        options = {} if diagnostic_stdout is None else {'diagnostic_stdout': diagnostic_stdout}
        return commands.run(argv, timeout=timeout, merge_stderr=False,
                            **options).decode('utf-8').strip()
    # Only package operations expose text. Identity/account probes and their
    # replies remain in private artifacts. Flush both APT streams over SSH while
    # it runs; the host spectator applies its normal redaction and size bounds.
    print('$ ' + shlex.join(argv), flush=True)

    def forward(data, stream):
        output = getattr(sys, stream).buffer
        output.write(data)
        output.flush()

    try:
        return commands.run(argv, timeout=timeout, merge_stderr=False,
                            on_output=forward, terminal=True).decode('utf-8').strip()
    finally:
        if commands.last_returncode is not None:
            print(f'[exit {commands.last_returncode}]', flush=True)


def enable_diagnostics():
    if commands.directory is None:
        directory = PAYLOAD / 'private'
        directory.mkdir(mode=0o700, exist_ok=True)
        commands.directory = Path(tempfile.mkdtemp(prefix='stage-', dir=directory))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_marker(marker, expected, machine, domain):
    require(isinstance(marker, dict) and marker.get('purpose') == 'onpc-system-test', 'marker-purpose')
    require(re.fullmatch(r'[0-9a-f]{32}', expected or '') and marker.get('run') == expected, 'run-identity')
    require(marker.get('machine_id') == machine and machine != marker.get('host_machine_id'), 'machine-identity')
    require(marker.get('domain_uuid') == domain.lower(), 'domain-identity')
    for key in ('baseline_sha256', 'preparation_sha256', 'package_sha256',
                'selected_inputs_sha256'):
        require(isinstance(marker.get(key), str) and re.fullmatch(r'[0-9a-f]{64}', marker[key]), 'marker-digest')


def check_prepared_hostname(expected_digest, hostname):
    require(sha(BASELINE) == expected_digest, 'preparation-digest')
    prepared = json.loads(BASELINE.read_text())
    require(hostname == prepared['guest']['hostname'], 'hostname')


def guard():
    require(os.geteuid() == 0, 'root-required')
    info = MARKER.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
            stat.S_IMODE(info.st_mode) == 0o600, 'marker-permissions')
    marker = json.loads(MARKER.read_text())
    validate_marker(marker, os.environ.get('ONPC_EXPECTED_RUN'),
                    Path('/etc/machine-id').read_text().strip(),
                    Path('/sys/class/dmi/id/product_uuid').read_text().strip())
    require(run(['systemd-detect-virt', '--vm']) in {'kvm', 'qemu'}, 'virtualization')
    check_prepared_hostname(marker['preparation_sha256'], Path('/etc/hostname').read_text().strip())
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                   if '=' in line)
    ubuntu = (release.get('ID', '').strip('"') == 'ubuntu' and
              release.get('VERSION_ID', '').strip('"') == '26.04')
    fedora = (release.get('ID', '').strip('"') == 'fedora' and
              release.get('VERSION_ID', '').strip('"') == '44' and
              release.get('VARIANT_ID', '').strip('"') == 'workstation')
    require(ubuntu or fedora, 'release')
    package = PAYLOAD / ('package.rpm' if fedora else 'package.deb')
    require(package == package_path(), 'package-platform')
    if fedora:
        require(run(['getenforce']) == 'Enforcing', 'selinux-enforcing')
    require(sha(package) == marker['package_sha256'], 'package-digest')
    inventory = json.loads((PAYLOAD / 'transfer-sha256.json').read_text())
    for relative, expected in inventory.items():
        path = PAYLOAD / relative
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and
                not path.is_symlink() and path.is_file() and sha(path) == expected, 'transfer-digest')
    return marker


def package_path():
    require(not ((PAYLOAD / 'package.rpm').exists() and (PAYLOAD / 'package.deb').exists()),
            'ambiguous-package-format')
    return PAYLOAD / ('package.rpm' if (PAYLOAD / 'package.rpm').exists() else 'package.deb')


def package_identity(package, *, installed=False):
    if package.suffix == '.rpm':
        identity = '%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}'
        return run(['rpm', '-q' if installed else '-qp', '--queryformat', identity,
                    'oh-no-parent-control' if installed else str(package)])
    return run(['dpkg-query', '-W', '-f=${Version}', 'oh-no-parent-control'] if installed
               else ['dpkg-deb', '-f', str(package), 'Version'])


def verify_package_files(package=None, *, category='package'):
    package = package_path() if package is None else package
    if package.suffix == '.rpm':
        require(package_identity(package, installed=True) == package_identity(package),
                category + '-version')
        require(not run(['rpm', '--verify', 'oh-no-parent-control']), category + '-file-digests')
        require(run(['getenforce']) == 'Enforcing', 'selinux-enforcing')
    else:
        require(run(['dpkg-query', '-W', '-f=${Status}', 'oh-no-parent-control']) ==
                'install ok installed', category + '-status')
        require(package_identity(package, installed=True) == package_identity(package),
                category + '-version')
        require(not run(['dpkg', '--verify', 'oh-no-parent-control']), category + '-file-digests')


def verify_package():
    verify_package_files()
    if package_path().suffix == '.rpm':
        # RPM can commit its database despite a failed post-transaction
        # scriptlet. Require the configured app and its independent boot gate.
        config = Path('/etc/oh-no-parent-control/config.json').stat()
        require(config.st_uid == 0 and stat.S_IMODE(config.st_mode) == 0o600,
                'configuration-permissions')
        # The broker is a static Type=dbus service. A public read exercises
        # normal activation after reboot, without restarting a service.
        started = time.monotonic()
        try:
            run(['busctl', '--system', '--quiet', 'call', BUS,
                 '/com/puffyslippers/OhNoParentControl1', BUS, 'ListManagedUsers'])
        except CommandError:
            try:
                broker_setup_failure_diagnostic(time.monotonic() - started)
            except Exception:
                # An unavailable diagnostic must not replace the failed check.
                pass
            raise
        for unit in (BROKER, 'oh-no-parent-control-execution-policy-ready.service'):
            require(run(['systemctl', 'is-active', unit]) == 'active', 'service-ready')


def broker_setup_failure_diagnostic(call_seconds):
    """Bounded independent discovery read; preserve the first setup failure.

    Do not start/restart a service, accept the reread, or emit account replies,
    D-Bus owner names or exception messages. The retained SSH stdout owns this
    observation even when setup fails before guest artifacts can be collected.
    """
    original_returncode = commands.last_returncode
    observation = {'event': 'broker-setup-failure',
                   'command_returncode': original_returncode,
                   'call_seconds': round(call_seconds, 3),
                   'discovery': 'unavailable', 'services': {}}

    def discovery():
        try:
            from gi.repository import Gio, GLib
            connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            try:
                connection.call_sync(BUS, '/com/puffyslippers/OhNoParentControl1', BUS,
                    'ListManagedUsers', None, GLib.VariantType.new('(a(uss))'),
                    Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
                return 'succeeded'
            except GLib.Error as error:
                remote = Gio.DBusError.get_remote_error(error)
                known = {BUS + '.Error.' + code: 'product:' + code for code in (
                    'RebootRequired', 'AccessDenied', 'InvalidRequest', 'Failed',
                    'BackendFailure', 'Busy')}
                known.update({'org.freedesktop.DBus.Error.' + code: 'dbus:' + code
                              for code in ('ServiceUnknown', 'NameHasNoOwner',
                                           'NoReply', 'Timeout', 'AccessDenied')})
                return known.get(remote, 'other-error')
        except Exception:
            return 'unavailable'

    def service_state(unit):
        try:
            state = commands.run(['systemctl', 'is-active', unit], timeout=3,
                                 check=False, merge_stderr=False).decode().strip()
            return state if state in (
                'active', 'inactive', 'failed', 'activating', 'deactivating',
                'reloading', 'unknown') else 'unavailable'
        except Exception:
            return 'unavailable'

    try:
        observation['discovery'] = discovery()
        for unit in (BROKER, 'oh-no-parent-control-execution-policy-ready.service'):
            observation['services'][unit] = service_state(unit)
        print(json.dumps(observation, sort_keys=True), flush=True)
        # Observe the already requested startup through its documented service
        # budget. Never activate/restart the broker or accept a later success as
        # repairing the original call. Emit fixed, bounded records only.
        if observation['services'][BROKER] == 'activating':
            settled_at = time.monotonic()
            deadline = settled_at + 180
            state = 'activating'
            while state == 'activating' and time.monotonic() < deadline:
                time.sleep(min(1, max(0, deadline - time.monotonic())))
                state = service_state(BROKER)
            terminal = {'event': 'broker-setup-settlement',
                        'observation_seconds': round(time.monotonic() - settled_at, 3),
                        'service': state, 'discovery': discovery(),
                        'result': 'unavailable', 'exit_status': None}
            try:
                raw = commands.run(['systemctl', 'show', BROKER,
                    '--property=Result', '--property=ExecMainStatus'], timeout=3,
                    check=False, merge_stderr=False).decode()
                properties = dict(line.split('=', 1) for line in raw.splitlines()
                                  if '=' in line)
                result = properties.get('Result')
                if result in ('success', 'exit-code', 'signal', 'core-dump',
                              'timeout', 'watchdog', 'start-limit-hit', 'resources',
                              'protocol', 'oom-kill'):
                    terminal['result'] = result
                status = properties.get('ExecMainStatus', '')
                if re.fullmatch(r'[0-9]{1,3}', status):
                    terminal['exit_status'] = int(status)
            except Exception:
                pass
            print(json.dumps(terminal, sort_keys=True), flush=True)
        broker_startup_cause_diagnostic()
    finally:
        commands.last_returncode = original_returncode


def broker_startup_cause_diagnostic():
    """Project known startup errors and a single outside-service trust read.

    The service can fail before the normal artifact collector is available.
    Never print raw journal text, account data or unrelated trust records, and
    never refresh trust or activate a service from this failure-only probe.
    """
    observation = {'event': 'broker-startup-cause', 'journal': 'unavailable',
                   'causes': [], 'outside_service_trust': 'unavailable'}
    known = {
        'onpc.service: saved-data migration is incomplete': 'migration-incomplete',
        'onpc.service: child trust database is not ready': 'child-trust-not-ready',
        'onpc.runtime startup failed': 'runtime-import-failed',
    }
    try:
        raw = commands.run(['journalctl', '--no-pager', '-b', '-u', BROKER,
                            '--lines=100', '--output=json'], timeout=5,
                           check=False, merge_stderr=False).decode()
        causes = set()
        for line in raw.splitlines():
            message = json.loads(line).get('MESSAGE')
            if not isinstance(message, str):
                continue
            if message in known:
                causes.add(known[message])
            # These are fixed helper error categories. Validate the complete
            # message; discard module names instead of forwarding journal text.
            match = re.fullmatch(
                r'oh-no-parent-control: child trust database is not ready '
                r'\((deadline modules=[A-Za-z0-9_,.\-]+|cli-timeout|'
                r'cli-exit status=[0-9]+|output-decoding|manifest-or-read)\)', message)
            if match:
                causes.add('child-trust-' + match[1].split()[0])
        observation['journal'] = 'read' if commands.last_returncode == 0 else 'read-failed'
        observation['causes'] = sorted(causes)
    except Exception:
        pass
    try:
        manifest = Path('/usr/share/oh-no-parent-control/child-extension.trust')
        expected = {tuple(line.split()) for line in manifest.read_text().splitlines()
                    if line.strip() and not line.startswith('#')}
        require(bool(expected) and all(len(row) == 3 for row in expected),
                'diagnostic-trust-manifest')
        raw = commands.run(['/usr/libexec/oh-no-parent-control-package-activation',
                            'read-child-trust'], timeout=5,
                           check=False, merge_stderr=False)
        if commands.last_returncode == 0:
            rows = json.loads(raw)
            require(isinstance(rows, list) and all(isinstance(row, list) and
                    len(row) == 3 and all(isinstance(value, str) for value in row)
                    for row in rows), 'diagnostic-trust-reply')
            present = {tuple(row) for row in rows}
            require(present <= expected, 'diagnostic-trust-unexpected-record')
            observation['outside_service_trust'] = (
                'complete' if present == expected else 'missing-records')
            observation['missing_records'] = len(expected - present)
        else:
            observation['outside_service_trust'] = 'read-failed'
    except Exception:
        pass
    print(json.dumps(observation, sort_keys=True), flush=True)
    child_trust_inputs_diagnostic()


def child_trust_inputs_diagnostic():
    """Separate missing integration inputs from a daemon/database load failure.

    Only fixed categories and booleans leave this failure-only probe. It does
    not reload the database, repair files, or accept a subsequent startup.
    """
    observation = {'event': 'child-trust-inputs', 'installed_trust': 'unavailable',
                   'file_backend': 'unavailable', 'daemon_journal': 'unavailable',
                   'daemon_events': []}

    def read_fixed(path):
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                    info.st_size <= 65536, 'diagnostic-trust-input')
            contents = stream.read(65537)
            require(len(contents) <= 65536, 'diagnostic-trust-input-size')
            return contents.decode('utf-8')

    try:
        manifest = read_fixed('/usr/share/oh-no-parent-control/child-extension.trust')
        installed = read_fixed('/etc/fapolicyd/trust.d/oh-no-parent-control.trust')
        observation['installed_trust'] = 'matches' if installed == manifest else 'differs'
    except FileNotFoundError:
        observation['installed_trust'] = 'missing-input'
    except Exception:
        pass
    try:
        config = read_fixed('/etc/fapolicyd/fapolicyd.conf')
        selections = re.findall(r'^\s*trust\s*=\s*([^#\n]+)', config, re.MULTILINE)
        if len(selections) == 1:
            observation['file_backend'] = (
                'enabled' if 'file' in [value.strip() for value in selections[0].split(',')]
                else 'disabled')
        elif not selections:
            observation['file_backend'] = 'distribution-default'
        else:
            observation['file_backend'] = 'ambiguous'
    except Exception:
        pass
    try:
        raw = commands.run(['journalctl', '--no-pager', '-b', '-u', 'fapolicyd.service',
                            '--lines=200', '--output=json'], timeout=5,
                           check=False, merge_stderr=False).decode()
        events = set()
        for line in raw.splitlines():
            message = json.loads(line).get('MESSAGE')
            if not isinstance(message, str):
                continue
            if message in ('Loading trust data from file backend', 'Loading file backend',
                           'Importing trust data from file backend'):
                events.add('file-backend-load')
            if message == 'Updated':
                events.add('refresh-completed')
            if re.fullmatch(r'(?:Failed to load (?:trust )?data from backend|'
                            r'Failed to create trust database, create_database\(\)|'
                            r'Cannot update trust database!)' + r'(?: \([0-9]+\))?', message):
                events.add('database-load-error')
            # Project only errors naming the package-owned trust file. Never
            # forward the journal's paths, unrelated records or free text.
            if '/etc/fapolicyd/trust.d/oh-no-parent-control.trust' in message and any(
                    token in message.lower() for token in ('cannot', "can't", 'denied', 'error')):
                events.add('owned-trust-file-error')
        observation['daemon_journal'] = 'read' if commands.last_returncode == 0 else 'read-failed'
        observation['daemon_events'] = sorted(events)
    except Exception:
        pass
    print(json.dumps(observation, sort_keys=True), flush=True)


def before_install():
    marker = guard()
    status = run(['rpm', '-qa', '--queryformat', '%{NAME}\n'] if package_path().suffix == '.rpm'
                 else ['dpkg-query', '-W', '-f=${Package}\t${db:Status-Abbrev}\n'])
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
    install_package()


def install_package():
    from guest_install_recipe import install as install_recipe
    enable_diagnostics()
    install_recipe(run, guard, package_path())
    print('onpc-system: stage=package-install outcome=passed', flush=True)


def install_previous():
    before_install()
    enable_diagnostics()
    previous = PAYLOAD / ('previous-package' + package_path().suffix)
    expected = json.loads((PAYLOAD / 'previous-inputs.json').read_text())
    require(sha(previous) == expected['sha256'], 'previous-package-digest')
    from guest_install_recipe import install as install_recipe
    install_recipe(run, guard, previous)
    verify_package_files(previous, category='previous-package')
    (PAYLOAD / 'results').mkdir(mode=0o700, exist_ok=True)
    (PAYLOAD / 'results/previous-install.json').write_text(json.dumps({
        'previous_package_sha256': expected['sha256'], 'payload_verified': True,
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    }))


def upgrade():
    marker = guard()
    enable_diagnostics()
    wait_for_boot()
    before = json.loads((PAYLOAD / 'results/previous-install.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(boot != before['boot'], 'previous-package-reboot-not-observed')
    require(reboot_cleared(),
            'previous-package-reboot-marker-retained')
    package = package_path()
    previous = PAYLOAD / ('previous-package' + package.suffix)
    require(sha(previous) == before['previous_package_sha256'], 'previous-package-digest')
    verify_package_files(previous, category='previous-package')
    old_version = package_identity(previous, installed=True)
    same_version = old_version == package_identity(package)
    before.update(boot_id=boot, package_sha256=marker['package_sha256'],
                  baseline_sha256=marker['baseline_sha256'])
    (PAYLOAD / 'before.json').write_text(json.dumps(before))
    guard()
    if package.suffix == '.rpm':
        run(['dnf', 'reinstall' if same_version else 'install', '-y', str(package)], timeout=1800)
    else:
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        run(['apt-get', '-o', 'DPkg::Lock::Timeout=120', '--reinstall', 'install',
             '--no-install-recommends', '-y', str(package)], timeout=1800)
    verify_package_files(package)
    require(reboot_requested(),
            'updated-package-did-not-request-reboot')
    (PAYLOAD / 'results/update-activation.json').write_text(json.dumps({
        'previous_package_sha256': before['previous_package_sha256'],
        'package_sha256': marker['package_sha256'], 'old_package_reboot_observed': True,
        'product_reboot_marker_absent_before_update': True, 'update_requested_reboot': True,
        'same_version_reinstall': same_version,
    }, sort_keys=True))


def installed_group(path):
    groups = {
        '/usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop':
            'wheel' if package_path().suffix == '.rpm' else 'sudo',
    }
    return grp.getgrnam(groups.get(str(path), 'root')).gr_gid


def activate_broker(*, reboot_required=False):
    # The static Type=dbus broker starts on demand. Use the explicitly allowed
    # public product interface, not an introspection interface its bus policy
    # does not expose. Suppress account labels returned by the read-only method.
    run(['systemctl', 'stop', BROKER])
    run(['busctl', '--system', 'call', 'org.freedesktop.DBus', '/org/freedesktop/DBus',
         'org.freedesktop.DBus', 'StartServiceByName', 'su', BUS, '0'])
    require(run(['systemctl', 'is-active', BROKER]) == 'active', 'dbus-activation')
    if reboot_required:
        verify_reboot_gate()
        return
    run(['busctl', '--system', '--quiet', 'call', BUS,
         '/com/puffyslippers/OhNoParentControl1', BUS, 'ListManagedUsers'])


def verify_reboot_gate():
    # Check the protocol error name, not translated command stderr or a generic
    # failure. A transport failure or successful policy call must fail this check.
    from gi.repository import Gio, GLib
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    try:
        connection.call_sync(BUS, '/com/puffyslippers/OhNoParentControl1', BUS,
            'ListManagedUsers', None, GLib.VariantType.new('(a(uss))'),
            Gio.DBusCallFlags.NONE, 30000, None)
    except GLib.Error as error:
        require(Gio.DBusError.get_remote_error(error) == BUS + '.Error.RebootRequired',
                'broker-reboot-error')
    else:
        raise GuestError('broker-policy-available-before-reboot')


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


def installed(*, reboot_required=False):
    wait_for_boot()
    verify_package_files()
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
    rules_before = execution_rule_state() if reboot_required else None
    activate_broker(reboot_required=reboot_required)
    for unit in (BROKER, 'accounts-daemon.service', 'fapolicyd.service', 'display-manager.service'):
        require(run(['systemctl', 'is-active', unit]) == 'active', 'service-ready')
    if package_path().suffix == '.rpm':
        require(run(['systemctl', 'is-active', 'oh-no-parent-control-execution-policy-ready.service']) ==
                'active', 'service-ready')
    verify_pam()
    for name in ('child.request-own-access', 'kiosk.request-access'):
        path = Path('/usr/share/polkit-1/actions') / f'tech.puffyslippers.com.ohnoparentcontrol.{name}.policy'
        root = ET.parse(path).getroot()
        require(bool(root.findall('action')), 'polkit-action')
    for path in ('/usr/share/wayland-sessions/oh-no-parent-control.desktop',
                 '/usr/share/gnome-session/sessions/oh-no-parent-control.session',
                 '/usr/share/polkit-1/rules.d/00-oh-no-parent-control-session.rules'):
        require(Path(path).is_file(), 'session-or-polkit-registration')
    if reboot_required:
        # Diagnostics-only activation must preserve existing upgrade policy and
        # must not generate policy on a fresh installation before reboot.
        require(execution_rule_state() == rules_before, 'policy-changed-before-reboot')
    else:
        rules = Path('/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
        require(rules.is_file() and rules.stat().st_uid == 0, 'generated-execution-rules')
    require(bool(run(['fapolicyd-cli', '--list'])), 'loaded-execution-rules')


def execution_rule_state():
    state = {}
    for name in ('01-oh-no-parent-control-deny.rules', '89-oh-no-parent-control.rules'):
        path = Path('/etc/fapolicyd/rules.d', name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            state[name] = None
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_uid == 0, 'generated-execution-rules')
            state[name] = (info.st_mode, info.st_uid, info.st_gid, sha(path))
    return state


def verify_pam():
    fedora = package_path().suffix == '.rpm'
    stacks = (('system-auth', 'system-auth', 'system-auth'),
              ('password-auth', 'password-auth', 'password-auth'),
              ('fingerprint-auth', 'fingerprint-auth', 'fingerprint-auth'),
              ('smartcard-auth', 'smartcard-auth', 'smartcard-auth')) if fedora else (
              ('common-auth', 'common-account', 'common-session'),)
    if fedora:
        run(['authselect', 'check'])
        profile = run(['authselect', 'current', '--raw']).split()
        require(bool(profile) and profile[0] == 'custom/oh-no-parent-control', 'pam-profile')
    for auth, account, session in stacks:
        contents = {name: Path('/etc/pam.d', name).read_text() for name in (auth, account, session)}
        auth_stack = '\n'.join(line for line in contents[auth].splitlines()
                              if line.lstrip().startswith('auth'))
        require('pam_oh_no_parent_control.so' in auth_stack, 'pam-auth')
        account_stack = '\n'.join(line for line in contents[account].splitlines()
                                 if line.lstrip().startswith('account'))
        require('pam_malcontent.so' in account_stack, 'pam-account')
        require('pam_oh_no_parent_control.so' in account_stack and
                account_stack.index('pam_malcontent.so') <
                account_stack.index('pam_oh_no_parent_control.so'), 'pam-runtime-cap')
        require('oh-no-parent-control-clear-session-runtime-max' not in contents[session],
                'obsolete-session-runtime-hook')
    require(not Path('/usr/libexec/oh-no-parent-control-clear-session-runtime-max').exists(),
            'obsolete-session-runtime-hook')


def reboot_requested():
    if package_path().suffix == '.rpm':
        path = Path('/run/oh-no-parent-control-reboot-required')
        return path.is_file() and path.read_text().strip() == 'reboot'
    path = Path('/run/reboot-required.pkgs')
    return (Path('/run/reboot-required').is_file() and path.is_file() and
            'oh-no-parent-control' in path.read_text().splitlines())


def reboot_cleared():
    if package_path().suffix == '.rpm':
        return not Path('/run/oh-no-parent-control-reboot-required').exists()
    path = Path('/run/reboot-required.pkgs')
    return not path.exists() or 'oh-no-parent-control' not in path.read_text().splitlines()


def retain_identity_for_redaction(uid):
    """Keep a private pre-mutation identity for collection after deletion/rename."""
    guard()
    import pwd
    account = pwd.getpwuid(uid)
    require(account.pw_uid >= 1000, 'redaction-identity-range')
    directory = PAYLOAD / 'private' / 'redaction-identities'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, _ = tempfile.mkstemp(suffix='.json', dir=directory)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump((account.pw_name, account.pw_gecos, account.pw_dir), stream)


def _audit_denials(raw):
    """Retain denial coordinates, excluding audit command lines and PROCTITLE."""
    rows = []
    for line in raw.decode(errors='replace').splitlines():
        header = re.match(r'(?:node=\S+ )?type=(AVC|USER_AVC) '
                          r'msg=audit\(([0-9.]+):([0-9]+)\):', line)
        if header is None or re.search(r'\bavc:\s+denied\b', line) is None:
            continue
        row = {'type': header[1], 'epoch': header[2], 'serial': header[3],
               'broker_unit': BROKER in line}
        permissions = re.search(r'denied\s+\{([a-zA-Z0-9_\s]+)\}', line)
        if permissions:
            row['permissions'] = permissions[1].split()
        for field in ('pid', 'uid', 'scontext', 'tcontext', 'tclass', 'permissive'):
            match = re.search(r'\b' + field + r'=([a-zA-Z0-9_:.,-]+)', line)
            if match:
                row[field] = match[1]
        rows.append(row)
    return rows


def collect_seed_access(output, redacted):
    """Read the missing denial sources only for a failed graphical seed."""
    guard()
    result = Commands().run([
        'journalctl', '--no-pager', '--utc', '-b', '--lines=300',
        '_PID=1', '+', '_SYSTEMD_UNIT=dbus-broker.service', '+',
        '_SYSTEMD_UNIT=dbus.service'], timeout=30, check=False, merge_stderr=False)
    (output / 'graphical-expiry-access-journal.txt').write_text(
        redacted(result.decode(errors='replace')))
    # Fedora's audit daemon can own AVC evidence not present in the journal.
    # This optional reader neither installs tools nor changes security policy.
    reader = shutil.which('ausearch')
    audit = {'status': 'reader-unavailable', 'denials': []}
    if reader is not None:
        commands = Commands()
        errors = []
        def retain_error(data, stream):
            if stream == 'stderr':
                errors.append(data)
        result = commands.run([reader, '--input-logs', '--start', 'boot',
                               '--message', 'AVC,USER_AVC', '--raw'], timeout=30,
                              check=False, merge_stderr=False, on_output=retain_error)
        rows = _audit_denials(result)
        audit = {'returncode': commands.last_returncode, 'denials': rows[-100:],
                 'truncated': len(rows) > 100,
                 'stderr': b''.join(errors)[:4096].decode(errors='replace')}
    (output / 'graphical-expiry-access-audit.json').write_text(
        redacted(json.dumps(audit, sort_keys=True)))


def collect(marker, outcome):
    """Copy only text diagnostics, redacting copies using the existing collector helper."""
    sys.path.insert(0, str(Path(__file__).parent / 'guest'))
    from redact import redact_text
    output = PAYLOAD / 'results'
    output.mkdir(parents=True, exist_ok=True)
    # Account names, home paths and host names are additional PII beyond secrets.
    import pwd
    identities = [(p.pw_name, p.pw_gecos, p.pw_dir) for p in pwd.getpwall() if p.pw_uid >= 1000]
    hostname = Path('/etc/hostname').read_text().strip()
    for source in sorted((PAYLOAD / 'private' / 'redaction-identities').glob('*.json')):
        require(source.is_file() and not source.is_symlink(), 'redaction-identity-file')
        identity = json.loads(source.read_text())
        require(isinstance(identity, list) and len(identity) == 3 and
                all(isinstance(value, str) for value in identity), 'redaction-identity-format')
        identities.append(identity)

    def redacted(contents):
        contents = redact_text(contents, marker['run'])
        for name, full, home in identities:
            for value in (home, full, name):
                if value and value != '/':
                    contents = contents.replace(value, '[Test user]')
        return contents.replace(hostname, '[Test VM]') if hostname else contents

    result = Commands().run(['journalctl', '--no-pager', '--utc', '-b', '-u', BROKER,
                             '-u', 'onpc-test-graphical-expiry-broker.service',
                             '-u', 'fapolicyd.service', '-u', 'accounts-daemon.service',
                             '-u', 'slapd.service', '-u', 'sssd.service'],
                            timeout=60, check=False, merge_stderr=False)
    (output / 'service-journal.txt').write_text(redacted(result.decode(errors='replace')))
    # Session-expiry diagnostics need the login-manager/desktop failure that
    # can precede a broker outage. Only redacted copies leave the guest.
    result = Commands().run(['journalctl', '--no-pager', '--utc', '-b',
                             '_SYSTEMD_UNIT=gdm.service', '+',
                             '_SYSTEMD_UNIT=systemd-logind.service', '+',
                             '_COMM=gnome-shell'], timeout=60, check=False, merge_stderr=False)
    (output / 'session-journal.txt').write_text(redacted(result.decode(errors='replace')))
    for name in ('prepared', 'prerequisites', 'broker-ready', 'seed-attempt', 'seeded'):
        source = EXPIRY_DIAGNOSTICS / (name + '.json')
        if source.exists():
            require(source.is_file() and not source.is_symlink()
                    and source.stat().st_size <= 65536, 'expiry-diagnostic-file')
            (output / ('graphical-expiry-' + name + '.json')).write_text(
                redacted(source.read_text()))
    if (EXPIRY_DIAGNOSTICS / 'seed-attempt.json').exists():
        collect_seed_access(output, redacted)
    result = Commands().run(['journalctl', '--no-pager', '--utc', '-b',
                             '_SYSTEMD_UNIT=polkit.service', '+',
                             'SYSLOG_IDENTIFIER=polkit-agent-helper-1'],
                            timeout=60, merge_stderr=False)
    (output / 'authentication-journal.txt').write_text(redacted(result.decode(errors='replace')))
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
        'selected_inputs_sha256': marker['selected_inputs_sha256'],
    }, sort_keys=True) + '\n')
    for source in output.glob('*.xml'):
        # Redact decoded values, then let the serializer escape replacements.
        # Redacting serialized XML can insert literal <redacted> tags into
        # tracebacks or miss XML-escaped identity/credential values.
        tree = ET.parse(source)
        for element in tree.iter():
            if element.text is not None:
                element.text = redacted(element.text)
            if element.tail is not None:
                element.tail = redacted(element.tail)
            for name, value in element.attrib.items():
                element.set(name, redacted(value))
        tree.write(source, encoding='utf-8', xml_declaration=True)


def install_setup():
    marker = guard()
    require(sha(PAYLOAD / 'selected-inputs.json') == marker['selected_inputs_sha256'],
            'selected-inputs-digest')
    install()


def install_suite():
    """Unconditional suite prerequisite; customer installation tests are separate."""
    marker = guard()
    require(sha(PAYLOAD / 'selected-inputs.json') == marker['selected_inputs_sha256'],
            'selected-inputs-digest')
    install_package()


def verify_setup():
    """Feature fixture setup only; no product-policy or activation assertions."""
    marker = guard()
    require(sha(PAYLOAD / 'selected-inputs.json') == marker['selected_inputs_sha256'],
            'selected-inputs-digest')
    wait_for_boot()
    verify_package()
    before = json.loads((PAYLOAD / 'before.json').read_text())
    require(before['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'setup-reboot-required')
    print('onpc-system: stage=feature-setup outcome=passed', flush=True)


def verify_snapshot():
    """Verify installation before publishing a reusable snapshot."""
    guard()
    wait_for_boot()
    verify_package()


def verify_installed():
    """Check the restored app against this attempt's package, without installing."""
    guard()
    installed()
    require(reboot_cleared(), 'snapshot-reboot-required')
    print('onpc-system: stage=snapshot-readiness outcome=passed', flush=True)


def prepare_toggle_session():
    """Prepare one disposable Parent autologin/autostart qualification session."""
    guard()
    installed()
    import pwd
    account = pwd.getpwnam('onpc-parent-jamie')
    home = Path(account.pw_dir)
    info = home.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == account.pw_uid
            and info.st_gid == account.pw_gid, 'toggle-session-home')
    executable = Path('/usr/bin/oh-no-parent-control-parent')
    info = executable.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
            and info.st_mode & 0o111, 'toggle-session-executable')

    directory = home / '.config'
    for path in (directory, directory / 'autostart'):
        try:
            info = path.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == account.pw_uid
                    and info.st_gid == account.pw_gid and not info.st_mode & 0o022,
                    'toggle-session-directory')
        except FileNotFoundError:
            path.mkdir(mode=0o700)
            os.chown(path, account.pw_uid, account.pw_gid)
    target = directory / 'autostart' / 'onpc-toggle-qualification.desktop'
    require(not target.exists() and not target.is_symlink(), 'toggle-session-collision')
    content = ('[Desktop Entry]\nType=Application\n'
               'Name=Parent Toggle Qualification\n'
               'Exec=/usr/bin/oh-no-parent-control-parent\n'
               'NoDisplay=true\nX-GNOME-Autostart-enabled=true\n')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        os.fchown(stream.fileno(), account.pw_uid, account.pw_gid)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    require(target.read_text() == content, 'toggle-session-autostart-readback')

    object_path = f'/org/freedesktop/Accounts/User{account.pw_uid}'
    run(['busctl', '--system', 'call', 'org.freedesktop.Accounts', object_path,
         'org.freedesktop.Accounts.User', 'SetAutomaticLogin', 'b', 'true'])
    require(run(['busctl', '--system', 'get-property', 'org.freedesktop.Accounts', object_path,
                 'org.freedesktop.Accounts.User', 'AutomaticLogin']) == 'b true',
            'toggle-session-autologin-readback')
    print('onpc-system: stage=toggle-session-prepared outcome=passed', flush=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) == 2 and argv[0] == 'collect' and argv[1] in {'passed', 'failed', 'installed'}:
            collect(guard(), argv[1])
        else:
            require(argv in (['guard'], ['before-install'], ['install'],
                             ['install-previous'], ['upgrade'], ['install-setup'],
                             ['verify-setup'], ['install-suite'], ['verify-installed'],
                             ['verify-snapshot'], ['prepare-toggle-session']),
                    'invalid-command')
            {'guard': guard, 'before-install': before_install, 'install': install,
             'install-previous': install_previous, 'upgrade': upgrade,
             'install-setup': install_setup, 'verify-setup': verify_setup,
             'install-suite': install_suite, 'verify-installed': verify_installed,
             'verify-snapshot': verify_snapshot,
             'prepare-toggle-session': prepare_toggle_session}[argv[0]]()
        return 0
    except Exception as error:
        category = str(error) if isinstance(error, (GuestError, CommandError)) else 'unexpected-failure'
        print(f'onpc-system: outcome=failed category={category}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
