"""Private pytest files, in-memory guest/transport doubles and waited Perl only.

No live account, VM, display, bus, shared cache or heavy fixture build. Compatible
in unit and cleanup scheduling; all ownership mutations remain process-local doubles.
"""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import guest_files
import native_fixtures as controller
import native_fixtures_guest as guest


from native_fixture_qualification import NativeFixtureJourney, PLAN
from private_artifacts import EvidenceError
from tests.fixtures.native_assets import (ASSETS, desktop_entry, desktop_id, sources,
    executable_sources, gui_sources, launcher_sources)
from ui_observations import AppRowsObservation


@pytest.fixture(autouse=True)
def platform(monkeypatch):
    monkeypatch.setattr(guest.session_control, 'package_format', lambda: 'deb')


def private_directories(path, root):
    path.mkdir(parents=True, exist_ok=True)
    while path != root:
        path.chmod(0o755)
        path = path.parent


@pytest.fixture
def payload(tmp_path, monkeypatch):
    home = tmp_path / 'different-home'
    home.mkdir(mode=0o700)
    child = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid(), pw_gid=os.getgid())
    monkeypatch.setattr(guest, 'ROOT_DIRECTORY', tmp_path)
    monkeypatch.setattr(guest, 'PREFIX', str(tmp_path / 'opt/fixtures/Applications'))
    parent = SimpleNamespace(pw_uid=2000)
    monkeypatch.setattr(guest, 'authority', lambda: (child, parent, 'session'))
    monkeypatch.setattr(guest.session_control, 'source_session', lambda *args: 'session')
    monkeypatch.setattr(guest.session_control, 'sessions', lambda: {})
    expected = {}
    for index, (name, (path, mode)) in enumerate(guest.destinations(child).items()):
        private_directories(path.parent, tmp_path)
        asset = next((asset for asset in ASSETS if desktop_id(asset[0]) == path.name), None)
        path.write_bytes(desktop_entry(asset).encode() if asset else f'distinct payload {index}'.encode())
        path.chmod(mode)
        expected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return child, expected


def test_readback_nonstandard_home_and_preserved_unrelated_files(payload):
    child, expected = payload
    xdg = Path(child.pw_dir) / '.local/share/applications'
    unrelated = xdg / 'unrelated.desktop'
    unrelated.write_bytes(b'preserve')
    before = unrelated.stat()
    first = guest.execute('read', expected)
    assert guest.execute('read', expected) == first
    assert len(first['files']) == 12
    assert unrelated.read_bytes() == b'preserve' and unrelated.stat() == before
    for source, (path, mode) in guest.destinations(child).items():
        assert path.stat().st_uid == child.pw_uid and path.stat().st_gid == child.pw_gid
        assert path.stat().st_mode & 0o777 == mode
    with pytest.raises(ValueError):
        guest.execute('prepare', expected)


@pytest.mark.parametrize('fault', ['digest', 'missing', 'bytes', 'mode', 'hardlink',
                                  'symlink', 'parent-link', 'parent-mode', 'launcher',
                                  'versioned-extra', 'versioned-directory', 'versioned-mode',
                                  'versioned-link', 'versioned-gui-digest', 'source-key',
                                  'versioned-owner', 'versioned-group'])
