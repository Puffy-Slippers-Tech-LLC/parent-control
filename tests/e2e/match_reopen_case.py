"""Case 186: saved matching, precise redisplay and rejected-save recovery."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_blocked_app, native_usable_app,
                            parent_management, parent_reopen, parent_selection, prefixed_stages)
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
SELECT_JORDAN = {
    **parent_selection(child='existing', screen_limits=True),
    'apps-page': 'ui:existing-apps',
}
CUSTOM = {
    **match_edit('match-wildcard', 'custom',
                 editor=('custom-open', 'custom-read'), row='custom-rule'),
    'allowed-save': 'ui:access-allowed', 'allowed-access': 'ui:access-row',
    **prefixed_stages('custom-reopen', parent_reopen()),
    **prefixed_stages('custom-return', SELECT_JORDAN),
    'remembered-rule': 'ui:match-row', 'remembered-access': 'ui:access-row',
    'suggested-rule': 'ui:match-soft-row',
}
PRECISE = {
    **match_edit('match-soft-precise', 'precise',
                 editor=('precise-open', 'precise-read'), row='precise-rule'),
    **prefixed_stages('select-riley', parent_selection(screen_limits=True)),
    **prefixed_stages('reselect-jordan', SELECT_JORDAN),
    'reselected-suggested': 'ui:match-soft-row',
    **match_edit('match-soft-precise', 'before-reopen',
                 editor=('before-reopen-open', 'before-reopen-read'), row='before-reopen-rule'),
    **prefixed_stages('precise-reopen', parent_reopen()),
    **prefixed_stages('precise-return', SELECT_JORDAN),
    'reopened-suggested': 'ui:match-soft-row',
    **match_edit('match-soft-precise', 'before-rejection',
                 editor=('before-rejection-open', 'before-rejection-read'), row='before-rejection-rule'),
    **match_edit('match-rejected-directory', 'rejected',
                 editor=('rejected-open', 'rejected-read'), row=None),
    **report_close('rejected'),
    'restored-rule': 'ui:match-row', 'restored-access': 'ui:access-row',
    'restored-suggested': 'ui:match-soft-row',
    **match_edit('match-soft-precise', 'recovered',
                 editor=('recovered-open', 'recovered-read'), row='recovered-rule'),
    'soft-save': 'ui:access-soft-conditional', 'soft-access': 'ui:access-soft-row',
    'final-precise': 'ui:match-soft-row',
}
CHILD_ENTRY = prefixed_stages('child-entry', desktop_entry(
    'other-child', source='gdm', entry='fresh'))
RESULTS = {
    'parent-logout': 'system:parent-logout', **CHILD_ENTRY,
    **prefixed_stages('blocked', native_blocked_app('S')),
    **prefixed_stages('allowed', {
        **native_usable_app('command'),
        'close': 'ui:native-close', 'closed': 'ui:native-closed'}),
}
SCREENS = {**SETUP, **CUSTOM, **PRECISE, **RESULTS}
SOFT = MATCH_APPS['S']
PLAN = JourneyPlan(
    prefix='match-reopen-case', worker_mode='match_reopen_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (*CUSTOM, *PRECISE)},
            **{stage: 'step-3' for stage in RESULTS}},
    advance_after={'initial-rule': 'step-2', 'final-precise': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS
                    and not stage.startswith('select-riley-')},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',)),
        **{prefix + '-parent-selected': SettingsObservation(
            'existing-fixture-child', True, ('30 minutes',))
           for prefix in ('custom-return', 'reselect-jordan', 'precise-return')},
        'select-riley-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={
        'initial-rule': MATCH_RULES[0], 'custom-open': 'initial-rule',
        'custom-read': 'initial-rule', 'custom-rule': MATCH_RULES[1],
        'remembered-rule': 'custom-rule', 'suggested-rule': (SOFT, MATCH_RULES[4]),
        **{stage: (SOFT, MATCH_RULES[4]) for stage in (
            'precise-open', 'precise-read', 'reselected-suggested',
            'before-reopen-open', 'before-reopen-read', 'reopened-suggested',
            'before-rejection-open', 'before-rejection-read', 'restored-suggested',
            'recovered-open', 'recovered-read')},
        **{stage: (SOFT, MATCH_RULES[5]) for stage in (
            'precise-rule', 'before-reopen-rule', 'before-rejection-rule',
            'recovered-rule', 'final-precise')},
        'rejected-open': 'custom-rule', 'rejected-read': 'custom-rule',
        'restored-rule': 'custom-rule'},
    access_checks={'allowed-access': 'allowed', 'remembered-access': 'allowed',
                   'restored-access': 'allowed', 'soft-access': (SOFT, 'conditional')},
    invocations=tuple(stage for stage, tag in CHILD_ENTRY.items() if tag.startswith('ui:')),
    challenges={'child-entry': ('other-child', 'child-entry-standard-recipient-qualified',
                               'child-entry-standard-recipient-rechecked')},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=AppPolicyJourney,
                             actions=fixture_actions(include_refusal=False))


E2E_CASES = {'match-reopen': execute}
