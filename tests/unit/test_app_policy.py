"""Keep versioned wildcard choices when an updater replaces a desktop ID."""

import copy

import pytest

from common.oh_no_parent_control_ui.app_policy import replacement_policy_ids


def policy(pattern='/apps/Lunar Client-*.AppImage'):
    return {'state': 'conditional', 'targets': ['/apps/Lunar Client-1.AppImage'],
            'patterns': [pattern] if pattern else [], 'user_saved_match_rule': False}


def app(app_id='new.desktop', target='/apps/Lunar Client-2.AppImage'):
    return {'id': app_id, 'targets': [target]}


def test_replacement_is_based_on_saved_pattern_without_mutating_inputs():
    policies = {'old.desktop': policy()}
    applications = [app()]
    before = copy.deepcopy((policies, applications))
    assert replacement_policy_ids(policies, applications) == {'new.desktop': 'old.desktop'}
    assert (policies, applications) == before


@pytest.mark.parametrize('policies,applications', [
    ({'old.desktop': policy()}, []),
    ({'old.desktop': policy(None)}, [app()]),
    ({'old.desktop': policy()}, [app(target='/other/Lunar Client-2.AppImage')]),
    ({'old.desktop': policy()}, [app(target='/apps/subdir/Lunar Client-2.AppImage')]),
    ({'old.desktop': policy()}, [app(target='app/org.example.Game/x86_64/stable')]),
    ({'old.desktop': policy()}, [app('old.desktop'), app()]),
    ({'old.desktop': policy(), 'new.desktop': {'state': 'allowed'}}, [app()]),
    ({'old.desktop': policy()}, [app(), app('second.desktop')]),
    ({'old.desktop': policy(), 'other.desktop': policy()}, [app()]),
])
def test_precise_explicit_existing_and_ambiguous_choices_are_not_reassigned(policies, applications):
    assert replacement_policy_ids(policies, applications) == {}


def test_matching_never_uses_labels_or_desktop_id_similarity():
    assert replacement_policy_ids({'Lunar.desktop': policy()}, [
        dict(app('Lunar-updated.desktop', '/apps/Unrelated.AppImage'), name='Lunar Client')]) == {}


@pytest.mark.parametrize('custom', [False, True])
def test_equivalent_current_and_orphaned_rules_can_be_consolidated(custom):
    old, current = policy(), policy()
    old['user_saved_match_rule'] = current['user_saved_match_rule'] = custom
    assert replacement_policy_ids({'old.desktop': old, 'new.desktop': current}, [app()]) == {
        'new.desktop': 'old.desktop'}


def test_old_wrapper_default_and_payload_default_are_the_same_choice():
    current = policy(None)
    current['targets'] = ['/usr/bin/AppImageLauncher']
    application = dict(app(), suggested_patterns=['/apps/Lunar Client-*.AppImage'])
    policies = {'old.desktop': policy(), 'new.desktop': current}
    assert replacement_policy_ids(policies, [application]) == {'new.desktop': 'old.desktop'}
    current['user_saved_match_rule'] = True
    assert replacement_policy_ids(policies, [application]) == {}
    current['user_saved_match_rule'] = False
    current['state'] = 'permanent'
    assert replacement_policy_ids(policies, [application]) == {}
