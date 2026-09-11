"""Controller authorization requires current private capture and durable proofs."""

import hashlib
import json
import time
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_graphical_smoke as smoke
from private_artifacts import EvidenceError
import vt6_authentication
from vt6_authentication import Authentication, CAPTURE_FIELDS, REFERENCE, STAGES
from tests.support.perl import run_perl


@pytest.fixture
def gate(tmp_path):
    (tmp_path / 'testresults').mkdir(mode=0o700)
    source = smoke.ROOT / REFERENCE
    verified = Mock(root=smoke.ROOT, source_files={REFERENCE: hashlib.sha256(source.read_bytes()).hexdigest()},
                    inputs={'source_sha256': 'e' * 64})
    boot = {'boot_sha256': 'a' * 64}
    active = {'active_vt6_verified': True}
    password = {**boot, **active, 'vt6_login_process_verified': True,
                'terminal_echo_disabled': True, 'vt6_recipient_continuity_verified': True}
    replies = {'boot': boot, 'vt6-getty-identity': {**boot, **active, 'vt6_getty_verified': True},
        'vt6-password-identity': password, 'vt6-password-recheck': password,
        'vt6-shell-identity': {**boot, **active, 'vt6_login_continuity_verified': True,
                               'vt6_foreground_shell_verified': True},
        'vt6-session': {**active, 'fixture_role': 'parent', 'unexpected_user_session': False,
                         'active_local_vt6_session': True}}
    command = Mock()
    command.prepare.return_value = {**boot, **active, 'vt6_login_continuity_verified': True,
        'vt6_command_input_authorized': True, 'command_challenge': 'd' * 64}
    command.complete.return_value = {**boot, **active, 'vt6_login_continuity_verified': True,
                                     'vt6_shell_ready_verified': True}
    observer = Mock(read=Mock(side_effect=lambda name: dict(replies[name])),
                    vt6_command_boundary=Mock(return_value=command))
    return Authentication(tmp_path, observer, verified), Mock(), source, replies


def advance(gate, count):
    auth, guard, source, _ = gate
    results = []
    for stage in STAGES[:count]:
        shot = None
        if stage == 'vt6-password-screen':
            shot = 'smoke-9.png'
            (auth.directory / 'testresults' / shot).write_bytes(source.read_bytes())
        results.append(auth.observe(stage, shot, guard))
    return results


def test_controller_supplies_exact_worker_receipts_only_after_fresh_proofs(gate):
    auth, guard, _, _ = gate
    results = advance(gate, 5)
    assert [result['stage'] for result in results] == list(STAGES)
    assert all(result['boot_sha256'] == 'a' * 64 for result in results)
    assert results[2]['vt6_password_input_authorized'] is True
    assert set(results[3]) == {'stage', 'boot_sha256', 'active_local_vt6_session',
        'active_vt6_verified', 'vt6_login_continuity_verified',
        'vt6_command_input_authorized', 'command_challenge'}
    assert set(results[4]) == {'stage', 'boot_sha256', 'active_local_vt6_session',
        'active_vt6_verified', 'vt6_login_continuity_verified', 'vt6_shell_ready_verified'}
    assert guard.call_count == auth.verified.recheck.call_count == 10
    auth.observer.vt6_command_boundary.assert_called_once()


@pytest.fixture
def capture_gate(gate):
    # The guarded runner explicitly uses /tmp. The test launcher's default
    # pytest temporary root can be on a different filesystem/mount policy.
    with tempfile.TemporaryDirectory(prefix='onpc-vt6-capture-', dir='/tmp') as directory:
        gate[0].directory = Path(directory)
        (gate[0].directory / 'testresults').mkdir(mode=0o700)
        yield gate


def test_controller_accepts_fresh_installed_tinycv_capture(capture_gate):
    auth, guard, source, _ = capture_gate
    advance(capture_gate, 2)
    path = auth.directory / 'testresults/smoke-9.png'
    # The installed basetest::_result_add_screenshot writes through this API.
    # Exercise real PNG creation, including the thumbnail, before our first read.
    run_perl(r'''
use lib '/usr/lib/os-autoinst';
use cv;
BEGIN { cv::init(); }
use tinycv;
my $image = tinycv::read(shift) or die 'image unreadable';
$image->write_with_thumbnail(shift);
''', str(source), str(path))
    before = path.stat()
    assert before.st_nlink == 1
    assert (before.st_dev, before.st_ino) not in auth.existing_inodes
    assert before.st_mtime_ns >= auth.capture_after
    assert before.st_ctime_ns >= auth.capture_after
    # Live provenance verification delays the first read by about a minute.
    # stat_result tuple equality uses integer seconds, hiding first-read atime
    # updates in fast tests. Cross that boundary as the live recheck does.
    time.sleep(1.05)
    result = auth.observe('vt6-password-screen', path.name, guard)
    assert result['vt6_password_input_authorized'] is True
    assert auth.capture_evidence['capture_sha256'] == auth.verified.source_files[REFERENCE]


