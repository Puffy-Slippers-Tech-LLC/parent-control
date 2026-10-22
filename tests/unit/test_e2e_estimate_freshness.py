"""Public calculation brackets distinguish countdown from an extra grant."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from installed_journey import JourneyPlan
from private_artifacts import EvidenceError
from request_composition import GrantAppEffectsJourney


def choice(seconds, start, end):
    return {'request': {
        'surface': 'child-overlay', 'form_count': 1, 'child': 'fixture-child',
        'approver': 'fixture-parent', 'duration_seconds': 75, 'custom_text': '1.25',
        'allow_soft': True, 'child_selector_enabled': False,
        'approver_selector_enabled': True, 'duration_enabled': True,
        'soft_choice_enabled': True, 'request_enabled': True, 'cancel_enabled': True,
        'message': '', 'mute': None},
        'estimate': {'kind': 'fixed', 'text': f'{seconds}s', 'seconds': seconds,
                     'precision_seconds': 1},
        'observed_monotonic_ns': round(end * 1e9),
        'estimate_read_bounds': [round(start * 1e9), round(end * 1e9)]}


def journey(tmp_path):
    plan = JourneyPlan('freshness', 'freshness', {
        'policy': 'ui:revoke-saved-balances',
        'before': 'ui:overlay-fraction-estimate-refresh',
        'after': 'ui:overlay-fraction-estimate-refresh'}, {})
    active = GrantAppEffectsJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
        settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
        app_rules={'fixture-app': ('conditional', 'precise')}, approval_stage='before',
        policy_reads={'policy': (None, 'zero')}, negative_estimates={'after': 'before'})
    active.balance = {'daily': {'seconds': 0, 'precision_seconds': 1},
        'one_time': {'seconds': 675, 'precision_seconds': 1},
        'observed_monotonic_ns': 1_000_000_000}
    return active


@pytest.mark.parametrize('extra', [0, 75])
def test_captured_estimate_values_require_actual_calculation_intervals(tmp_path, extra):
    active = journey(tmp_path)
    # Captured old/new values and read timestamps. The illustrative old
    # calculation bracket includes six seconds of label age; endpoint-only
    # subtraction incorrectly predicts about 440 instead of the observed 435.
    before = choice(491, 1085.873749078, 1091.873749078)
    after = choice(435 + extra, 1141.946701414, 1142.946701414)
    active.balance['one_time'] = {'seconds': 430, 'precision_seconds': 60}
    active.balance['observed_monotonic_ns'] = 1080_000_000_000
    active.check_settings('before', {'ui': {'valid_choice': before}})
    observed = {'ui': {'valid_choice': after}}
    if extra:
        with pytest.raises(EvidenceError, match='negative-added-time'):
            active.check_settings('after', observed)
    else:
        active.check_settings('after', observed)
        assert observed['comparison']['no_additional_grant_with_elapsed_bounds']


@pytest.mark.parametrize('fault', [
    'missing', 'tuple', 'bool', 'reversed', 'zero', 'wrong-end', 'wide-read',
    'overlap', 'uncertainty-hides-grant', 'elapsed', 'expired', 'precision',
    'changed-choice', 'extra-grant'])
def test_bad_or_ambiguous_public_calculation_evidence_refuses(tmp_path, fault):
    active = journey(tmp_path)
    before = choice(675, 100, 101)
    after = choice(665, 110, 111)
    if fault == 'missing': after.pop('estimate_read_bounds')
    if fault == 'tuple': after['estimate_read_bounds'] = tuple(after['estimate_read_bounds'])
    if fault == 'bool': after['estimate_read_bounds'][0] = True
    if fault == 'reversed': after['estimate_read_bounds'][0] = 112_000_000_000
    if fault == 'zero': after['estimate_read_bounds'][0] = 0
    if fault == 'wrong-end': after['estimate_read_bounds'][1] -= 1
    if fault == 'wide-read': after = choice(625, 110, 156)
    if fault == 'overlap': after = choice(675, 100.5, 102)
    if fault == 'uncertainty-hides-grant':
        before = choice(675, 100, 140)
        after = choice(610, 150, 190)
    if fault == 'elapsed': after = choice(550, 223, 224)
    if fault == 'expired':
        active.balance['one_time']['seconds'] = 10
        before = choice(85, 100, 101)
        after = choice(75, 110, 111)
    if fault == 'precision': after['estimate']['precision_seconds'] = 60
    if fault == 'changed-choice': after['request']['allow_soft'] = False
    if fault == 'extra-grant': after['estimate']['seconds'] += 75
    active.check_settings('before', {'ui': {'valid_choice': before}})
    with pytest.raises(EvidenceError):
        active.check_settings('after', {'ui': {'valid_choice': after}})
    assert 'after' not in active.effects_negative_seen


def test_deepcopy_replay_and_failed_step_never_publish_a_success_reply(tmp_path):
    active = journey(tmp_path)
    before = choice(675, 100, 101)
    active.check_settings('before', {'ui': {'valid_choice': before}})
    captured = deepcopy(active.effects_negative_seen['before'])
    before['estimate_read_bounds'][0] = 0
    before['estimate']['seconds'] = 1
    assert active.effects_negative_seen['before'] == captured
    with pytest.raises(EvidenceError, match='replay'):
        active.check_settings('before', {'ui': {'valid_choice': captured}})
    active.steps = [{'stage': stage} for stage in active.plan.stages[:-1]]
    active.boot = 'b' * 64
    active.ui = SimpleNamespace(boot_proof=active.boot,
        observe=Mock(return_value={'valid_choice': choice(740, 110, 111)}))
    active.collect_failure = Mock()
    (tmp_path / 'after.request.json').write_text(json.dumps({'stage': 'after', 'screenshot': None}))
    with pytest.raises(EvidenceError, match='negative-added-time'):
        active.step(Mock())
    assert active.failed and not (tmp_path / 'after.reply.json').exists()
    active.progress.assert_not_called()


def test_successful_pair_is_single_use(tmp_path):
    active = journey(tmp_path)
    active.check_settings('before', {'ui': {'valid_choice': choice(675, 100, 101)}})
    observed = {'ui': {'valid_choice': choice(665, 110, 111)}}
    active.check_settings('after', observed)
    with pytest.raises(EvidenceError, match='replay'):
        active.check_settings('after', observed)


def positive_journey(tmp_path):
    plan = JourneyPlan('approval-freshness', 'approval-freshness', {
        'approval': 'ui:overlay-fraction-estimate-refresh',
        'policy': 'ui:revoke-saved-balances'}, {})
    active = GrantAppEffectsJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
        settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
        app_rules={'fixture-app': ('conditional', 'precise')}, approval_stage='approval',
        policy_reads={'policy': (None, 'positive')}, approval_stages={'policy': 'approval'})
    active.balance = {'daily': {'seconds': 0, 'precision_seconds': 1},
        'one_time': {'seconds': 300, 'precision_seconds': 60},
        'observed_monotonic_ns': 1_000_000_000_000}
    return active


@pytest.mark.parametrize('seconds,end,read,grant', [
    (304, 1280.494051135, 1488.003243662, 94),
    (316, 1273.359709059, 1492.966555514, 93)])
@pytest.mark.parametrize('fault', [None, 'below-lower', 'above-upper', 'stale',
                                  'missing', 'wide', 'overlap', 'precision'])
def test_positive_approval_uses_calculation_start_without_relaxing_bounds(
        tmp_path, seconds, end, read, grant, fault):
    active = positive_journey(tmp_path)
    captured = choice(seconds, end - 6, end)
    # The retained endpoint-only lower bound rejected both observations.
    assert seconds - (read - end) - 1 > grant
    if fault == 'below-lower': grant = int(seconds - (read - (end - 6)) - 1) - 1
    if fault == 'above-upper': grant = seconds + 2
    if fault == 'stale': read = end - 6 + 600.001
    if fault == 'missing': captured.pop('estimate_read_bounds')
    if fault == 'wide': captured['estimate_read_bounds'][0] -= 40_000_000_000
    if fault == 'overlap': read = end - .1
    if fault == 'precision': captured['estimate']['precision_seconds'] = 60
    value = {'settings': active.effects_settings, 'apps': [['fixture-app', 'conditional']],
        'rules': [['fixture-app', 'precise']], 'balances': {
            'child': 'fixture-child', 'observed_monotonic_ns': round(read * 1e9),
            **{key: {'seconds': number, 'precision_seconds': 1}
               for key, number in (('daily', 0), ('one_time', grant), ('total', grant))}}}
    observed = {'ui': {'revoke_cancel': value}}
    if fault:
        with pytest.raises(EvidenceError):
            active.check_settings('approval', {'ui': {'valid_choice': captured}})
            active.check_settings('policy', observed)
        assert 'policy' not in active.effects_seen
    else:
        active.check_settings('approval', {'ui': {'valid_choice': captured}})
        captured['estimate_read_bounds'][0] = 0
        active.check_settings('policy', observed)
        assert observed['comparison']['positive_grant_with_elapsed_bounds']
        with pytest.raises(EvidenceError, match='replay'):
            active.check_settings('policy', observed)
