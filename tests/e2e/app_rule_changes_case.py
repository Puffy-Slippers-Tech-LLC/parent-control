"""Cases 13–16: six app-rule transitions with explicit limit/match bindings."""
from dataclasses import replace
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, native_activity_entry, native_usable_app,
                            native_blocked_app, parent_reopen, parent_selection,
                            prefixed_stages, retained_app_activities, retained_app_visit)
from journey_checks import RetainedDesktopJourney, check_balances
from kiosk_approved_flow import obtain_time
from named_app_set import named_app_set
from policy_edits import NativePolicyJourney
from private_artifacts import require
from request_composition import KioskRequestJourney
from ui_observations import SettingsObservation


APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['S'], 'match-soft-precise', 'allowed'))
ROUNDS = (('allowed-soft', 'conditional'), ('soft-hard', 'permanent'),
          ('hard-soft', 'conditional'), ('soft-allowed', 'allowed'),
          ('allowed-hard', 'permanent'), ('hard-allowed', 'allowed'))
CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=75, allow_soft=True)
USERS = (('riley', 'child', 'fresh'),)
SCREENS = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read')
SCREENS.update(named_app_set(source='desktop', entry='same-user', window='retained',
                            child='existing', apps=APPS, prefix='setup-rules'))
SCREENS.update(retained_app_activities(USERS))
ENTRIES = {'riley': ('child', desktop_entry('child', source='gdm', entry='fresh'))}
MATCHES = {'setup-rules-saved-a-match': (MATCH_APPS['A'], MATCH_RULES[0]),
           'setup-rules-saved-s-match': (MATCH_APPS['S'], MATCH_RULES[5])}
ACCESSES = {'setup-rules-saved-a-access': (MATCH_APPS['A'], 'allowed'),
            'setup-rules-saved-s-access': (MATCH_APPS['S'], 'allowed')}
ACTIVITIES, ACTIVITY_ENTRIES, SESSION_CHECKS = {}, {}, {}


def entry(prefix, account, *, source, source_account=None, fresh=False):
    screens = desktop_entry(account, source=source, entry='fresh' if fresh else 'retained',
                            source_account=source_account)
    ENTRIES[prefix] = (account, screens)
    return prefixed_stages(prefix, screens)


SCREENS.update({
    **entry('jordan', 'other-child', source='gdm', fresh=True),
    **native_activity_entry('initial-matching', child='other-child', binding='policy'),
    **native_activity_entry('initial-nonmatching', child='other-child', binding='unmatched-soft'),
    'jordan-session': 'system:standard-entry-same',
    **entry('prepared-parent', 'parent', source='desktop', source_account='other-child'),
    'prepared-apps': 'ui:existing-apps',
})
PHASES = {stage: 'step-1' for stage in SCREENS}
matching_capture = 'initial-matching-capture'
nonmatching_capture = 'initial-nonmatching-capture'
for name, access in ROUNDS:
    group = {}
    if name in ('soft-hard', 'allowed-hard'):
        if name == 'soft-hard':
            # Read the actual remaining daily margin before a real 75-second
            # soft-included approval. No synthetic grant or revoke-first setup.
            group.update({
                'soft-opening-balance': 'ui:time-explanation-refresh-read',
                'soft-opening-desktop': 'ui:desktop',
                'soft-opening-switch': 'system:parent-switch-user',
                'soft-opening-greeter': 'ui:gdm-returned',
                **prefixed_stages('soft-opening', obtain_time(
                    initial='observed', **CHOICES, exit='automatic')),
            })
        group.update(entry(name + '-prepare', 'other-child',
            source='gdm' if name == 'soft-hard' else 'desktop',
            source_account=None if name == 'soft-hard' else 'parent'))
        group.update(native_activity_entry(name + '-opening', child='other-child', binding='policy'))
        matching_capture = name + '-opening-capture'
        group.update(entry(name + '-save-parent', 'parent', source='desktop', source_account='other-child'))
    # Verify the selected limit state before each tested access save. Matching
    # was set once by FLOW19; no extra match save can conceal a transition.
    group.update({name + '-settings': 'ui:discovery-ready', name + '-apps': 'ui:existing-apps',
                  name + '-save': 'ui:access-' + access, name + '-access': 'ui:access-row',
                  name + '-match': 'ui:match-row'})
    ACCESSES[name + '-access'] = (MATCH_APPS['A'], access)
    MATCHES[name + '-match'] = (MATCH_APPS['A'], MATCH_RULES[0])
    group.update(entry(name + '-result', 'other-child', source='desktop', source_account='parent'))
    ACTIVITY_ENTRIES[name + '-result-source-desktop'] = nonmatching_capture
    SESSION_CHECKS[name + '-result-entry-guard'] = 'jordan-session'
    if access != 'allowed':
        group[name + '-closed'] = 'ui:native-policy-closed'
        ACTIVITIES[name + '-closed'] = (matching_capture, 'closed')
        group.update(prefixed_stages(name + '-matching', native_blocked_app('A')))
    else:
        group.update(prefixed_stages(name + '-matching', {
            **native_usable_app('command'), 'close': 'ui:native-close', 'closed': 'ui:native-closed'}))
    # S's already-open secondary window is outside A's precise match. Compare
    # it before new input, use it, then independently test a new launch too.
    group.update({name + '-nonmatching-retained': 'ui:native-unmatched-soft-activity',
                  name + '-nonmatching-resubmit': 'ui:native-unmatched-soft-resubmit',
                  name + '-nonmatching-submitted': 'ui:native-unmatched-soft-submitted',
                  name + '-nonmatching-close': 'ui:native-unmatched-soft-close',
                  name + '-nonmatching-closed': 'ui:native-unmatched-soft-closed',
                  **native_activity_entry(name + '-nonmatching-new', child='other-child',
                                          binding='unmatched-soft')})
    ACTIVITIES[name + '-nonmatching-retained'] = (nonmatching_capture, 'same')
    nonmatching_capture = name + '-nonmatching-new-capture'
    group.update(retained_app_visit(name + '-riley', account='child', source='desktop',
                                    source_account='other-child'))
    ENTRIES[name + '-riley'] = ('child', desktop_entry('child', source='desktop', entry='retained',
                                                     source_account='other-child'))
    ACTIVITY_ENTRIES[name + '-riley-source-desktop'] = 'riley-activity-capture'
    ACTIVITIES[name + '-riley-activity-opened'] = ('riley-activity-capture', 'same')
    group[name + '-riley-usable'] = 'ui:overlay-native-activity'
    ACTIVITIES[name + '-riley-usable'] = ('riley-activity-capture', 'same')
    SESSION_CHECKS[name + '-riley-entry-guard'] = 'riley-desktop-identity'
    group.update(entry(name + '-parent', 'parent', source='desktop', source_account='child'))
    SCREENS.update(group)
    PHASES.update({stage: 'step-2' for stage in group})

