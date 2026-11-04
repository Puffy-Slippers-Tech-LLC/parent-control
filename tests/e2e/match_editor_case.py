"""Case 185: a rejected match edit preserves the parent's enforced rule."""
from accessible_ui import MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_blocked_app,
                            native_usable_app, parent_management, prefixed_stages)
from match_rules import match_edit
from native_fixtures import fixture_actions
from parent_reports import report_close
from policy_edits import AppPolicyJourney
from ui_observations import SettingsObservation


SETUP = {
    **fresh_desktop('parent'), **parent_management(child='existing'),
    'parent-selected': 'ui:existing-returned',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'saved-settings': 'ui:existing-returned', 'apps-page': 'ui:existing-apps',
    'initial-rule': 'ui:match-row',
}
EDITS = {
    **match_edit('match-wildcard', 'confirmed',
                 editor=('confirmed-open', 'confirmed-read'), row='confirmed-rule'),
    'block-save': 'ui:access-permanent', 'blocked-access': 'ui:access-row',
    **match_edit('match-rejected-directory', 'rejected',
                 editor=('rejected-open', 'rejected-read'), row=None),
    **report_close('rejected'),
}
CHILD_ENTRY = prefixed_stages('child-entry', desktop_entry(
    'other-child', source='gdm', entry='fresh'))
RESULTS = {
    'restored-rule': 'ui:match-row', 'restored-access': 'ui:access-row',
    'parent-logout': 'system:parent-logout', **CHILD_ENTRY,
    **prefixed_stages('blocked', native_blocked_app('A')),
    **prefixed_stages('nonmatching', {
        **native_usable_app('command', role='N'),
        'close': 'ui:native-nonmatching-close', 'closed': 'ui:native-nonmatching-closed'}),
}
SCREENS = {**SETUP, **EDITS, **RESULTS}
PLAN = JourneyPlan(
    prefix='match-editor-case', worker_mode='match_editor_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EDITS},
            **{stage: 'step-3' for stage in RESULTS}},
    advance_after={'initial-rule': 'step-2', 'rejected-feedback-draft-closed': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={'initial-rule': MATCH_RULES[0], 'confirmed-open': 'initial-rule',
                  'confirmed-read': 'initial-rule', 'confirmed-rule': MATCH_RULES[1],
                  'rejected-open': 'confirmed-rule', 'rejected-read': 'confirmed-rule',
                  'restored-rule': 'confirmed-rule'},
    access_checks={'blocked-access': 'permanent', 'restored-access': 'permanent'},
    invocations=tuple(stage for stage, tag in CHILD_ENTRY.items() if tag.startswith('ui:')),
    challenges={'child-entry': ('other-child', 'child-entry-standard-recipient-qualified',
                               'child-entry-standard-recipient-rechecked')},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=AppPolicyJourney,
                             actions=fixture_actions(include_refusal=False))


E2E_CASES = {'match-editor': execute}