@pytest.mark.parametrize('view', ['descriptor', 'path'])
@pytest.mark.parametrize('field', CAPTURE_FIELDS)
def test_changed_capture_retains_exact_field_without_values_or_authorization(gate, monkeypatch, view, field):
    auth, guard, source, _ = gate
    advance(gate, 2)
    path = auth.directory / 'testresults/smoke-9.png'
    path.write_bytes(source.read_bytes())
    compare = vt6_authentication.verify_prompt_pixels

    def compare_then_change(*args):
        result = compare(*args)
        current = path.stat()
        changed = SimpleNamespace(**{name: getattr(current, name) for name in CAPTURE_FIELDS})
        setattr(changed, field, getattr(changed, field) + 1)
        if view == 'descriptor':
            monkeypatch.setattr(vt6_authentication.os, 'fstat', lambda fd: changed)
        else:
            original = Path.stat
            monkeypatch.setattr(Path, 'stat', lambda selected, **kwargs:
                changed if selected == path else original(selected, **kwargs))
        return result

    monkeypatch.setattr(vt6_authentication, 'verify_prompt_pixels', compare_then_change)
    code = f'vt6-auth:capture-{view}-{field.removeprefix("st_")}-refused'
    with pytest.raises(EvidenceError) as error:
        auth.observe('vt6-password-screen', path.name, guard)
    assert str(error.value) == auth.refusal == code
    assert auth.failed and auth.capture_evidence is None
    assert 'vt6-password-recheck' not in [call.args[0] for call in auth.observer.read.call_args_list]


@pytest.mark.parametrize('failure', [None, 'inputs', 'recipient', 'checkpoint'])
def test_password_diagnostics_bracket_cost_without_authorizing_or_hiding_failure(gate, failure):
    auth, guard, _, replies = gate
    advance(gate, 1)
    reports = []
    diagnostic = {'executable': 'login', 'login_timeout_seconds': 60,
                  'timeout_source': 'login.defs', 'login_version': '2.41.3',
                  'matches_pinned_recipient': True}
    replies['vt6-login-diagnostic'] = diagnostic
    auth.verified.recheck_milliseconds = {'source': 2, 'assets': 0, 'baseline': 68000}
    def report(stage, value):
        assert stage == 'vt6-password-ready'
        reports.append(value)
        if failure == 'checkpoint':
            raise RuntimeError('private-canary')
    auth.on_diagnostic = report
    if failure == 'inputs':
        auth.verified.recheck.side_effect = RuntimeError('private-canary')
    if failure == 'recipient':
        read = auth.observer.read.side_effect
        def changed(name):
            if name == 'vt6-password-identity':
                raise RuntimeError('private-canary')
            return read(name)
        auth.observer.read.side_effect = changed
    if failure:
        with pytest.raises(EvidenceError, match='vt6-auth:.*-refused'):
            auth.observe('vt6-password-ready', None, guard)
        assert auth.failed
    else:
        assert auth.observe('vt6-password-ready', None, guard)['terminal_echo_disabled'] is True
    assert [r['phase'] for r in reports] == {
        None: ['before-inputs', 'inputs-before', 'after-inputs', 'inputs-after'],
        'inputs': ['before-inputs', 'inputs-before'],
        'recipient': ['before-inputs', 'inputs-before', 'after-inputs'],
        'checkpoint': ['before-inputs']}[failure]
    assert 'private-canary' not in json.dumps(reports)
    assert 'authorized' not in json.dumps(reports)


@pytest.mark.parametrize('fault', ['existing', 'old-time', 'symlink', 'hardlink',
    'wrong-pixels', 'reference', 'name', 'wrong-stage', 'late-boot', 'recipient',
    'before-worker', 'after-worker', 'before-inputs', 'after-inputs', 'directory-link',
    'directory-replaced', 'renamed-old-image'])