def test_baseline_readback_refuses_without_repairing(payload, monkeypatch, fault):
    child, expected = payload
    target = next(iter(guest.destinations(child).values()))[0]
    if fault == 'digest': expected[sources()[0]] = '0' * 64
    if fault == 'missing': target.unlink()
    if fault == 'bytes': target.write_bytes(b'changed')
    if fault == 'mode': target.chmod(0o644)
    if fault == 'hardlink': os.link(target, target.with_name('copy'))
    if fault == 'symlink':
        target.rename(target.with_name('copy'))
        target.symlink_to(target.with_name('copy'))
    if fault == 'parent-link':
        target.parent.rename(target.parent.with_name('preserved'))
        target.parent.symlink_to(target.parent.with_name('preserved'))
    if fault == 'parent-mode': target.parent.chmod(0o777)
    if fault == 'launcher':
        launcher = Path(child.pw_dir) / '.local/share/applications' / desktop_id('A')
        launcher.write_bytes(b'wrong launcher')
        expected[launcher_sources()[0]] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    versioned = Path(guest.PREFIX) / 'Versioned'
    if fault == 'versioned-extra': (versioned / 'Allowed Nonmatch.AppImage').write_bytes(b'foreign')
    if fault == 'versioned-directory': (versioned / 'foreign').mkdir()
    if fault == 'versioned-mode': versioned.chmod(0o700)
    if fault == 'versioned-link':
        versioned.rename(versioned.with_name('preserved-versioned'))
        versioned.symlink_to(versioned.with_name('preserved-versioned'))
    if fault == 'versioned-gui-digest': expected[gui_sources()[2]] = expected[gui_sources()[0]]
    if fault == 'source-key':
        expected[executable_sources()[2].replace('/Versioned/', '/')] = expected.pop(executable_sources()[2])
    if fault in ('versioned-owner', 'versioned-group'):
        versioned_inode = versioned.stat().st_ino
        actual = guest.os.fstat
        def fstat(fd):
            info = actual(fd)
            if info.st_ino == versioned_inode:
                values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                values['st_uid' if fault == 'versioned-owner' else 'st_gid'] += 1
                return SimpleNamespace(**values)
            return info
        monkeypatch.setattr(guest.os, 'fstat', fstat)
    before = {path: path.lstat() for path, _ in guest.destinations(child).values()
              if path.exists() or path.is_symlink()}
    with pytest.raises((ValueError, OSError)):
        guest.execute('read', expected)
    assert {path: path.lstat() for path in before} == before


def test_runtime_cannot_install_even_with_missing_baseline(payload):
    child, expected = payload
    target = next(iter(guest.destinations(child).values()))[0]
    target.unlink()
    with pytest.raises(ValueError): guest.execute('prepare', expected)
    assert not target.exists()


@pytest.mark.parametrize('fault', [None, 'missing', 'bytes', 'mode', 'group', 'record',
    'uid', 'foreign-policy', 'stock-bytes', 'sample-bytes', 'listing-bytes', 'compiled',
    'product-witness', 'product-header', 'product-mode'])