FINAL = {**prefixed_stages('final-reopen', parent_reopen()),
         **prefixed_stages('final-child', parent_selection(child='existing', screen_limits=True)),
         'final-apps': 'ui:existing-apps', 'final-match': 'ui:match-row', 'final-access': 'ui:access-row'}
SCREENS.update(FINAL)
PHASES.update({stage: 'step-3' for stage in FINAL})
MATCHES['final-match'] = (MATCH_APPS['A'], MATCH_RULES[0])
ACCESSES['final-access'] = (MATCH_APPS['A'], 'allowed')
LOGIN_STAGES = {prefix + '-' + stage for prefix, (_account, screens) in ENTRIES.items()
                for stage in screens if stage in {
                    'installed-greeter', 'parent-focused', 'child-focused', 'standard-focused',
                    'recipient-qualified', 'recipient-rechecked', 'child-recipient-qualified',
                    'child-recipient-rechecked', 'standard-recipient-qualified',
                    'standard-recipient-rechecked', 'desktop'}}
PLAN = JourneyPlan(
    prefix='app-rule-changes', worker_mode='app_rule_changes_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **PHASES, 'installed-greeter': 'start'},
    advance_after={'installed-greeter': 'step-1', 'prepared-apps': 'step-2',
                   'hard-allowed-parent-desktop': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        **{stage: SettingsObservation('existing-fixture-child', True, ('30 minutes',))
           for stage in ('saved-settings', 'final-child-parent-selected',
                         *(name + '-settings' for name, _access in ROUNDS))}},
    match_checks=MATCHES, access_checks=ACCESSES,
    activity_checks=ACTIVITIES, activity_entries=ACTIVITY_ENTRIES,
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (account, prefix + '-' + recipient + 'qualified',
                        prefix + '-' + recipient + 'rechecked')
                for prefix, (account, _screens) in ENTRIES.items()
                for recipient in ({'parent': 'recipient-', 'child': 'child-recipient-',
                                    'other-child': 'standard-recipient-'}[account],)},
    kiosk_request=('other-child', 'parent', 75, True),
)
# The pattern stays in A's directory. S's Versioned subdirectory remains
# outside it, so the same retained nonmatching activity proves isolation.
PATTERN_PLAN = replace(
    PLAN, worker_mode='app_rule_changes_pattern_case',
    screen_tags={stage: tag.replace('ui:text-match-precise-',
                                    'ui:text-match-wildcard-appimages-')
                 for stage, tag in SCREENS.items()},
    match_checks={stage: (app, MATCH_RULES[2] if app == MATCH_APPS['A'] else rule)
                  for stage, (app, rule) in MATCHES.items()},
)


