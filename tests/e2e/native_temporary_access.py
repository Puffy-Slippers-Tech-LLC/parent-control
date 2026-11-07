"""Case 231: three approvals replace the child's temporary native app access."""
from accessible_ui import MATCH_APPS, NAMED_CHILD_OPERATIONS, OVERLAY_BOUND_OPERATIONS
from access_choices import AccessChoiceJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            fresh_desktop, native_blocked_app, native_usable_app, prefixed_stages)
from native_fixtures import fixture_actions
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import approval_and_return
from ui_observations import SettingsObservation


ROWS = (('allowed', 'A', 'allowed'), ('hard', 'H', 'permanent'),
        ('soft', 'S', 'conditional'))
REQUESTS = {'first': ('other-child', 'parent', 30, False),
            'included': ('other-child', 'other-parent', 30, True),
            'replacement': ('other-child', 'parent', 30, False)}
SCREENS = app_policy_entry(child='existing', initial_rows=False,
                           allowance='time-explanation-setup-thirty-read')
ACCESS = {}
for name, role, choice in ROWS:
    operation = 'access-' + (name + '-' if role != 'A' else '')
    SCREENS.update({name + '-save': 'ui:' + operation + choice,
                    name + '-row': 'ui:' + operation + 'row'})
    ACCESS[name + '-row'] = (MATCH_APPS[role], choice)
SCREENS.update({
    **desktop_return('leave-parent', account='parent'),
    **prefixed_stages('initial', desktop_entry('other-child', source='gdm', entry='fresh')),
    **prefixed_stages('allowed', native_usable_app('grid')),
    'allowed-capture': 'ui:native-policy-activity',
    **prefixed_stages('initial-hard', native_blocked_app('H', route='grid')),
    **prefixed_stages('initial-soft', native_blocked_app('S', route='grid'))})
STEP2 = len(SCREENS)
ACTIVITIES, COUNTDOWNS, BINDINGS = {}, {}, {}
for name, (_child, approver, seconds, soft) in REQUESTS.items():
    group = {
        'independent-launch': 'ui:child-command-launch',
        **approval_and_return(prefix='open', entry='open', child='existing-fixture-child',
            approver='fixture-parent' if approver == 'parent' else 'other-fixture-parent',
            duration_seconds=seconds, allow_soft=soft, surface='overlay'),
        **({'soft-closed': 'ui:native-policy-soft-closed'} if name == 'replacement' else {}),
        'allowed-preserved': 'ui:native-policy-activity',
        'allowed-submit': 'ui:native-resubmit',
        'allowed-submitted': 'ui:native-submitted',
        'allowed-original': 'ui:native-policy-activity',
        **prefixed_stages('hard', native_blocked_app('H', route='grid')),
        **({**prefixed_stages('soft', native_usable_app('grid', role='S')),
            'soft-capture': 'ui:native-policy-soft-activity'} if soft else
           prefixed_stages('soft', native_blocked_app('S', route='grid'))),
    }
    SCREENS.update(prefixed_stages(name, group))
    BINDINGS.update({name + '-' + stage: REQUESTS[name] for stage, tag in group.items()
                     if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
    ACTIVITIES.update({name + '-' + stage: ('allowed-capture', 'same')
                       for stage in ('allowed-preserved', 'allowed-original')})
    COUNTDOWNS[name + '-countdown'] = (name + '-open-estimate', 'estimate', 1, 300)
ACTIVITIES['replacement-soft-closed'] = ('included-soft-capture', 'closed')
ACTIVITIES['included-soft-capture'] = ('allowed-capture', 'separate')
STEP3 = len(SCREENS)
SCREENS.update({**prefixed_stages('final', desktop_entry('parent', source='desktop', entry='retained',
                                                      source_account='other-child')),
                'final-apps': 'ui:existing-apps'})
for name, role, choice in ROWS:
    SCREENS['final-' + name + '-row'] = 'ui:access-' + (name + '-' if role != 'A' else '') + 'row'
    ACCESS['final-' + name + '-row'] = (MATCH_APPS[role], choice)
LOGINS = {'initial': ('other-child', 'initial-'), 'final': ('parent', 'final-')}
LOGIN_STAGES = {prefix + stage for account, prefix in LOGINS.values() for stage in fresh_desktop(account)}
PLAN = JourneyPlan(
    prefix='native-grid-temporary-access', worker_mode='native_grid_temporary_access',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < STEP2 else 'step-2' if index < STEP3 else 'step-3'
               for index, stage in enumerate(SCREENS)}, 'installed-greeter': 'start'},
    advance_after={'initial-soft-denied': 'step-2', 'replacement-soft-denied': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800}, access_checks=ACCESS,
    overlay_request=REQUESTS['first'], overlay_requests=BINDINGS,
    countdown_checks=COUNTDOWNS, activity_checks=ACTIVITIES,
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={name: (account, prefix + ('recipient-qualified' if account == 'parent'
                                        else 'standard-recipient-qualified'),
                      prefix + ('recipient-rechecked' if account == 'parent'
                                else 'standard-recipient-rechecked'))
                for name, (account, prefix) in LOGINS.items()},
    assertions_after={'final-soft-row': 'visible-result'},
)


class TemporaryAccessJourney(KioskRequestJourney, AccessChoiceJourney):
    def check_estimate(self, observed):
        # Each request's current public estimate accounts for earlier grants/use.
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is not None:
            require(choice['request']['child'] == 'existing-fixture-child'
                    and choice['request']['duration_seconds'] == 30
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] >= 900,
                    'temporary-access:request-margin')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=TemporaryAccessJourney)


E2E_CASES = {'native-grid-child-overlay': execute}
