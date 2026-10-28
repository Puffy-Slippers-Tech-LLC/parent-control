"""Customer controller preserves ownership and durable input acknowledgement."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.support.needle_matcher import match_image

import parent_about
import installed_journey
from private_artifacts import EvidenceError
from tests.support.paths import ROOT


@pytest.mark.parametrize('failure', [None, 'checkpoint', 'worker-loss'])
def test_next_input_requires_persisted_observation_and_current_worker(tmp_path, failure):
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

    journey = parent_about.ParentJourney(SimpleNamespace(directory=tmp_path), progress)
    if failure:
        with pytest.raises((OSError, RuntimeError)):
            journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
    else:
        journey.step(guard)
        assert recorded == ['ready']
        assert json.loads(reply.read_text()) == {'parent_about': True}


def test_boot_replacement_refuses_before_next_customer_action(tmp_path):
    stage = 'desktop'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    progress = Mock()
    journey = parent_about.ParentJourney(SimpleNamespace(directory=tmp_path), progress)
    journey.steps = [{'stage': s} for s in parent_about.STAGES[:parent_about.STAGES.index(stage)]]
    journey.boot = 'a' * 64
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b'*64}))
    journey.ui = SimpleNamespace(boot_proof=None,
        observe=Mock(side_effect=EvidenceError('ui:boot-changed')))
    with pytest.raises(EvidenceError, match='boot-changed'):
        journey.step(Mock())
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()
    assert journey.ui.boot_guard == 'a' * 64
    journey.vm.read.assert_not_called()


def test_installed_prompt_matches_existing_qualified_secret_recipient():
    result = match_image(ROOT / 'tests/fixtures/installed-parent-prompt.png',
                         'onpc-gdm-parent-masked-password')
    assert result['ok'] and all(area['similarity'] == 1 for area in result['area']), result


def test_installed_other_parent_click_region_refuses_parent_prompt():
    result = match_image(ROOT / 'tests/fixtures/installed-parent-prompt.png',
                         'onpc-gdm-other-parent-installed-input-account')
    assert not result['ok'], result


def test_installed_wrong_role_prompt_refuses_the_parent_secret_needle():
    result = match_image(ROOT / 'tests/fixtures/installed-other-parent-prompt.png',
                         'onpc-gdm-parent-masked-password')
    assert not result['ok'], result


@pytest.mark.parametrize('fault', ['missing-return', 'stale-return', 'wrong-child', 'weak-match',
                                  'alternate', 'wrong-alternate', 'weak-alternate'])
def test_terminal_evidence_refuses_missing_or_reused_return(tmp_path, fault):
    # Exercise the semantic result contract with otherwise complete evidence,
    # so an unrelated fixture refusal cannot satisfy the return checks.
    plan = parent_about.PLAN
    details = []
    observations = []
    for stage, tag in plan.screen_tags.items():
        kind, operation = tag.split(':', 1)
        observations.append({'stage': stage, kind: {
            'operation': operation, 'outcome': 'passed'}})
        details.append({'title': 'parent-' + stage, 'result': 'ok'})
    (tmp_path / 'testresults').mkdir()
    result = tmp_path / 'testresults/result-smoke.json'
    result.write_text(json.dumps({'result': 'ok', 'details': details}))
    screens = installed_journey.matched_screens(tmp_path, plan, observations)
    assert [screen['stage'] for screen in screens] == list(plan.screen_tags)
    assert screens[-1]['stage'] == 'parent-returned'
    if fault == 'missing-return':
        details.pop()
        result.write_text(json.dumps({'result': 'ok', 'details': details}))
        expected_error = '^parent:missing-screens$'
    elif fault == 'stale-return':
        # Keep the worker's return marker and every earlier observation:
        # neither can stand in for a fresh terminal UI observation.
        assert observations.pop()['stage'] == 'parent-returned'
        expected_error = '^parent:ui-evidence$'
    elif fault == 'weak-match':
        # A weak image match cannot replace the fresh terminal UI result.
        assert observations.pop()['stage'] == 'parent-returned'
        details.insert(-1, {'needle': 'onpc-parent-returned', 'result': 'ok',
                           'area': [{'result': 'ok', 'similarity': 99}],
                           'screenshot': 'smoke-returned.png'})
        result.write_text(json.dumps({'result': 'ok', 'details': details}))
        expected_error = '^parent:ui-evidence$'
    elif fault in ('alternate', 'wrong-alternate', 'weak-alternate'):
        # Diagnostic images may accompany complete semantic evidence, but
        # cannot replace the fresh terminal observation, regardless of score.
        needle = ('onpc-gdm-other-parent-baseline-installed-input-account'
                  if fault == 'wrong-alternate' else 'onpc-gdm-parent-baseline-installed-account')
        similarity = 99 if fault == 'weak-alternate' else 100
        details.insert(-1, {'needle': needle, 'result': 'ok',
                           'area': [{'result': 'ok', 'similarity': similarity}],
                           'screenshot': 'smoke-alternate.png'})
        result.write_text(json.dumps({'result': 'ok', 'details': details}))
        # Inserting a diagnostic before the final marker shifts only that
        # marker's source index; every semantic result must stay identical.
        expected_screens = [*screens[:-1], {
            **screens[-1], 'detail_index': screens[-1]['detail_index'] + 1}]
        assert installed_journey.matched_screens(tmp_path, plan, observations) == expected_screens
        assert observations.pop()['stage'] == 'parent-returned'
        expected_error = '^parent:ui-evidence$'
    else:
        assert observations[-1]['stage'] == 'parent-returned'
        observations[-1]['ui']['operation'] = 'about'
        expected_error = '^parent:ui-evidence$'
    with pytest.raises(EvidenceError, match=expected_error):
        installed_journey.matched_screens(tmp_path, plan, observations)
