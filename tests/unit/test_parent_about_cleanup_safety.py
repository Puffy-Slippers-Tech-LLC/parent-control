"""Customer controller preserves ownership and durable input acknowledgement."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import parent_about
import installed_journey
from private_artifacts import EvidenceError
from tests.support.needle_matcher import match_image, NEEDLES
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
    with pytest.raises(EvidenceError, match='boot-changed'):
        journey.step(Mock())
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


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
def test_terminal_evidence_refuses_missing_or_reused_return(tmp_path, monkeypatch, fault):
    details = []
    observations = []
    for index, (stage, tag) in enumerate(parent_about.SCREEN_TAGS.items()):
        if tag.startswith('ui:'):
            observations.append({'stage': stage, 'ui': {'operation': tag[3:], 'outcome': 'passed'}})
        else:
            details.append({'needle': tag, 'result': 'ok', 'area': [{'result': 'ok', 'similarity': 100}],
                            'screenshot': f'smoke-{index}.png'})
        details.append({'title': 'parent-' + stage, 'result': 'ok'})
    if fault == 'missing-return':
        details.pop()
    elif fault == 'stale-return':
        observations.pop()
    elif fault == 'wrong-child':
        observations[-1]['ui']['operation'] = 'about'
    elif fault == 'weak-match':
        details[0]['area'][0]['similarity'] = 99
    else:
        details[0]['needle'] = ('onpc-gdm-parent-baseline-installed-account' if fault != 'wrong-alternate'
                                else 'onpc-gdm-other-parent-baseline-installed-input-account')
        if fault == 'weak-alternate':
            details[0]['area'][0]['similarity'] = 99
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
    monkeypatch.setattr(installed_journey, 'screenshot', lambda *_: {'sha256': 'a'*64})
    if fault == 'alternate':
        screens = parent_about.matched_screens(tmp_path, observations)
        assert screens[0]['needle'] == 'onpc-gdm-parent-baseline-installed-account'
    else:
        with pytest.raises(EvidenceError, match='parent:'):
            parent_about.matched_screens(tmp_path, observations)
