"""Private native database doubles; no packages, services or VMs are changed."""

import copy
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.integration import native_transaction as native


BASELINE = {'vm_uuid': 'accepted-target', 'preparation_sha256': 'a' * 64}
SELECTED = 'b' * 64


def test_solver_status_view_preserves_every_reverse_dependency_on_short_writes(monkeypatch):
    actual_write = os.write
    monkeypatch.setattr(native.os, 'write', lambda descriptor, data:
                        actual_write(descriptor, data[:7]))
    status = 'Package: target\n\nPackage: reverse-consumer\nDepends: target (>= 999)\n'
    with native.status_view(status) as descriptor:
        assert os.read(descriptor, 4096).decode() == status
    with pytest.raises(OSError):
        os.fstat(descriptor)


def bundle(tmp_path, package_format):
    old, new = (('0.11.1-1', '0.11.1-1ubuntu0.3') if package_format == 'deb' else
                ('0:0.1.6-4.fc44', '0:0.1.9-1.fc44'))
    name, architecture = (('bubblewrap', 'amd64') if package_format == 'deb' else
                          ('xdg-dbus-proxy', 'x86_64'))
    manifest = {'schema_version': 1, 'pair_id': package_format + '-pair',
                'package_format': package_format, 'selection': {
                    'package': name, 'architecture': architecture}, 'packages': {}}
    directory = tmp_path / 'bundle'
    directory.mkdir()
    for phase, version in (('old', old), ('new', new)):
        data = (phase + '-authenticated-native-package').encode()
        path = phase + '.' + package_format
        (directory / path).write_bytes(data)
        sha256 = hashlib.sha256(data).hexdigest()
        manifest['selection'][phase] = {'version': version, 'sha256': sha256}
        manifest['packages'][phase] = {'path': path, 'name': name, 'version': version,
            'architecture': architecture, 'sha256': sha256,
            'executable': {'sha256': hashlib.sha256(phase.encode()).hexdigest()}}
    rebind(manifest)
    return directory, manifest


def rebind(manifest):
    manifest['binding_sha256'] = native.digest({key: value for key, value in manifest.items()
                                              if key != 'binding_sha256'})


def deb_root(tmp_path, version='0.11.1-1ubuntu0.3'):
    root = tmp_path / 'guest'
    for directory in ('var/lib/dpkg/updates', 'var/lib/dpkg/triggers', 'var/lib/dpkg/info'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / 'var/lib/dpkg/status').write_text(
        'Package: bubblewrap\nStatus: install ok installed\nArchitecture: amd64\n'
        f'Version: {version}\nDepends: libc6 (>= 2.38)\n\n'
        'Package: libc6\nStatus: install ok installed\nArchitecture: amd64\nVersion: 2.43\n\n'
        'Package: man-db\nStatus: install ok installed\nArchitecture: amd64\nVersion: 2.13.1\n\n')
    (root / 'var/lib/dpkg/triggers/File').write_text('/usr/share/man man-db/noawait\n')
    (root / 'var/lib/dpkg/info/man-db.triggers').write_text('interest-noawait /usr/share/man\n')
    (root / 'var/lib/dpkg/info/man-db.postinst').write_text('#!/bin/sh\nmandb -pq\n')
    for path in root.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root


