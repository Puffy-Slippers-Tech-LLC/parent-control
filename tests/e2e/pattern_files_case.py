"""Case 189: a parent's version pattern governs new files and survives rejection."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            native_blocked_app, native_usable_app, prefixed_stages,
                            retained_parent_entry)
from match_rules import match_edit
from native_fixtures import fixture_actions
from parent_reports import report_close
from policy_edits import AppPolicyJourney
from real_interval import interval_action
from ui_observations import SettingsObservation
from versioned_appimage_assets import versioned_copy_actions


SETUP = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                         initial_rows=False)
EDITS = {
    **match_edit('match-soft-wildcard', 'confirmed',
                 editor=('confirmed-open', 'confirmed-read'), row='confirmed-rule'),
    'block-save': 'ui:access-soft-permanent', 'blocked-access': 'ui:access-soft-row',
    'next-copy': 'ui:existing-apps', 'nonmatch-copy': 'ui:existing-apps',
}
CHILD_ENTRY = desktop_entry('other-child', source='gdm', entry='fresh')
PARENT_RETURN = desktop_entry('parent', source='gdm', entry='retained')
RESULTS = {
    **desktop_return('leave-parent', account='parent'),
    **prefixed_stages('child-entry', CHILD_ENTRY),
    **prefixed_stages('current', native_blocked_app('S')),
    **prefixed_stages('next', native_blocked_app('VersionNext')),
    **prefixed_stages('existing', {
        **native_usable_app('command', role='VersionExisting'),
        'close': 'ui:native-version-existing-close',
        'closed': 'ui:native-version-existing-closed'}),
    'refresh-interval': 'ui:standard-desktop',
    **prefixed_stages('new-nonmatch', {
        **native_usable_app('command', role='VersionNonmatch'),
        'close': 'ui:native-version-nonmatch-close',
        'closed': 'ui:native-version-nonmatch-closed'}),
    'child-logout': 'system:standard-logout', 'child-greeter': 'ui:gdm-returned',
    **prefixed_stages('parent-return', PARENT_RETURN),
    **prefixed_stages('supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)),
    'returned-apps': 'ui:existing-apps',
    **match_edit('match-soft-rejected-directory', 'rejected',
                 editor=('rejected-open', 'rejected-read'), row=None),
    **report_close('rejected'),
    'restored-rule': 'ui:match-soft-row', 'restored-access': 'ui:access-soft-row',
    'copies-cleanup': 'ui:existing-apps', 'parent-logout': 'system:parent-logout',
}
SCREENS = {**SETUP, **EDITS, **RESULTS}
LOGIN_STAGES = {prefix + '-' + stage for prefix, entry in (
    ('child-entry', CHILD_ENTRY), ('parent-return', PARENT_RETURN))
    for stage, tag in entry.items() if tag.startswith('ui:')}
PLAN = JourneyPlan(
    prefix='pattern-files-case', worker_mode='pattern_files_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EDITS},
            **{stage: 'step-3' for stage in RESULTS}},
    advance_after={'apps-page': 'step-2', 'nonmatch-copy': 'step-3'},
    stage_actions={'desktop': 'native-verify', 'next-copy': 'version-next-copy',
                   'nonmatch-copy': 'version-nonmatch-copy',
                   'refresh-interval': 'refresh-interval', 'copies-cleanup': 'version-cleanup'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={**{stage: (MATCH_APPS['S'], MATCH_RULES[4]) for stage in (
        'confirmed-open', 'confirmed-read', 'confirmed-rule')},
        'rejected-open': 'confirmed-rule', 'rejected-read': 'confirmed-rule',
        'restored-rule': 'confirmed-rule'},
    access_checks={stage: (MATCH_APPS['S'], 'permanent') for stage in (
        'blocked-access', 'restored-access')},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={
        'child-entry': ('other-child', 'child-entry-standard-recipient-qualified',
                        'child-entry-standard-recipient-rechecked'),
        'parent-return': ('parent', 'parent-return-recipient-qualified',
                          'parent-return-recipient-rechecked')})


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        journey_type=AppPolicyJourney, actions={
            **fixture_actions(include_refusal=False),
            **versioned_copy_actions(administrative=True),
            'refresh-interval': interval_action(60)})


E2E_CASES = {'pattern-files': execute}