def test_fedora_readback_checks_owned_admission_and_stock_without_repair(payload, tmp_path, monkeypatch, fault):
    from tests.fixtures import native_assets as assets
    child, expected = payload
    # The two shared runtimes have identical source bytes in both directories.
    for first, second in zip(assets.gui_sources()[:2], assets.gui_sources()[2:]):
        path = guest.destinations(child)[second][0]
        path.write_bytes(guest.destinations(child)[first][0].read_bytes())
        expected[second] = expected[first]
    rules = assets.native_policy_files(expected, (1000, 1001))
    listing = '/usr/share/fapolicyd/default-ruleset.known-libs'
    stock = {name: b'# fixed stock source\n' for name in assets.NATIVE_STOCK_RULE_NAMES}
    stock.update({'42-trusted-elf.rules': b'allow perm=execute all : trust=1\n',
                  '70-trusted-lang.rules': b'deny_audit perm=open all : ftype=text/x-python trust=0\n',
                  '90-deny-execute.rules': b'deny_audit perm=execute all : all\n'})
    samples = {listing: ('\n'.join(stock) + '\n').encode()} | {
        '/usr/share/fapolicyd/sample-rules/' + name: data for name, data in stock.items()}
    manifest = ''.join(path + '\t' + hashlib.sha256(data).hexdigest()
        + '\t33188\troot\troot\t0\n' for path, data in samples.items())
    files = {path: [data, 0o644, 987] for path, data in rules.items()}
    files.update({path: [data, 0o644, 0] for path, data in samples.items()})
    files.update({'/etc/fapolicyd/rules.d/' + name: [data, 0o644, 987] for name, data in stock.items()})
    header = b'# Generated by Oh No! Parent Control. Do not edit.\n'
    product = {'00-oh-no-parent-control-canary.rules': b'# owned installed canary\n',
               '01-oh-no-parent-control-deny.rules': header + b'deny_syslog perm=execute uid=1001 : sha256hash=' + b'a' * 64 + b'\n',
               '89-oh-no-parent-control.rules': header + b'allow perm=open uid=1001 : path=/finite/exception\n'}
    files.update({'/etc/fapolicyd/rules.d/' + name: [data, 0o644, 10] for name, data in product.items()})
    witness = '/var/lib/oh-no-parent-control/installed-fapolicyd-canary'
    files[witness] = [product['00-oh-no-parent-control-canary.rules'], 0o600, 10]
    record = {'purpose': 'onpc-reusable-fixtures-v1', 'pending': None, 'files': {
        path: {'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o644, 'uid': 0, 'gid': 987}
        for path, data in rules.items()}}
    target = next(iter(rules))
    names = {Path(path).name for path in rules} | set(stock) | set(product)
    if fault == 'missing': del files[target]
    if fault == 'bytes': files[target][0] = b'changed'
    if fault == 'mode': files[target][1] = 0o666
    if fault == 'group': files[target][2] = 0
    if fault == 'record': record['files'][target]['sha256'] = '0' * 64
    if fault == 'foreign-policy': names.add('95-administrator.rules')
    if fault == 'stock-bytes': files['/etc/fapolicyd/rules.d/90-deny-execute.rules'][0] = b'changed'
    if fault == 'sample-bytes': files['/usr/share/fapolicyd/sample-rules/90-deny-execute.rules'][0] = b'changed'
    if fault == 'listing-bytes': files[listing][0] = b'changed.rules\n'
    if fault == 'product-witness': files[witness][0] = b'foreign'
    if fault == 'product-header': files['/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules'][0] = b'foreign'
    if fault == 'product-mode': files['/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules'][1] = 0o666
    reads = []
    def read(path, mode=0o600, gid=0, limit=guest.LIMIT):
        reads.append(path)
        if path == '/var/lib/onpc-baseline-fixtures.json':
            assert mode == 0o600 and gid == 0
            return json.dumps(record).encode()
        data, actual_mode, actual_gid = files[path]
        guest.require(mode == actual_mode and (gid is None or gid == actual_gid))
        return data
    monkeypatch.setattr(guest, 'activity_root_file', read)
    monkeypatch.setattr(guest.session_control, 'package_format', lambda: 'rpm')
    monkeypatch.setattr(guest.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=
        (1003 if fault == 'uid' else 1000) if name == guest.session_control.ACCOUNTS['child'] else 1001))
    monkeypatch.setattr(guest.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=987))
    original_lexists = guest.os.path.lexists
    monkeypatch.setattr(guest.os.path, 'lexists', lambda path: False if str(path).startswith(
        '/etc/fapolicyd/') else original_lexists(path))
    original_directory = guest.directory
    @contextmanager
    def policy_directory(path, owner):
        if path == Path('/etc/fapolicyd/rules.d'):
            yield -999, lambda: None
        else:
            with original_directory(path, owner) as value:
                yield value
    monkeypatch.setattr(guest, 'directory', policy_directory)
    original_listdir = guest.os.listdir
    monkeypatch.setattr(guest.os, 'listdir', lambda fd: list(names) if fd == -999 else original_listdir(fd))
    original_stat, original_read = guest.os.stat, guest.read_regular
    def policy_stat(path, *args, **options):
        if options.get('dir_fd') == -999:
            return SimpleNamespace(st_gid=files['/etc/fapolicyd/rules.d/' + path][2])
        return original_stat(path, *args, **options)
    def policy_read(fd, name, *, owner, mode, limit):
        if fd == -999:
            data, actual_mode, actual_gid = files['/etc/fapolicyd/rules.d/' + name]
            guest.require(owner == 0 and mode == actual_mode)
            return data, SimpleNamespace(st_gid=actual_gid)
        return original_read(fd, name, owner=owner, mode=mode, limit=limit)
    monkeypatch.setattr(guest.os, 'stat', policy_stat)
    monkeypatch.setattr(guest, 'read_regular', policy_read)
    calls = []
    def command(argv, **options):
        calls.append(argv)
        assert options['check'] and options['timeout'] == 30 and options['stdin'] == guest.subprocess.DEVNULL
        return SimpleNamespace(stdout=(manifest if argv[0] == 'rpm' else
            '/usr/sbin/fagenrules: ' + ('changed' if fault == 'compiled' else 'No change') + '\n').encode(), stderr=b'')
    monkeypatch.setattr(guest.subprocess, 'run', command)
    before = {path: path.stat() for path, _ in guest.destinations(child).values()}
    if fault:
        with pytest.raises((ValueError, KeyError)):
            guest.execute('read', expected)
    else:
        first = guest.execute('read', expected)
        assert len(first['files']) == 12 and guest.execute('read', expected) == first
        assert len(calls) == 4 and set(rules) <= set(reads)
    signature = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                              info.st_mtime_ns, info.st_ctime_ns)
    assert {path: signature(path.stat()) for path in before} == {path: signature(info) for path, info in before.items()}