def test_authorization_refuses_stale_capture_and_late_proof_loss(gate, fault):
    auth, guard, source, replies = gate
    path = auth.directory / 'testresults/smoke-9.png'
    if fault in ('existing', 'renamed-old-image'):
        path.write_bytes(source.read_bytes())
    advance(gate, 2)
    path.write_bytes(source.read_bytes())
    shot = 'smoke-9.png'
    if fault == 'old-time':
        import os
        os.utime(path, ns=(1, 1))
    elif fault == 'symlink':
        path.unlink()
        path.symlink_to(source)
    elif fault == 'hardlink':
        import os
        os.link(path, auth.directory / 'testresults/link.png')
    elif fault == 'wrong-pixels':
        path.write_bytes(b'bad image')
    elif fault == 'reference':
        auth.verified.source_files[REFERENCE] = 'b' * 64
    elif fault in ('directory-link', 'directory-replaced'):
        directory = auth.directory / 'testresults'
        directory.rename(auth.directory / 'old-results')
        if fault == 'directory-link':
            directory.symlink_to(auth.directory / 'old-results')
        else:
            directory.mkdir(mode=0o700)
            path.write_bytes(source.read_bytes())
    elif fault == 'renamed-old-image':
        shot = 'smoke-10.png'
        path.rename(path.with_name(shot))
    elif fault == 'late-boot':
        reads = auth.observer.read.side_effect
        count = 0
        def changed(name):
            nonlocal count
            if name == 'boot':
                count += 1
                return {'boot_sha256': ('b' if count > 1 else 'a') * 64}
            return reads(name)
        auth.observer.read.side_effect = changed
    elif fault == 'recipient':
        reads = auth.observer.read.side_effect
        def refused(name):
            if name == 'vt6-password-recheck':
                raise RuntimeError('private-canary')
            return reads(name)
        auth.observer.read.side_effect = refused
    elif fault.endswith('worker'):
        guard.side_effect = ([RuntimeError('private-canary')] if fault.startswith('before')
                             else [None, RuntimeError('private-canary')])
    elif fault.endswith('inputs'):
        auth.verified.recheck.side_effect = ([RuntimeError('private-canary')] if fault.startswith('before')
                                            else [None, RuntimeError('private-canary')])
    with pytest.raises(EvidenceError, match='vt6-auth:.*-refused'):
        auth.observe('vt6-password-ready' if fault == 'wrong-stage' else 'vt6-password-screen',
                     '../smoke-9.png' if fault == 'name' else shot, guard)
    calls = list(auth.observer.mock_calls)
    with pytest.raises(EvidenceError, match='previous-failure'):
        auth.observe('vt6-password-screen', 'smoke-9.png', guard)
    assert auth.observer.mock_calls == calls


@pytest.mark.parametrize('stage', STAGES)
def test_repeated_stage_never_issues_another_receipt(gate, stage):
    auth, guard, _, _ = gate
    advance(gate, STAGES.index(stage) + 1)
    with pytest.raises(EvidenceError, match='refused'):
        auth.observe(stage, 'smoke-9.png' if stage.endswith('-screen') else None, guard)


@pytest.mark.parametrize('fault', [None, 'checkpoint', 'late-worker', 'existing-reply', 'capture-refusal'])
def test_smoke_persists_authorization_before_publication(gate, fault):
    auth, guard, source, _ = gate
    advance(gate, 2)
    (auth.directory / 'testresults/smoke-9.png').write_bytes(source.read_bytes())
    stage = 'vt6-password-screen'
    reply = auth.directory / (stage + '.reply.json')
    def progress(name, observed):
        assert name == stage
        if observed is not None:
            assert not reply.exists()
            if fault == 'capture-refusal':
                assert observed == {'vt6_refusal': 'vt6-auth:capture-mtime-refused'}
                return
            assert observed['vt6_password_input_authorized'] is True
            if fault == 'checkpoint':
                raise RuntimeError('checkpoint')
    controller = smoke.Smoke(auth.directory, Mock(state={'run': 'f' * 32}), Mock(), 'host-key',
        authenticate=True, vt6_auth=True, verified=auth.verified, progress=progress)
    controller.steps = [{'stage': s} for s in smoke.VT6_AUTH_STAGES[:6]]
    controller._vt6_authentication = auth
    (auth.directory / (stage + '.request.json')).write_text(json.dumps(
        {'stage': stage, 'screenshot': 'smoke-9.png'}))
    if fault == 'late-worker':
        guard.side_effect = [None, None, None, RuntimeError('worker stopped')]
    if fault == 'existing-reply':
        reply.write_text('sentinel')
    if fault == 'capture-refusal':
        import os
        os.utime(auth.directory / 'testresults/smoke-9.png', ns=(1, 1))
    if fault:
        with pytest.raises((RuntimeError, AssertionError, EvidenceError)):
            controller.guarded_step(guard)
        assert reply.read_text() == 'sentinel' if reply.exists() else True
        with pytest.raises(RuntimeError, match='previous-failure'):
            controller.guarded_step(guard)
    else:
        controller.guarded_step(guard)
        assert json.loads(reply.read_text())['vt6_password_input_authorized'] is True
