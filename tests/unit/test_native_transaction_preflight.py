"""Private native database doubles; no packages, services or VMs are changed."""

import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.integration import native_transaction as native


BASELINE = {'vm_uuid': 'accepted-target', 'preparation_sha256': 'a' * 64}
SELECTED = 'b' * 64


@pytest.mark.parametrize('fail', [False, True])
def test_solver_status_view_preserves_every_reverse_dependency_on_short_writes(
        tmp_path, monkeypatch, fail):
    actual_write = os.write
    monkeypatch.setattr(native.os, 'write', lambda descriptor, data:
                        actual_write(descriptor, data[:7]))
    status = 'Package: target\n\nPackage: reverse-consumer\nDepends: target (>= 999)\n'
    try:
        with native.status_view(status, directory=tmp_path) as descriptor:
            path = Path('/proc/self/fd/' + str(descriptor)).resolve(strict=True)
            assert path.parent == tmp_path
            assert path.read_text() == status
            assert path.stat().st_mode & 0o777 == 0o600
            assert os.read(descriptor, 4096).decode() == status
            if fail:
                raise RuntimeError('solver failed')
    except RuntimeError:
        assert fail
    assert not path.exists()
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
    def __init__(self, manifest, *, status_directory, extra=False, incompatible=False, hold=False, mutate=None):
        self.manifest = manifest
        self.status_directory = status_directory
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
            assert not pass_fds
            status_path = Path(next(value.split('=', 1)[1] for value in arguments
                                    if value.startswith('Dir::State::status=')))
            assert status_path.resolve(strict=True) == status_path
            self.status_views.append(status_path.read_text())
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
    runner = DebRunner(manifest, status_directory=tmp_path, **options)
    receipt = native.preflight('ubuntu', manifest, directory, root=root, runner=runner,
        baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
    return directory, manifest, root, runner, receipt


@pytest.mark.parametrize('installed_version', ['0.11.1-1', '0.11.1-1ubuntu0.3'])
def test_deb_exact_plans_start_from_actual_baseline_then_authenticated_old(tmp_path, installed_version):
    directory, manifest = bundle(tmp_path, 'deb')
    root = deb_root(tmp_path, installed_version)
    before = (root / 'var/lib/dpkg/status').read_bytes()
    runner = DebRunner(manifest, status_directory=tmp_path)
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
    runner = DebRunner(manifest, status_directory=tmp_path, **options)
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
        native.preflight('ubuntu', manifest, directory, root=root,
            runner=DebRunner(manifest, status_directory=tmp_path),
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
            rpm_header('gpg-pubkey', 'fedora-signing-fingerprint', '6786af3b',
                       epoch=None, arch=None),
            rpm_header('filesystem', '3.18', '52.fc44',
                filetriggername=['/sbin', '/usr/bin', '/usr/bin', '/usr/sbin'],
                filetriggerflags=[262144, 65536, 262144, 262144], filetriggerindex=[2, 0, 1, 2],
                filetriggerversion=['', '', '', ''],
                filetriggerscripts=['synthetic filesystem in', 'synthetic filesystem postun',
                                    'synthetic filesystem sbin postun'],
                filetriggerscriptprog=['<lua>'] * 3, filetriggerscriptflags=[],
                filetriggerpriorities=[1000000] * 3,
                transfiletriggername=['/sbin', '/usr/sbin'], transfiletriggerflags=[262144] * 2,
                transfiletriggerindex=[0, 0], transfiletriggerversion=['', ''],
                transfiletriggerscripts=['synthetic nonmatching sbin postun'],
                transfiletriggerscriptprog=['<lua>'], transfiletriggerscriptflags=[],
                transfiletriggerpriorities=[1000000]),
            rpm_header('glibc-common', '2.43', '9.fc44',
                transfiletriggername=['/lib', '/lib', '/lib64', '/lib64',
                                      '/usr/lib', '/usr/lib', '/usr/lib64', '/usr/lib64'],
                transfiletriggerflags=[65536, 262144] * 4,
                transfiletriggerindex=[0, 1] * 4, transfiletriggerversion=[''] * 8,
                transfiletriggerscripts=['synthetic ldconfig in', 'synthetic ldconfig postun'],
                transfiletriggerscriptprog=['<lua>', '<lua>'],
                transfiletriggerscriptflags=[], transfiletriggerpriorities=[2000000, 2000000]),
            rpm_header('man-db', '2.13.1', '3.fc44',
                transfiletriggername=['/usr/share/man', '/usr/share/man'],
                transfiletriggerflags=[65536, 262144], transfiletriggerindex=[0, 1],
                transfiletriggerversion=['', ''],
                transfiletriggerscripts=['synthetic man-db in', 'synthetic man-db postun'],
                transfiletriggerscriptprog=['/bin/sh', '/bin/sh'], transfiletriggerscriptflags=[],
                transfiletriggerpriorities=[1000000, 1000000])]
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


def synthetic_review(records):
    """Pin tiny synthetic definitions independently; this supplies no native runtime proof."""
    return {record['identity']: {prefix: hashlib.sha256(json.dumps(
        {tag: record[tag] for tag in native.RPM_TAGS if tag.startswith(prefix)},
        sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        for prefix in ('trigger', 'filetrigger', 'transfiletrigger')}
        for record in records if record['name'] in {'filesystem', 'glibc-common', 'man-db'}}


@pytest.fixture
def rpm_review(monkeypatch):
    module = RpmModule()
    monkeypatch.setattr(native, 'RPM_TRIGGER_REVIEW', synthetic_review(native.rpm_inventory(module)))
    # Preflight composition checks use a finite environment double. Dedicated
    # environment tests below exercise the real helper with private files.
    monkeypatch.setattr(native, 'rpm_trigger_environment', lambda root, runner:
                        {'filesystem_branch': 'synthetic-private-environment'})
    return module


def test_rpm_inventory_preserves_archless_signing_key_records():
    module = RpmModule()
    records = native.rpm_inventory(module)
    key = next(record for record in records if record['name'] == 'gpg-pubkey')
    assert key['arch'] is None
    assert key['identity'] == 'gpg-pubkey-0:fedora-signing-fingerprint-6786af3b.(none)'
    assert len(records) == len(module.records)
    assert module.closed == 1


@pytest.mark.parametrize('field', ['name', 'version', 'release', 'arch'])
def test_rpm_inventory_refuses_missing_ordinary_package_identity(field):
    module = RpmModule()
    module.records[0][field] = None
    with pytest.raises(ValueError, match='malformed-rpm-status'):
        native.rpm_inventory(module)
    assert module.closed == 1


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
            output = ('/usr/bin/xdg-dbus-proxy\n/usr/share/man/man1/xdg-dbus-proxy.1.gz\n'
                      '/usr/lib/.build-id/ab/cdef\n')
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


def test_rpm_exact_native_capability_reverse_dependency_and_trigger_receipt(tmp_path, rpm_review):
    directory, manifest, root, module, runner = rpm_case(tmp_path)
    receipt = native.preflight('fedora', manifest, directory, root=root, runner=runner,
        rpm_module=module, baseline_provenance=native.digest(BASELINE), selected_input_sha256=SELECTED)
    assert module.closed == 2
    assert len([command for command in runner.commands if '--upgrade' in command]) == 2
    assert receipt['native_state']['providers']['old'] == {
        'libgio-2.0.so.0()(64bit)': ['glib2\t0:2.84.0-1.fc44\tx86_64'],
        'rpmlib(PayloadIsZstd) <= 5.4.18-1': ['native-rpm-engine:checked-by-rpm-test']}
    triggers = receipt['native_state']['triggers']['applicable']
    assert {trigger['owner'] for trigger in triggers} == {
        'filesystem-0:3.18-52.fc44.x86_64', 'glibc-common-0:2.43-9.fc44.x86_64',
        'man-db-0:2.13.1-3.fc44.x86_64'}
    trigger = next(trigger for trigger in triggers if trigger['owner'].startswith('man-db-'))
    assert trigger['definitions']['transfiletriggerscripts'] == [
        'synthetic man-db in', 'synthetic man-db postun']
    assert receipt['native_state']['triggers']['completion_required']
    assert not receipt['old_generation_established']


@pytest.mark.parametrize('fault,reason', [('incompatible', 'native-command-failed'),
    ('pending', 'pending-or-failed-trigger-work'), ('lock', 'held-packages'),
    ('unknown-trigger', 'unreviewed-external-trigger'), ('missing-trigger', 'missing-reviewed-man-db-trigger')])
def test_rpm_refuses_incompatible_or_unaccounted_baseline_without_repair(tmp_path, rpm_review, fault, reason):
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


RPM_PAYLOAD = {'/usr/bin/xdg-dbus-proxy', '/usr/lib/.build-id/ab/cdef',
               '/usr/share/man/man1/xdg-dbus-proxy.1.gz'}


def test_rpm_trigger_arrays_bind_each_matching_script_and_payload(rpm_review):
    records = native.rpm_inventory(rpm_review)
    before = copy.deepcopy(records)
    result = native.rpm_triggers(records, {'package': 'xdg-dbus-proxy'}, RPM_PAYLOAD)
    by_owner = {item['owner'].split('-0:')[0]: item for item in result['applicable']}
    assert set(by_owner) == {'filesystem', 'glibc-common', 'man-db'}
    for owner, kind, path, interpreter in (
            ('filesystem', 'filetrigger', '/usr/bin/xdg-dbus-proxy', '<lua>'),
            ('glibc-common', 'transfiletrigger', '/usr/lib/.build-id/ab/cdef', '<lua>'),
            ('man-db', 'transfiletrigger', '/usr/share/man/man1/xdg-dbus-proxy.1.gz', '/bin/sh')):
        item = by_owner[owner]
        assert item['kind'] == kind
        assert item['actions'] == [dict(index=index, action=kind + action, paths=[path],
            interpreter=interpreter, script_sha256=hashlib.sha256(
                item['definitions'][kind + 'scripts'][index].encode()).hexdigest())
            for index, action in ((0, 'in'), (1, 'postun'))]
    assert records == before


@pytest.mark.parametrize('field,value', [
    ('filetriggerflags', [262144] * 4),
    ('filetriggerindex', [2, 1, 0, 2]),
    ('filetriggerscripts', ['changed', 'synthetic filesystem postun', 'synthetic filesystem sbin postun']),
    ('filetriggerscriptprog', ['/bin/sh'] * 3),
    ('filetriggerscriptflags', [1, 0, 0]),
    ('filetriggerpriorities', [999999] * 3),
    ('filetriggerversion', ['', 'changed', '', '']),
    ('filetriggername', ['/sbin', '/usr/bin', '/usr/bin', '/different-nonmatching']),
    ('transfiletriggerscripts', ['changed nonmatching registration']),
    ('version', '3.19'), ('release', '53.fc44'), ('arch', 'aarch64'), ('name', 'foreign-owner'),
])
def test_rpm_trigger_review_refuses_every_changed_pinned_definition(rpm_review, field, value):
    record = next(item for item in rpm_review.records if item['name'] == 'filesystem')
    record[field] = value
    records = native.rpm_inventory(rpm_review)
    before = copy.deepcopy(records)
    with pytest.raises(native.PreflightError, match='changed-reviewed-trigger|unreviewed-external-trigger'):
        native.rpm_triggers(records, {'package': 'xdg-dbus-proxy'}, RPM_PAYLOAD)
    assert records == before


@pytest.mark.parametrize('changes,reason', [
    ({'filetriggerindex': [2, 0, 1]}, 'malformed-trigger-association'),
    ({'filetriggerindex': [2, 0, 9, 2]}, 'malformed-trigger-association'),
    ({'filetriggerindex': [2, False, 1, 2]}, 'malformed-trigger-association'),
    ({'filetriggerindex': [0, 0, 1, 0]}, 'malformed-trigger-association'),
    ({'filetriggerscriptprog': ['<lua>']}, 'malformed-trigger-association'),
    ({'filetriggerscriptflags': [0]}, 'malformed-trigger-association'),
    ({'filetriggerpriorities': []}, 'malformed-trigger-association'),
    ({'filetriggerversion': []}, 'malformed-trigger-association'),
    ({'filetriggerscripts': [], 'filetriggerscriptprog': [],
      'filetriggerscriptflags': [], 'filetriggerpriorities': []}, 'malformed-trigger-association'),
    ({'filetriggerflags': [262144, 1, 262144, 262144]}, 'unreviewed-trigger-action'),
])
def test_rpm_malformed_associations_refuse_even_with_synthetic_digest_binding(
        rpm_review, monkeypatch, changes, reason):
    record = next(item for item in rpm_review.records if item['name'] == 'filesystem')
    record.update(changes)
    records = native.rpm_inventory(rpm_review)
    # Deliberately bind malformed synthetic data to exercise association checks
    # independently of the production digest gate. Never alter real review pins.
    monkeypatch.setattr(native, 'RPM_TRIGGER_REVIEW', synthetic_review(records))
    with pytest.raises(native.PreflightError, match=reason):
        native.rpm_triggers(records, {'package': 'xdg-dbus-proxy'}, RPM_PAYLOAD)


@pytest.mark.parametrize('owner,reason', [
    ('filesystem', 'missing-reviewed-native-trigger'),
    ('glibc-common', 'missing-reviewed-native-trigger'),
    ('man-db', 'missing-reviewed-man-db-trigger'),
])
def test_rpm_missing_expected_trigger_owner_refuses(rpm_review, owner, reason):
    records = [item for item in native.rpm_inventory(rpm_review) if item['name'] != owner]
    with pytest.raises(native.PreflightError, match=reason):
        native.rpm_triggers(records, {'package': 'xdg-dbus-proxy'}, RPM_PAYLOAD)


def test_rpm_unknown_matching_package_trigger_refuses(rpm_review):
    records = native.rpm_inventory(rpm_review)
    next(record for record in records if record['name'] == 'glib2')['triggername'] = ['xdg-dbus-proxy']
    with pytest.raises(native.PreflightError, match='unreviewed-external-trigger'):
        native.rpm_triggers(records, {'package': 'xdg-dbus-proxy'}, RPM_PAYLOAD)


@pytest.mark.parametrize('fault,reason', [
    (None, None), ('layout', 'unreviewed-filesystem-layout'),
    ('writable', 'unsafe-trigger-executable'), ('nonexecutable', 'unsafe-trigger-executable'),
    ('outside', 'unsafe-trigger-executable'), ('engine', 'unreviewed-rpm-engine'),
    ('provider', 'trigger-executable-provider'), ('multiple-providers', 'trigger-executable-provider'),
    ('service', 'man-db-service-definition'), ('config', 'man-db-service-definition'),
    ('resolution', 'unreviewed-ldconfig-resolution'),
])
def test_rpm_trigger_environment_uses_private_layout_and_executable_providers(
        tmp_path, monkeypatch, fault, reason):
    root = tmp_path / 'guest'
    binaries = root / 'usr/bin'
    binaries.mkdir(parents=True)
    (root / 'bin').symlink_to('usr/bin')
    (root / 'usr/sbin').symlink_to('bin' if fault != 'layout' else 'wrong')
    (root / 'sbin').symlink_to('usr/sbin')
    monkeypatch.setattr(native.shutil, 'which', lambda name:
                        '/usr/local/bin/ldconfig' if fault == 'resolution' else str(binaries / name))
    service = '[Service]\nExecStart=/usr/bin/mandb'
    config = {'usr/lib/systemd/system/man-db-cache-update.service': service,
              'etc/sysconfig/man-db': 'SERVICE="yes"\nOPTS="-q"\n',
              'etc/man_db.conf': 'MANDB_MAP /usr/share/man /var/cache/man\n'}
    for relative, text in config.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o644)
    monkeypatch.setattr(native, 'RPM_SERVICE_REVIEW', {
        **{path: hashlib.sha256(text.encode()).hexdigest() for path, text in config.items()},
        'effective_service': hashlib.sha256(service.encode()).hexdigest()})
    if fault == 'config':
        (root / 'etc/man_db.conf').write_text('MANDB_MAP /usr/share/man /foreign/cache\n')
    providers = {'rpm': 'rpm', 'ldconfig': 'glibc', 'sh': 'bash',
                 'systemd-run': 'systemd', 'systemctl': 'systemd',
                 'mandb': 'man-db', 'whatis': 'man-db'}
    for name in providers:
        path = binaries / name
        path.write_bytes(('synthetic ' + name).encode())
        path.chmod(0o755)
    if fault in {'writable', 'nonexecutable'}:
        (binaries / 'rpm').chmod(0o777 if fault == 'writable' else 0o644)
    if fault == 'outside':
        outside = tmp_path / 'outside'
        outside.write_text('outside')
        (binaries / 'rpm').unlink()
        (binaries / 'rpm').symlink_to(outside)
    calls = []

    def run(arguments, *, timeout):
        assert timeout == 120
        calls.append(arguments)
        if arguments == ['rpm', '--version']:
            output = 'RPM version ' + ('6.0.3' if fault == 'engine' else '6.0.2')
        elif arguments[0] == 'rpm':
            assert arguments[1:3] == ['-q', '--whatprovides']
            name = providers[Path(arguments[3]).name]
            output = name + '\t0:1.0-1.fc44\tx86_64\n'
            if fault == 'provider':
                output = 'foreign-provider\t0:1.0-1.fc44\tx86_64\n'
            elif fault == 'multiple-providers':
                output *= 2
        else:
            assert arguments == ['systemctl', 'cat', 'man-db-cache-update.service']
            output = '[Service]\nExecStart=/usr/bin/' + ('wrong' if fault == 'service' else 'mandb')
        return SimpleNamespace(returncode=0, stdout=output, stderr='')

    runner = SimpleNamespace(run=run)
    if reason:
        with pytest.raises(native.PreflightError, match=reason):
            native.rpm_trigger_environment(root, runner)
    else:
        result = native.rpm_trigger_environment(root, runner)
        assert result['filesystem_branch'] == 'merged-sbin-noop'
        assert result['rpm_version'] == 'RPM version 6.0.2'
        assert result['links']['/usr/sbin']['target'] == 'bin'
        assert len(result['executables']) == 7
        assert result['executables']['/bin/sh']['resolved'] == '/usr/bin/sh'
        assert result['executables']['/usr/bin/rpm']['sha256'] == hashlib.sha256(b'synthetic rpm').hexdigest()
        assert len(calls) == 9


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
    runner = DebRunner(manifest, status_directory=tmp_path)
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
    runner = DebRunner(manifest, status_directory=tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match='native-state-changed'):
        native.preflight('ubuntu', manifest, directory, root=root, runner=runner,
            baseline_provenance=BASELINE, selected_input_sha256=SELECTED)
