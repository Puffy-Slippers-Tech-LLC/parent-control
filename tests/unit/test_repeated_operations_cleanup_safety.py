"""Repeated invocation identity, durable assertions and fixed VM dispatch."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_give_repeated_public_operations_distinct_stages as check
import check_graphical_smoke as smoke
from installed_journey import InstalledJourney
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, RepeatedOperationsQualification
from private_artifacts import EvidenceError
from repeated_operations import PLAN, RepeatedOperationsJourney


def test_fixed_dispatch_requires_assets_and_exclusive_route(monkeypatch):
    context = SimpleNamespace()
    assert issubclass(RepeatedOperationsQualification, KioskEntryQualification)
    assert isinstance(RepeatedOperationsQualification.journey(context, Mock()),
                      RepeatedOperationsJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'repeated_operations': True}]
    for options in ({}, {'assets': check.ASSETS, 'provision_credentials': True,
                         'parent_about': True}):
        with pytest.raises(CommandError, match='repeated-operations-prerequisites'):
            smoke.main(repeated_operations=True, **options)


@pytest.mark.parametrize('fault', ['stale-request', 'stale-reply', 'missing-result', 'changed-settings'])
def test_controller_failure_never_acknowledges_or_retries(tmp_path, fault):
    journey = InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), PLAN)
    stage = 'return-second'
    journey.steps = [{'stage': name} for name in PLAN.stages[:PLAN.stages.index(stage)]]
    settings = {'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['1 hour']}
    journey.check_settings('baseline-second', {'ui': {'settings': settings}})
    observed = {'operation': 'parent-screen-page', 'outcome': 'passed', 'settings': dict(settings)}
    if fault == 'missing-result':
        del observed['settings']
    if fault == 'changed-settings':
        observed['settings']['allowance'] = ['0 minutes']
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'boot'}))
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value=observed))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({
        'stage': 'return-first' if fault == 'stale-request' else stage, 'screenshot': None}))
    reply = tmp_path / (stage + '.reply.json')
    if fault == 'stale-reply':
        reply.write_text('old')
    with pytest.raises(EvidenceError):
        journey.step(Mock())
    if fault == 'stale-reply':
        assert reply.read_text() == 'old'
    else:
        assert not reply.exists()
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.validate()
    journey.progress.assert_not_called()
