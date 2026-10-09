"""Desktop-session qualification preserves durable acknowledgement and ownership."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import desktop_session
from private_artifacts import EvidenceError


@pytest.mark.parametrize('guest,filename,command', [
    ({'ubuntu_version': '26.04'}, 'package.deb', ['dpkg-deb', '-f']),
    ({'os_id': 'fedora', 'version': '44'}, 'package.rpm',
     ['rpm', '-qp', '--queryformat', '%{VERSION}']),
])
def test_snapshot_attachment_reads_verified_platform_package(tmp_path, guest, filename, command):
    from parent_setup_qualification import KioskEntryQualification
    qualification = object.__new__(KioskEntryQualification)
    qualification.assets = tmp_path
    qualification.commands = SimpleNamespace(run=Mock(return_value=b'1.4\n'))
    snapshot = SimpleNamespace(getXMLDesc=Mock(return_value='<domainsnapshot><memory snapshot="internal"/></domainsnapshot>'))
    domain = SimpleNamespace(snapshotLookupByName=Mock(return_value=snapshot))
    lease = SimpleNamespace(capture=SimpleNamespace(state={'guest': guest}),
                            source=SimpleNamespace(domain=domain))
    qualification.attach_installed_snapshot(lease)
    assert qualification.commands.run.call_args.args[0] == (
        command + [str(tmp_path / filename)] + (['Version'] if filename.endswith('.deb') else []))
    domain.snapshotLookupByName.assert_called_once_with('onpc-v1.4', 0)
    assert lease.online_pending is True


def test_input_preflight_failure_is_retained_before_cleanup(tmp_path, monkeypatch):
    import parent_setup_qualification as setup
    qualification = object.__new__(setup.ParentJourneyQualification)
    qualification.directory, qualification.assets = tmp_path, tmp_path
    qualification.commands = Mock()
    qualification.ledger = setup.smoke.runner.RunLedger()
    qualification.checkpoint = Mock()
    lease = SimpleNamespace(prepare=Mock(), guard=Mock(), save=Mock())
    monkeypatch.setattr(setup.smoke.runner, 'bootstrap', Mock(return_value='host key'))
    monkeypatch.setattr(setup.smoke, 'VerifiedInputs', Mock(
        side_effect=EvidenceError('provenance:package-platform')))
    with pytest.raises(EvidenceError, match='provenance:package-platform'):
        qualification.execute(lease, Mock())
    assert qualification.ledger.outcomes['infrastructure'] == {
        'outcome': 'failed', 'category': 'provenance:package-platform'}
    assert qualification.checkpoint.call_args.args == ('before-cleanup',)


@pytest.mark.parametrize('plan', [desktop_session.LOGOUT_PLAN, desktop_session.SWITCH_PLAN,
                                 desktop_session.LOCK_PLAN, desktop_session.SUPPLIED_LOCK_PLAN,
                                 desktop_session.LOCK_RECIPIENT_PLAN,
                                 desktop_session.CHILD_DENIAL_PLAN, desktop_session.RETAINED_DENIAL_PLAN],
                         ids=['logout', 'switch', 'lock', 'supplied-lock', 'lock-recipient', 'child-denial', 'gdm-denial'])
@pytest.mark.parametrize('failure', [None, 'checkpoint', 'worker-loss'])
def test_next_input_requires_persisted_observation_and_current_worker(tmp_path, plan, failure):
    reply = tmp_path / 'ready.reply.json'
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    recorded = []

    def progress(stage, observed):
        assert not reply.exists()
        if failure == 'checkpoint':
            raise OSError('checkpoint failed')
        recorded.append(stage)

    def guard():
        assert not reply.exists()
        if recorded and failure == 'worker-loss':
            raise RuntimeError('worker stopped')

    journey = desktop_session.DesktopSessionJourney(
        SimpleNamespace(directory=tmp_path), progress, plan)
    if failure:
        with pytest.raises((OSError, RuntimeError)):
            journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
    else:
        journey.step(guard)
        assert recorded == ['ready']
        assert json.loads(reply.read_text()) == {plan.worker_mode: True,
            **({'invocations': list(plan.invocations)} if plan.invocations else {}),
            **({'challenge_bindings': {key: list(value) for key, value in plan.challenges.items()}}
               if plan.challenges else {})}


@pytest.mark.parametrize('failure', ['', 'replaced', 'checkpoint', 'worker-loss'])
def test_retained_child_comparison_precedes_durable_return_reply(tmp_path, monkeypatch, failure):
    import session_control
    plan = desktop_session.CHILD_DENIAL_PLAN
    stage = 'retained-after'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    reply = tmp_path / (stage + '.reply.json')
    def progress(current, observed):
        assert not reply.exists()
        assert observed['comparison'] == {'same_retained_locked_child': True}
        if failure == 'checkpoint': raise OSError('checkpoint')
    journey = desktop_session.RetainedDenialJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.retained_session = 'a' * 64
    journey.boot = 'b' * 64
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={
        'operation': 'child-retained-locked', 'outcome': 'passed', 'interface': 'system session',
        'locked': True, 'session_sha256': ('c' if failure == 'replaced' else 'a') * 64}))
    guards = 0
    def guard():
        nonlocal guards
        guards += 1
        if failure == 'worker-loss' and guards > 1: raise RuntimeError('worker lost')
    if failure:
        with pytest.raises((EvidenceError, OSError, RuntimeError)): journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(guard)
        assert json.loads(reply.read_text()) == {'observed': stage}


@pytest.mark.parametrize('plan', [desktop_session.LOGOUT_PLAN, desktop_session.SWITCH_PLAN,
                                 desktop_session.LOCK_PLAN, desktop_session.SUPPLIED_LOCK_PLAN,
                                 desktop_session.LOCK_RECIPIENT_PLAN],
                         ids=['logout', 'switch', 'lock', 'supplied-lock', 'lock-recipient'])
def test_boot_replacement_refuses_before_next_customer_action(tmp_path, plan):
    stage = 'desktop'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    progress = Mock()
    journey = desktop_session.DesktopSessionJourney(
        SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    journey.transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        'operation': 'desktop', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
        'boot_sha256': 'b' * 64,
    }).encode()))
    with pytest.raises(EvidenceError, match='boot-changed'):
        journey.step(Mock())
    journey.transport.call.assert_called_once()
    assert journey.transport.call.call_args.args[0][-1] == 'a' * 64
    journey.vm.read.assert_not_called()
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('failure', ['', 'checkpoint', 'worker-loss', 'changed-surface'])
def test_actual_lock_reveal_recorder_decoder_refuses_before_reply(tmp_path, failure):
    from ui_observations import UiObservations
    plan = desktop_session.LOCK_PLAN
    stage = 'reveal-ready'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    reply = tmp_path / (stage + '.reply.json')
    observed = []

    def progress(current, result):
        assert not reply.exists()
        assert result['ui']['lock']['desktop_input_available'] is False
        if failure == 'checkpoint': raise OSError('checkpoint failed')
        observed.append(current)

    guard = Mock(side_effect=lambda: (_ for _ in ()).throw(RuntimeError('worker lost'))
                 if observed and failure == 'worker-loss' else None)
    journey = desktop_session.DesktopSessionJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        'operation': 'parent-lock-reveal-ready', 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'a' * 64,
        'lock': {'entry': 'curtain', 'owner': 'fixture-parent', 'locked': True,
            'desktop_input_available': False, 'recipient': None,
            'surface_id': ('c' if failure == 'changed-surface' else 'b') * 64,
            'provider': {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}}}).encode()))
    journey.ui = UiObservations(journey.transport)
    journey.ui.lock_surface_id = 'b' * 64
    if failure:
        with pytest.raises((OSError, RuntimeError, EvidenceError)): journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(guard)
        assert observed == [stage]
        assert json.loads(reply.read_text()) == {'observed': stage}


@pytest.mark.parametrize('failure', ['', 'checkpoint', 'worker-loss', 'changed-challenge', 'stale'])
def test_lock_recipient_real_recorder_persists_fresh_proof_before_reply(tmp_path, failure):
    from ui_observations import UiObservations
    import time
    plan = desktop_session.LOCK_RECIPIENT_PLAN
    stage = 'lock-recipient-rechecked'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    reply = tmp_path / (stage + '.reply.json')
    observed = []

    def progress(current, result):
        assert not reply.exists()
        assert result['ui']['lock']['empty'] is True
        if failure == 'checkpoint': raise OSError('checkpoint failed')
        observed.append(current)

    guard = Mock(side_effect=lambda: (_ for _ in ()).throw(RuntimeError('worker lost'))
                 if observed and failure == 'worker-loss' else None)
    journey = desktop_session.DesktopSessionJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        'operation': 'parent-lock-recipient-rechecked', 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'a' * 64,
        'lock': {'entry': 'challenge', 'owner': 'fixture-parent', 'locked': True,
            'desktop_input_available': False, 'recipient': 'fixture-parent',
            'surface_id': 'b' * 64, 'empty': True, 'masked': True, 'focused': True,
            'challenge_id': ('d' if failure == 'changed-challenge' else 'c') * 64,
            'provider': {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}}}).encode()))
    journey.ui = UiObservations(journey.transport)
    journey.ui.last_operation = 'parent-lock-recipient-qualified'
    journey.ui.lock_surface_id = 'b' * 64
    journey.ui.lock_recipient_id = 'c' * 64
    journey.ui.lock_recipient_checked = time.monotonic() - (30 if failure == 'stale' else 0)
    if failure:
        with pytest.raises((OSError, RuntimeError, EvidenceError)): journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(guard)
        assert observed == [stage]
        assert json.loads(reply.read_text()) == {'observed': stage,
            'lock_recipient': {'surface': 'lock', 'role': 'parent', 'challenge_id': 'c' * 64}}