def limits_off_plan(base=PLAN):
    """Reuse the six rounds, preparing Soft→Hard through a real approval."""
    additions = {
        'saved-settings': {
            'limits-off-page': 'ui:discovery-ready',
            'limits-off-save': 'ui:parent-toggle-disabled',
            'limits-off-settings': 'ui:discovery-ready',
        },
        'allowed-soft-parent-desktop': {
            'soft-opening-settings': 'ui:discovery-ready',
            'soft-opening-enable': 'ui:parent-toggle-enabled',
            'soft-opening-enabled': 'ui:discovery-ready',
        },
        'soft-hard-save-parent-desktop': {
            'soft-opening-disable-page': 'ui:discovery-ready',
            'soft-opening-disable': 'ui:parent-toggle-disabled',
        },
    }
    extra_entries = {}
    for prefix, account, source_account in (
            ('soft-opening-disabled-child', 'other-child', 'parent'),
            ('soft-opening-disabled-parent', 'parent', 'other-child')):
        screens = desktop_entry(account, source='desktop', entry='retained',
                                source_account=source_account)
        extra_entries[prefix] = (account, screens)
        additions['soft-hard-save-parent-desktop'].update(prefixed_stages(prefix, screens))
        if account == 'other-child':
            additions['soft-hard-save-parent-desktop']['soft-opening-preserved'] = 'ui:native-policy-activity'
    screens = {}
    phases = dict(base.phases)
    for stage, tag in base.screen_tags.items():
        screens[stage] = tag
        screens.update(additions.get(stage, {}))
        phases.update({extra: base.phases[stage] for extra in additions.get(stage, {})})
    extra_login = {prefix + '-' + stage for prefix, (_account, group) in extra_entries.items()
                   for stage in group if stage in {
                       'installed-greeter', 'parent-focused', 'child-focused', 'standard-focused',
                       'recipient-qualified', 'recipient-rechecked', 'child-recipient-qualified',
                       'child-recipient-rechecked', 'standard-recipient-qualified',
                       'standard-recipient-rechecked', 'desktop'}}
    settings = dict(base.settings_checks)
    for stage in ('limits-off-settings', 'soft-opening-settings', 'final-child-parent-selected',
                  *(name + '-settings' for name, _access in ROUNDS)):
        settings[stage] = SettingsObservation('existing-fixture-child', False, ('30 minutes',))
    for stage in ('limits-off-page', 'soft-opening-enabled', 'soft-opening-disable-page'):
        settings[stage] = SettingsObservation('existing-fixture-child', True, ('30 minutes',))
    return replace(
        base, worker_mode='app_rule_changes_disabled_case', screen_tags=screens, phases=phases,
        settings_checks=settings,
        child_bindings={stage: 'existing' for stage, tag in screens.items()
                        if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
        invocations=tuple(stage for stage in screens if stage in LOGIN_STAGES | extra_login),
        challenges={**base.challenges,
            **{prefix: (account, prefix + '-' + role + '-qualified', prefix + '-' + role + '-rechecked')
               for prefix, (account, _group) in extra_entries.items()
               for role in ({'parent': 'recipient', 'other-child': 'standard-recipient'}[account],)}},
        activity_checks={**ACTIVITIES, 'soft-opening-preserved': ('soft-hard-opening-capture', 'same')},
        activity_entries={**ACTIVITY_ENTRIES,
            'soft-opening-disabled-child-source-desktop': 'allowed-soft-nonmatching-new-capture',
            'soft-opening-disabled-parent-source-desktop': 'soft-hard-opening-capture'},
    )


DISABLED_PLAN = limits_off_plan()
DISABLED_PATTERN_PLAN = replace(limits_off_plan(PATTERN_PLAN),
                                worker_mode='app_rule_changes_disabled_pattern_case')


class AppRuleChangesJourney(RetainedDesktopJourney, NativePolicyJourney, KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
                         parent_expected={}, parent_checks={}, window_checks={},
                         session_checks={**SESSION_CHECKS, **({
                             'soft-opening-disabled-child-entry-guard': 'jordan-session',
                         } if 'soft-opening-preserved' in plan.activity_checks else {})})

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed, 1800)
        if stage == 'soft-opening-balance':
            value = observed['ui']['time_explanation']
            require(value['child'] == 'existing-fixture-child'
                    and value['daily']['seconds'] - value['daily']['precision_seconds'] >= 900,
                    'app-transitions:soft-opening-daily-margin')
            observed.setdefault('comparison', {})['soft_opening_daily_margin'] = True


def execute(recorder, context, *, plan=PLAN, binding='enabled-precise'):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-006/' + binding
    # Six ordered saves, retained visits for both children and final Parent
    # reopening need transport/authentication headroom beyond thirty minutes.
    # This is one worker deadline; individual product observations stay bounded.
    record_installed_journey(recorder, context, plan, timeout=3600,
                             journey_type=AppRuleChangesJourney)


def execute_pattern(recorder, context):
    execute(recorder, context, plan=PATTERN_PLAN, binding='enabled-pattern')


def execute_disabled(recorder, context):
    execute(recorder, context, plan=DISABLED_PLAN, binding='disabled-precise')


def execute_disabled_pattern(recorder, context):
    execute(recorder, context, plan=DISABLED_PATTERN_PLAN, binding='disabled-pattern')


E2E_CASES = {'enabled-precise': execute, 'enabled-pattern': execute_pattern,
             'disabled-precise': execute_disabled, 'disabled-pattern': execute_disabled_pattern}