def test_shared_reader_rejects_owner_and_replacement(tmp_path, monkeypatch):
    path = tmp_path / 'file'
    path.write_bytes(b'payload')
    path.chmod(0o600)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(ValueError):
            guest_files.read_regular(fd, 'file', owner=os.getuid() + 1, mode=0o600, limit=32)
        real_read = guest_files.os.read
        def replace(desc, count):
            result = real_read(desc, count)
            if count != 1:
                path.rename(tmp_path / 'old')
                path.write_bytes(b'payload')
                path.chmod(0o600)
            return result
        monkeypatch.setattr(guest_files.os, 'read', replace)
        with pytest.raises(ValueError):
            guest_files.read_regular(fd, 'file', owner=os.getuid(), mode=0o600, limit=32)
    finally:
        os.close(fd)


@pytest.mark.parametrize('fault', [None, 'owner', 'mode', 'hardlink', 'symlink'])
def test_product_private_witness_allows_inherited_group_but_keeps_pinned_file_guards(tmp_path, monkeypatch, fault):
    path = tmp_path / 'witness'
    path.write_bytes(b'installed product bytes')
    path.chmod(0o600)
    if fault == 'mode': path.chmod(0o640)
    if fault == 'hardlink': os.link(path, tmp_path / 'second')
    if fault == 'symlink':
        path.rename(tmp_path / 'preserved')
        path.symlink_to(tmp_path / 'preserved')
    inode = path.stat().st_ino
    real_stat, real_fstat = guest.os.stat, guest.os.fstat
    def declared(info):
        # Guest root ownership is simulated; the filesystem primitives still
        # pin actual pytest-private descriptors, modes, links and identities.
        if info.st_ino != inode:
            return info
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        values.update(st_uid=1001 if fault == 'owner' else 0, st_gid=10)
        return SimpleNamespace(**values)
    monkeypatch.setattr(guest.os, 'stat', lambda *args, **options: declared(real_stat(*args, **options)))
    monkeypatch.setattr(guest.os, 'fstat', lambda fd: declared(real_fstat(fd)))
    @contextmanager
    def pinned_parent(parent, account):
        assert parent == tmp_path and account.pw_uid == 0
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            yield fd, lambda: None
        finally:
            os.close(fd)
    monkeypatch.setattr(guest, 'directory', pinned_parent)
    if fault:
        with pytest.raises(ValueError): guest.activity_root_file(path, gid=None)
    else:
        assert guest.activity_root_file(path, gid=None) == b'installed product bytes'
        # Native and baseline callers retain their explicit exact-group guard.
        with pytest.raises(ValueError): guest.activity_root_file(path, gid=0)


