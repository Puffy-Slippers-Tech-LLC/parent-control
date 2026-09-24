"""Planned reboot authority, durable intent, boot continuity and fresh login."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_customer_reboot as check
import check_graphical_smoke as smoke
import customer_reboot as reboot
import installed_journey as journeys
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.perl import run_perl
from tests.unit.test_e2e_desktop_session import RUN_PROBE


BEFORE, AFTER = 'a' * 64, 'b' * 64


def boundary(tmp_path, monkeypatch, stage='reboot-requested'):
    progress = Mock()
    journey = reboot.CustomerRebootJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock()), progress)
    journey.steps = [{'stage': item} for item in reboot.PLAN.stages[:reboot.PLAN.stages.index(stage)]]
    journey.boot = BEFORE
    journey.transport = Mock()
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': BEFORE}),
        wait_boot_change=Mock(return_value={'previous_boot_sha256': BEFORE,
            'boot_sha256': AFTER, 'boot_changed': True}))
    journey.ui = Mock()
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={
        'operation': 'parent-command-context', 'outcome': 'passed'}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    return journey, progress


def test_fixed_launcher(monkeypatch):
    launch = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', launch)
    assert check.main() == 0
    launch.assert_called_once_with(assets=check.ASSETS, provision_credentials=True, customer_reboot=True)


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'product_free_entry': True},
    {'package_authority': True}, {'package_install': True}, {'challenges': True}])
def test_exclusive_product_free_entry(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError): smoke.main(customer_reboot=True, **kwargs)


@pytest.mark.parametrize('transition', [('missing', 'reboot-installed-greeter'),
    ('package-result', 'reboot-installed-greeter'), ('reboot-requested', 'reboot-desktop'),
    ['reboot-requested', 'reboot-installed-greeter']])
def test_only_adjacent_declared_command_and_gdm_transition_allowed(transition):
    with pytest.raises(EvidenceError, match='reboot-plan'):
        replace(reboot.PLAN, reboot_transition=transition)


@pytest.mark.parametrize('fault', ['', 'transport', 'guard', 'boot', 'context', 'intent'])
def test_submission_records_intent_before_one_input_and_never_replays(tmp_path, monkeypatch, fault):
    journey, progress = boundary(tmp_path, monkeypatch)
    def submit(boot):
        assert boot == BEFORE
        assert json.loads((tmp_path / 'customer-reboot-intent.json').read_text()) == {
            'stage': 'reboot-requested', 'previous_boot_sha256': BEFORE}
        if fault == 'transport': raise TimeoutError()
    journey.transport.request_customer_reboot.side_effect = submit
    if fault == 'boot': journey.vm.read.return_value = {'boot_sha256': AFTER}
    if fault == 'context': session_control.observe.side_effect = EvidenceError('wrong-context')
    if fault == 'intent': (tmp_path / 'customer-reboot-intent.json').write_text('preserve')
    guard = Mock(side_effect=EvidenceError('lost-owner') if fault == 'guard' else None)
    if fault:
        with pytest.raises((EvidenceError, TimeoutError, FileExistsError)): journey.step(guard)
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
        assert not (tmp_path / 'reboot-requested.reply.json').exists()
    else:
        journey.step(guard)
        assert (tmp_path / 'reboot-requested.reply.json').exists()
        assert progress.call_args.args[1]['reboot']['submitted']
        with pytest.raises(EvidenceError): journey.submit_reboot(Mock())
    assert journey.transport.request_customer_reboot.call_count == (fault in ('', 'transport'))


def test_live_wrong_entry_probe_refuses_reboot_before_transport(tmp_path, monkeypatch):
    journey, _ = boundary(tmp_path, monkeypatch, 'wrong-entry')
    result = reboot.refuse_reboot(journey, Mock())
    assert result['reboot_refused'] is True
    journey.transport.request_customer_reboot.assert_not_called()
    assert not (tmp_path / 'customer-reboot-intent.json').exists()


@pytest.mark.parametrize('fault', ['', 'unsubmitted', 'unchanged', 'changed-again', 'gdm', 'durability'])
def test_new_boot_requires_fresh_gdm_and_durable_result(tmp_path, monkeypatch, fault):
    journey, progress = boundary(tmp_path, monkeypatch, 'reboot-installed-greeter')
    stale = journey.ui
    fresh = Mock()
    fresh.observe.return_value = {'operation': 'gdm-list', 'outcome': 'passed'}
    monkeypatch.setattr(journeys, 'UiObservations', Mock(return_value=fresh))
    journey.reboot_submitted = fault != 'unsubmitted'
    journey.vm.read.return_value = {'boot_sha256': 'c' * 64 if fault == 'changed-again' else AFTER}
    if fault == 'unchanged': journey.vm.wait_boot_change.side_effect = EvidenceError('unchanged')
    if fault == 'gdm': fresh.observe.side_effect = EvidenceError('no-gdm')
    if fault == 'durability': progress.side_effect = OSError('storage failed')
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'reboot-installed-greeter.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        observed = progress.call_args.args[1]
        assert observed['boot_transition']['boot_sha256'] == AFTER
        assert observed['assertion']['id'] == 'changed-boot-usable-gdm'
        assert journey.boot == AFTER
        fresh.observe.assert_called_once_with('gdm-list')
    stale.observe.assert_not_called()
    journey.transport.request_customer_reboot.assert_not_called()


def test_unexpected_later_reboot_still_refuses(tmp_path, monkeypatch):
    journey, _ = boundary(tmp_path, monkeypatch, 'reboot-parent-focused')
    journey.reboot_submitted = journey.reboot_observed = True
    journey.vm.read.return_value = {'boot_sha256': AFTER}
    with pytest.raises(EvidenceError, match='boot-changed'): journey.step(Mock())
    journey.vm.wait_boot_change.assert_not_called()
    journey.ui.observe.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'reboot-requested', 'reboot-installed-greeter',
    'reboot-recipient-rechecked', 'reboot-desktop'])
def test_worker_uses_two_fresh_secret_proofs_and_stops_on_refusal(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::run')
    source = source.replace('}, $action);', "}, [qw(reboot-installed-greeter reboot-parent-focused "
        "reboot-recipient-qualified reboot-recipient-rechecked reboot-desktop)], "
        "{'after-reboot' => ['parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked']});")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'fixed refusal' if $_[0] eq $action;
        return {observed => $_[0], ui_focused => 1} if $_[0] eq 'reboot-installed-greeter';
        return {observed => $_[0], challenge => {id => 'after-reboot', role => 'parent',
            surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}}
            if $_[0] =~ /^reboot-recipient-/;
    """)
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    expected = list(reboot.PLAN.screen_tags)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault:
        assert result['events'].count(['secret']) == 2
        assert result['events'][-1] == ['power', 'off']