class DebRunner:
    def __init__(self, manifest, *, extra=False, incompatible=False, hold=False, mutate=None):
        self.manifest = manifest
        self.extra = extra
        self.incompatible = incompatible
        self.hold = hold
        self.mutate = mutate
        self.commands = []
        self.status_views = []

    def run(self, arguments, *, timeout, pass_fds=()):
        assert timeout == 120
        self.commands.append(arguments)
        output, code = '', 0
        if arguments[0] == 'dpkg':
            assert arguments[1] in ('--audit', '--compare-versions')
        elif arguments[0] == 'apt-mark':
            assert arguments == ['apt-mark', 'showhold']
            output = 'bubblewrap\n' if self.hold else ''
        elif arguments[0] == 'dpkg-query':
            assert arguments == ['dpkg-query', '--listfiles', 'bubblewrap:amd64']
            output = '/usr/bin/bwrap\n/usr/share/man/man1/bwrap.1.gz\n'
        elif arguments[0] == 'dpkg-deb':
            phase = Path(arguments[-1]).stem
            item = self.manifest['packages'][phase]
            if arguments[1] == '--field':
                output = ('Package: bubblewrap\nArchitecture: amd64\nVersion: ' +
                          item['version'] + '\nDepends: libc6 (>= 2.38)\n')
            else:
                assert arguments[1] == '--contents'
                output = ('-rwxr-xr-x root/root 80424 2026-01-01 00:00 ./usr/bin/bwrap\n'
                          '-rw-r--r-- root/root 123 2026-01-01 00:00 ./usr/share/man/man1/bwrap.1.gz\n')
        elif arguments[0] == 'apt-get':
            assert '--simulate' in arguments and '--no-download' in arguments
            assert '--reinstall' in arguments
            assert 'Dir::Etc::sourcelist=/dev/null' in arguments
            assert 'Dir::Etc::sourceparts=-' in arguments
            assert len(pass_fds) == 1
            os.lseek(pass_fds[0], 0, os.SEEK_SET)
            self.status_views.append(os.read(pass_fds[0], 100000).decode())
            phase = Path(arguments[-1]).stem
            version = self.manifest['packages'][phase]['version']
            output = f'Inst bubblewrap [previous] ({version} local-deb [amd64])\nConf bubblewrap ({version} local-deb [amd64])\n'
            if self.extra:
                output += 'Inst extra (1 local-deb [amd64])\nConf extra (1 local-deb [amd64])\n'
            if self.incompatible:
                code = 100
                output = 'Broken reverse dependency: third-party requires bubblewrap >= 999\n'
            if self.mutate:
                self.mutate()
        else:
            raise AssertionError(arguments)
        return SimpleNamespace(returncode=code, stdout=output, stderr='')