def test_controller_uncertain_transport_never_replays(monkeypatch):
    verified = SimpleNamespace(recheck=Mock(), asset_files={name: hashlib.sha256(name.encode()).hexdigest()
                                                         for name in sources()})
    transport = SimpleNamespace(config={'run': 'owned'}, guard=Mock(), call=Mock(side_effect=OSError))
    fixture = controller.NativeFixtures(transport, verified)
    with pytest.raises(OSError): fixture.verify()
    with pytest.raises(EvidenceError, match='replay'): fixture.verify()
    assert fixture.failed and transport.call.call_count == 1


def test_all_public_fixture_rows_and_default_matches_are_required():
    rows = controller.expected_rows()
    assert controller.check_catalogue(AppRowsObservation(rows))['declared_launchers'] == 4
    for changed in (rows[:-1], tuple((row[0], 'allowed', 'precise') for row in rows),
                    tuple((row[0], 'permanent', row[2]) for row in rows)):
        with pytest.raises(EvidenceError): controller.check_catalogue(AppRowsObservation(changed))


@pytest.mark.parametrize('fault', ['missing', 'match'])
def test_catalogue_failure_retains_closed_fixture_diagnostics(fault, capsys):
    rows = controller.expected_rows()
    changed = rows[:-1] if fault == 'missing' else tuple(
        (row[0], row[1], 'precise') for row in rows)
    # Unrelated public IDs are neither identities nor diagnostic payloads here.
    changed += (('parent-app-' + 'f' * 16, 'allowed', 'precise'),)
    with pytest.raises(EvidenceError, match='^native:catalogue-defaults$'):
        controller.check_catalogue(AppRowsObservation(changed))
    output = capsys.readouterr()
    assert not output.out
    diagnostic = json.loads(output.err.removeprefix('native:catalogue-diagnostic='))
    assert diagnostic['row_count'] == len(changed)
    assert len(diagnostic['fixtures']) == 4
    assert {item['id'] for item in diagnostic['fixtures']} == {row[0] for row in rows}
    for item in diagnostic['fixtures']:
        expected = next(row[1:] for row in rows if row[0] == item['id'])
        actual = next((row[1:] for row in changed if row[0] == item['id']), None)
        assert item['expected'] == list(expected)
        assert item['present'] == (actual is not None)
        assert item['actual'] == (list(actual) if actual is not None else None)


def test_guest_refusal_checks_actual_authority_and_preserves_empty_entry(payload, monkeypatch):
    child, expected = payload
    monkeypatch.setattr(guest, 'authority', Mock(side_effect=guest.session_control.SessionError('session:source-owner')))
    assert guest.execute('refuse', expected) == {'wrong_entry_refused': True}


