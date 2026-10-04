"""Private pytest files, in-memory guest/transport doubles and waited Perl only.

No live account, VM, display, bus, shared cache or heavy fixture build. Compatible
in unit and cleanup scheduling; all ownership mutations remain process-local doubles.
"""
import hashlib
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
from tests.fixtures.native_assets import ASSETS, desktop_entry, desktop_id, sources
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
    assert len(first['files']) == 10
    assert unrelated.read_bytes() == b'preserve' and unrelated.stat() == before
    for source, (path, mode) in guest.destinations(child).items():
        assert path.stat().st_uid == child.pw_uid and path.stat().st_gid == child.pw_gid
        assert path.stat().st_mode & 0o777 == mode
    with pytest.raises(ValueError):
        guest.execute('prepare', expected)


@pytest.mark.parametrize('fault', ['digest', 'missing', 'bytes', 'mode', 'hardlink',
                                  'symlink', 'parent-link', 'parent-mode', 'launcher'])
def test_baseline_readback_refuses_without_repairing(payload, fault):
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