def probe_deb(tmp_path, **options):
    directory, manifest = bundle(tmp_path, 'deb')
    root = deb_root(tmp_path)
    runner = DebRunner(manifest, **options)
    receipt = native.preflight('ubuntu', manifest, directory, root=root, runner=runner,
        baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
    return directory, manifest, root, runner, receipt


@pytest.mark.parametrize('installed_version', ['0.11.1-1', '0.11.1-1ubuntu0.3'])
def test_deb_exact_plans_start_from_actual_baseline_then_authenticated_old(tmp_path, installed_version):
    directory, manifest = bundle(tmp_path, 'deb')
    root = deb_root(tmp_path, installed_version)
    before = (root / 'var/lib/dpkg/status').read_bytes()
    runner = DebRunner(manifest)
    receipt = native.preflight('ubuntu', manifest, directory, root=root, runner=runner,
        baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
    assert f'Version: {installed_version}\n' in runner.status_views[0]
    assert 'Version: 0.11.1-1\n' in runner.status_views[1]
    assert 'Version: 0.11.1-1ubuntu0.3\n' not in runner.status_views[1]
    assert (root / 'var/lib/dpkg/status').read_bytes() == before
    assert receipt['baseline_provenance_sha256'] == native.digest(BASELINE)
    assert receipt['selected_input_sha256'] == SELECTED
    assert receipt['native_manifest_sha256'] == native.digest(manifest)
    assert receipt['native_binding_sha256'] == manifest['binding_sha256']
    assert receipt['read_only'] and not receipt['old_generation_established']
    assert not receipt['live_transaction_qualified']
    trigger = receipt['native_state']['triggers']['applicable'][0]
    assert trigger['owner'] == 'man-db' and trigger['version'] == '2.13.1'
    assert trigger['controls']['postinst']['definition'].endswith('mandb -pq\n')
    assert not receipt['native_state']['triggers']['man_db_auto_update']
    assert not list((root / 'var/lib/dpkg/updates').iterdir())


@pytest.mark.parametrize('options,reason', [({'extra': True}, 'additional-or-missing-native-changes'),
    ({'incompatible': True}, 'native-command-failed'), ({'hold': True}, 'held-packages')])
def test_deb_incompatible_baseline_never_repairs_or_downgrades(tmp_path, options, reason):
    directory, manifest = bundle(tmp_path, 'deb')
    root = deb_root(tmp_path)
    runner = DebRunner(manifest, **options)
    before = (root / 'var/lib/dpkg/status').read_bytes()
    with pytest.raises(ValueError, match=reason):
        native.preflight('ubuntu', manifest, directory, root=root, runner=runner,
            baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
    assert (root / 'var/lib/dpkg/status').read_bytes() == before
    assert all(command[0] != 'apt-get' or '--simulate' in command for command in runner.commands)


@pytest.mark.parametrize('fault,reason', [('pending', 'pending-triggers'),
    ('updates', 'package-updates-pending'), ('missing-trigger', 'missing-reviewed-man-db-trigger'),
    ('unknown-trigger', 'unreviewed-external-trigger')])
def test_deb_health_and_complete_external_trigger_inventory(tmp_path, fault, reason):
    directory, manifest = bundle(tmp_path, 'deb')
    root = deb_root(tmp_path)
    if fault == 'pending':
        (root / 'var/lib/dpkg/triggers/Unincorp').write_text('/usr/share/man\n')
    elif fault == 'updates':
        (root / 'var/lib/dpkg/updates/0001').write_text('interrupted')
    elif fault == 'missing-trigger':
        (root / 'var/lib/dpkg/triggers/File').write_text('')
    else:
        (root / 'var/lib/dpkg/triggers/File').write_text('/usr/share/man libc6/noawait\n')
        for kind in ('triggers', 'postinst'):
            path = root / ('var/lib/dpkg/info/libc6.' + kind)
            path.write_text('external\n')
            path.chmod(0o644)
    with pytest.raises(ValueError, match=reason):
        native.preflight('ubuntu', manifest, directory, root=root, runner=DebRunner(manifest),
            baseline_provenance=BASELINE, selected_input_sha256=SELECTED)


def test_consumer_receipt_rechecks_native_database_and_refuses_provenance_changes(tmp_path):
    directory, manifest, root, runner, receipt = probe_deb(tmp_path)
    options = dict(root=root, runner=runner, baseline_provenance=BASELINE,
                   selected_input_sha256=SELECTED)
    count = len(runner.commands)
    actual = native.verify_receipt(receipt, 'ubuntu', manifest, directory, **options)
    assert len(runner.commands) > count and actual['native_state'] == receipt['native_state']
    for changed, reason in (({'baseline_provenance': {'vm_uuid': 'foreign'}}, 'baseline-provenance-mismatch'),
                            ({'selected_input_sha256': 'c' * 64}, 'selected-input-mismatch')):
        with pytest.raises(ValueError, match=reason):
            native.verify_receipt(receipt, 'ubuntu', manifest, directory, **{**options, **changed})
    status = root / 'var/lib/dpkg/status'
    status.write_text(status.read_text().replace('Version: 2.43', 'Version: 2.44'))
    with pytest.raises(ValueError, match='installed-baseline-mismatch'):
        native.verify_receipt(receipt, 'ubuntu', manifest, directory, **options)


def rpm_header(name, version, release, **fields):
    result = {key: [] for key in native.RPM_TAGS}
    result.update(name=name, version=version, release=release, epoch=0, arch='x86_64')
    result.update(fields)
    return result


class RpmModule:
    def __init__(self):
        self.records = [rpm_header('xdg-dbus-proxy', '0.1.9', '1.fc44'),
            rpm_header('glib2', '2.84.0', '1.fc44', providename=['libgio-2.0.so.0()(64bit)']),
            rpm_header('man-db', '2.13.1', '1.fc44', transfiletriggername=['/usr/share/man'],
                transfiletriggerflags=[65536], transfiletriggerindex=[0],
                transfiletriggerversion=[''], transfiletriggerscripts=['systemctl start man-db-cache-update'],
                transfiletriggerscriptprog=['/bin/sh'], transfiletriggerscriptflags=[0],
                transfiletriggerpriorities=[2000000])]
        self.closed = 0

    def TransactionSet(self):
        module = self
        class Transaction:
            def dbMatch(self):
                return iter(copy.deepcopy(module.records))
            def closeDB(self):
                module.closed += 1
        return Transaction()

    @staticmethod
    def labelCompare(old, new):
        assert old == ('0', '0.1.6', '4.fc44') and new == ('0', '0.1.9', '1.fc44')
        return -1


class RpmRunner:
    def __init__(self, manifest, *, incompatible=False, pending=False):
        self.manifest = manifest
        self.incompatible = incompatible
        self.pending = pending
        self.commands = []

    def run(self, arguments, *, timeout):
        assert timeout == 120
        self.commands.append(arguments)
        output, code = '', 0
        if arguments[0] == 'dnf':
            assert arguments == ['dnf', '--cacheonly', '--disablerepo=*', 'check']
        elif arguments[0] == 'systemctl':
            output = ('LoadState=loaded\nActiveState=inactive\nSubState=dead\nResult=success\nJob=\n'
                      if not self.pending else
                      'LoadState=loaded\nActiveState=activating\nSubState=start\nResult=success\nJob=12\n')
        elif '--upgrade' in arguments:
            assert '--test' in arguments and '--oldpackage' in arguments and '--replacepkgs' in arguments
            assert len([value for value in arguments if value.endswith('.rpm')]) == 1
            code = 1 if self.incompatible else 0
        elif '--queryformat' in arguments and '-qp' in arguments:
            phase = Path(arguments[-1]).stem
            item = self.manifest['packages'][phase]
            output = f"{item['name']}\t{item['version']}\t{item['architecture']}\n"
        elif '-qpl' in arguments:
            output = '/usr/bin/xdg-dbus-proxy\n/usr/share/man/man1/xdg-dbus-proxy.1.gz\n'
        elif '-ql' in arguments:
            assert arguments == ['rpm', '-ql', 'xdg-dbus-proxy']
            output = '/usr/bin/xdg-dbus-proxy\n/usr/share/man/man1/xdg-dbus-proxy.1.gz\n'
        elif '--requires' in arguments:
            output = 'libgio-2.0.so.0()(64bit)\nrpmlib(PayloadIsZstd) <= 5.4.18-1\n'
        elif '--whatprovides' in arguments:
            output = 'glib2\t0:2.84.0-1.fc44\tx86_64\n'
        else:
            raise AssertionError(arguments)
        return SimpleNamespace(returncode=code, stdout=output, stderr='')


def rpm_case(tmp_path, **options):
    directory, manifest = bundle(tmp_path, 'rpm')
    root = tmp_path / 'guest'
    root.mkdir()
    return directory, manifest, root, RpmModule(), RpmRunner(manifest, **options)


def test_rpm_exact_native_capability_reverse_dependency_and_trigger_receipt(tmp_path):
    directory, manifest, root, module, runner = rpm_case(tmp_path)
    receipt = native.preflight('fedora', manifest, directory, root=root, runner=runner,
        rpm_module=module, baseline_provenance=native.digest(BASELINE), selected_input_sha256=SELECTED)
    assert module.closed == 2
    assert len([command for command in runner.commands if '--upgrade' in command]) == 2
    assert receipt['native_state']['providers']['old'] == {
        'libgio-2.0.so.0()(64bit)': ['glib2\t0:2.84.0-1.fc44\tx86_64'],
        'rpmlib(PayloadIsZstd) <= 5.4.18-1': ['native-rpm-engine:checked-by-rpm-test']}
    trigger = receipt['native_state']['triggers']['applicable'][0]
    assert trigger['owner'] == 'man-db-0:2.13.1-1.fc44.x86_64'
    assert trigger['definitions']['transfiletriggerscripts'] == ['systemctl start man-db-cache-update']
    assert receipt['native_state']['triggers']['completion_required']
    assert not receipt['old_generation_established']


@pytest.mark.parametrize('fault,reason', [('incompatible', 'native-command-failed'),
    ('pending', 'pending-or-failed-trigger-work'), ('lock', 'held-packages'),
    ('unknown-trigger', 'unreviewed-external-trigger'), ('missing-trigger', 'missing-reviewed-man-db-trigger')])
def test_rpm_refuses_incompatible_or_unaccounted_baseline_without_repair(tmp_path, fault, reason):
    directory, manifest, root, module, runner = rpm_case(tmp_path,
        incompatible=fault == 'incompatible', pending=fault == 'pending')
    if fault == 'lock':
        (root / 'etc/dnf').mkdir(parents=True)
        (root / 'etc/dnf/versionlock.toml').write_text('version = "1.0"\n[[packages]]\nname = "xdg-dbus-proxy"\n')
        (root / 'etc/dnf/versionlock.toml').chmod(0o644)
    elif fault == 'unknown-trigger':
        module.records[-1]['name'] = 'foreign-trigger'
    elif fault == 'missing-trigger':
        module.records.pop()
    before = copy.deepcopy(module.records)
    with pytest.raises(ValueError, match=reason):
        native.preflight('fedora', manifest, directory, root=root, runner=runner,
            rpm_module=module, baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
    assert module.records == before
    assert all(command[0] != 'rpm' or '--upgrade' not in command or '--test' in command
               for command in runner.commands)
    assert not any(command[0] == 'dnf' and 'install' in command for command in runner.commands)


@pytest.mark.parametrize('fault,reason', [('digest', 'package-digest'), ('symlink', 'unsafe-file'),
    ('binding', 'native-input-binding'), ('version', 'wrong-package-identity'),
    ('architecture', 'wrong-package-identity'), ('same-bytes', 'same-native-generation')])
def test_unverified_or_substituted_inputs_refuse_before_native_probes(tmp_path, fault, reason):
    directory, manifest = bundle(tmp_path, 'deb')
    path = directory / 'old.deb'
    if fault == 'digest':
        path.write_bytes(b'tampered')
    elif fault == 'symlink':
        path.unlink()
        path.symlink_to(directory / 'new.deb')
    elif fault == 'binding':
        manifest['binding_sha256'] = 'c' * 64
    elif fault in ('version', 'architecture'):
        manifest['packages']['old'][fault] = 'unreviewed'
        rebind(manifest)
    else:
        manifest['packages']['new']['executable'] = manifest['packages']['old']['executable']
        rebind(manifest)
    runner = DebRunner(manifest)
    with pytest.raises(ValueError, match=reason):
        native.preflight('ubuntu', manifest, directory, runner=runner,
            baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
    assert runner.commands == []


def test_package_database_change_during_native_plans_refuses(tmp_path):
    directory, manifest = bundle(tmp_path, 'deb')
    root = deb_root(tmp_path)
    status = root / 'var/lib/dpkg/status'
    def mutate():
        status.write_text(status.read_text().replace('Version: 2.43', 'Version: 2.44'))
    runner = DebRunner(manifest, mutate=mutate)
    with pytest.raises(ValueError, match='native-state-changed'):
        native.preflight('ubuntu', manifest, directory, root=root, runner=runner,
            baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