def test_preparation_authority_and_public_selection_bind_same_child(monkeypatch):
    import accessible_ui
    import baseline_fixtures
    from tests.fixtures.baseline_assets import native_files
    names = ('onpc-child-riley', 'onpc-child-jordan', 'onpc-parent-jamie')
    accounts = {name: SimpleNamespace(pw_name=name, pw_uid=1001 + index,
        pw_gid=1001 + index, pw_dir='/home/' + name) for index, name in enumerate(names)}
    passwd = '\n'.join(f'{name}:x:{user.pw_uid}:{user.pw_gid}::{user.pw_dir}:/bin/bash'
                       for name, user in accounts.items()).encode()
    prepared = baseline_fixtures.accounts(SimpleNamespace(read_file=Mock(return_value=passwd)))
    monkeypatch.setattr(guest.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(guest.pwd, 'getpwnam', accounts.__getitem__)
    monkeypatch.setattr(guest.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(guest.os, 'getgrouplist', lambda *_: [27])
    monkeypatch.setattr(guest.session_control, 'sessions', lambda: {})
    monkeypatch.setattr(guest.session_control, 'source_session', lambda *_: 'parent-session')
    child, _, _ = guest.authority()
    assert child.pw_uid == prepared['other'].pw_uid
    assert child.pw_name == accessible_ui.CHILD_ACCOUNTS[accessible_ui.EXISTING_CHILD]
    files = native_files(prepared)
    for path, _ in guest.destinations(child).values():
        assert files[str(path)][2] == 'other'
    for stage in ('child-picker-opened', 'child-choice-highlighted', 'parent-selected'):
        operation = PLAN.screen_tags[stage].removeprefix('ui:')
        bindings = (accessible_ui.PICKER_OPERATIONS | accessible_ui.HIGHLIGHT_OPERATIONS
                    | accessible_ui.SETTINGS_OPERATIONS)
        assert bindings[operation] == accessible_ui.EXISTING_CHILD
    assert PLAN.screen_tags['apps-page'] == 'ui:existing-apps'
    for stage in ('app-rows', 'wrong-child', 'wrong-page', 'reopened-rows'):
        operation = PLAN.screen_tags[stage].removeprefix('ui:')
        assert operation in accessible_ui.APP_ROW_OPERATIONS and operation.startswith('existing-')


def test_worker_sequence_matches_plan_and_stops_on_preparation_failure():
    from tests.support.perl import run_perl
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'}=1; $INC{'onpc_parent.pm'}=1; $INC{'onpc_gdm.pm'}=1; }
package testapi; sub record_info {} sub power {push @main::events, 'power'} sub check_shutdown {1}
sub console {bless {}, 'Console'}
package Console; sub disable {}
package onpc_gdm; sub reattach_functional {}
package onpc_parent;
sub enter_desktop {my ($j,@args)=@_; die 'entry' unless join(',',@args) eq 'gdm,parent,fresh,success';
    for ('installed-greeter','parent-focused','recipient-qualified','recipient-rechecked') {$j->seen($_)}
    return $j->seen('desktop');}
sub launch {my($j,$desktop,$expected)=@_; die 'launch' unless $expected eq 'management';
    $j->consume_observation('desktop',$desktop); $j->seen('parent-command'); $j->seen('parent-window');}
sub select_child {my($j,$child,$opened)=@_; die 'child' unless $child eq 'existing';
    $j->consume_observation('child-picker-opened',$opened); $j->seen('child-choice-highlighted');
    return $j->seen('parent-selected');}
package main;
require onpc_app_rows;
eval {onpc_app_rows::native_fixtures(sub {push @events,$_[0]; FAIL return {observed=>$_[0]};});};
print encode_json(\@events);
'''
    for failure in (False, True):
        result = run_perl(program.replace('FAIL', "die 'refused' if $_[0] eq 'desktop';" if failure else ''))
        expected = list(PLAN.screen_tags)
        assert json.loads(result.stdout) == (expected[:expected.index('desktop') + 1]
                                            if failure else expected + ['power'])


def test_qualification_reuses_baseline_without_asset_transfer():
    from parent_setup_qualification import NativeFixtureQualification, KioskEntryQualification
    assert issubclass(NativeFixtureQualification, KioskEntryQualification)
    assert NativeFixtureQualification.prepare_context is KioskEntryQualification.prepare_context
    context = SimpleNamespace(lease=Mock(), verified=Mock())
    qualification = object.__new__(NativeFixtureQualification)
    journey = qualification.journey(context, Mock())
    assert isinstance(journey, NativeFixtureJourney) and journey.plan is PLAN


@pytest.mark.parametrize('fault', [None, 'missing', 'bytes', 'mode', 'link', 'foreign-owner', 'wrong-target'])
def test_riley_same_target_readback_preserves_shared_owner_and_never_repairs(payload, monkeypatch, fault):
    from tests.fixtures.native_assets import riley_grid_sources
    shared, all_expected = payload
    home = Path(shared.pw_dir).parent / 'riley-home'
    launcher = home / '.local/share/applications' / desktop_id('A')
    private_directories(launcher.parent, guest.ROOT_DIRECTORY)
    launcher.write_bytes(desktop_entry(ASSETS[0]).encode())
    launcher.chmod(0o644)
    riley = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid() + 1000, pw_gid=os.getgid() + 1000)
    monkeypatch.setattr(guest.pwd, 'getpwnam', lambda name: riley if name == guest.session_control.ACCOUNTS['child'] else shared)
    real_directory = guest.directory
    # Host-private directories physically belong to the test runner. Leaf
    # metadata below separately checks the declared guest ownership split.
    monkeypatch.setattr(guest, 'directory', lambda path, owner: real_directory(path, shared))
    expected = {source: all_expected[source] for source in riley_grid_sources()}
    real_read = guest.read_regular
    calls = []
    def read(fd, name, *, owner, **options):
        calls.append((name, owner))
        data, info = real_read(fd, name, owner=os.getuid(), **options)
        if owner == riley.pw_uid:
            assert name == desktop_id('A')
            if fault == 'foreign-owner': raise ValueError('files:refused')
            info = SimpleNamespace(**{key: getattr(info, key) for key in
                ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')},
                st_uid=riley.pw_uid, st_gid=riley.pw_gid)
        return data, info
    monkeypatch.setattr(guest, 'read_regular', read)
    if fault == 'missing': launcher.unlink()
    if fault == 'bytes': launcher.write_bytes(b'changed')
    if fault == 'mode': launcher.chmod(0o777)
    if fault == 'link':
        launcher.rename(launcher.with_suffix('.preserved'))
        launcher.symlink_to(launcher.with_suffix('.preserved'))
    if fault == 'wrong-target':
        launcher.write_bytes(desktop_entry(ASSETS[1]).encode())
        # Even a caller digest matching a different launcher cannot change A's target.
        expected[riley_grid_sources()[-1]] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    before = {path: path.lstat() for path in home.rglob('*')}
    if fault:
        with pytest.raises((ValueError, OSError)): guest.execute('read', expected, 'riley-grid')
    else:
        first = guest.execute('read', expected, 'riley-grid')
        assert guest.execute('read', expected, 'riley-grid') == first
        assert set(first['files']) == set(riley_grid_sources()) and first['launchers'] == [desktop_id('A')]
        assert all(owner == shared.pw_uid for name, owner in calls if name != desktop_id('A'))
        assert (desktop_id('A'), riley.pw_uid) in calls
    # Read access may change atime; no contents, identity or write clocks change.
    signature = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                              info.st_mtime_ns, info.st_ctime_ns)
    assert {path: signature(path.lstat()) for path in before} == {path: signature(info) for path, info in before.items()}


def test_riley_controller_reads_its_finite_profile_twice(monkeypatch):
    from tests.fixtures.native_assets import riley_grid_sources
    expected = {source: hashlib.sha256(source.encode()).hexdigest() for source in sources()}
    value = {'files': {source: {} for source in riley_grid_sources()}, 'launchers': [desktop_id('A')]}
    transport = SimpleNamespace(config={'run': 'owned'}, guard=Mock(), call=Mock(
        return_value=(json.dumps(value, sort_keys=True) + '\n').encode()))
    verified = SimpleNamespace(recheck=Mock(), asset_files=expected)
    fixture = controller.NativeFixtures(transport, verified, profile='riley-grid')
    assert fixture.verify() == {'verified': 1, 'verified_files': 9, 'independent_readback': True}
    assert transport.call.call_count == 2
    for call in transport.call.call_args_list:
        assert call.args[0][4] == 'riley-grid'
        assert json.loads(call.args[0][5]) == {source: expected[source] for source in riley_grid_sources()}
    with pytest.raises(EvidenceError, match='replay'): fixture.verify()


def test_riley_requires_the_same_fedora_policy_guard_before_any_file_read(payload, monkeypatch):
    from tests.fixtures.native_assets import riley_grid_sources
    shared, all_expected = payload
    expected = {source: all_expected[source] for source in riley_grid_sources()}
    policy = Mock(side_effect=ValueError('files:native-policy-unproven'))
    monkeypatch.setattr(guest, 'verify_native_policy', policy)
    reader = Mock()
    monkeypatch.setattr(guest, 'read_regular', reader)
    with pytest.raises(ValueError, match='native-policy-unproven'):
        guest.riley_readback(shared, expected)
    policy.assert_called_once_with(expected)
    reader.assert_not_called()
