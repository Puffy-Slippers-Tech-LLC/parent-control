"""Ordinary GDM account-navigation qualification contracts."""

import json
from pathlib import Path

from tests.support.paths import ROOT
from tests.support.perl import run_perl
from tests.support.gdm_navigation import RUN


def test_worker_repeats_selection_from_an_independent_list_and_escapes_once():
    result = json.loads(run_perl(RUN).stdout)
    assert result['ok'], result['error']
    assert [event[1] for event in result['events'] if event[0] == 'exchange'] == [
        'initial-list', 'initial-focused', 'initial-prompt', 'initial-returned',
        'repeated-list', 'repeated-focused', 'repeated-prompt', 'repeated-returned',
    ]
    assert [event[1] for event in result['events'] if event[0] == 'key'] == [
        'ret', 'esc', 'ret', 'esc']
    assert result['events'][-3:] == [
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]


def test_gdm_navigation_qualification_reuses_the_prepared_app_snapshot():
    import check_e2e_gdm_navigation as check
    from parent_setup_qualification import GdmNavigationQualification

    assert check.ASSETS == Path(__file__).resolve().parents[2] / 'output/test-runs/host/allocations/onpc-parent-setup-input'
    context = type('Context', (), {})()
    journey = GdmNavigationQualification.journey(context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert list(journey.plan.screen_tags) == [
        'initial-list', 'initial-focused', 'initial-prompt', 'initial-returned',
        'repeated-list', 'repeated-focused', 'repeated-prompt', 'repeated-returned',
    ]


def test_gdm_navigation_is_the_fixed_argument_free_integration_selector():
    source = (ROOT / 'tests/integration/check_e2e_gdm_navigation.py').read_text()
    assert "ASSETS = named_input()" in source
    assert 'gdm_navigation=True' in source
    assert 'sys.argv' not in source
