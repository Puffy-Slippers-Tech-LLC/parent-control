"""Case 246: three station approvals replace Jordan's temporary app access."""
from accessible_ui import FLATPAK_POLICY_APPS, KIOSK_BOUND_OPERATIONS, NAMED_CHILD_OPERATIONS
from flatpak_fixtures import fixture_actions
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            fresh_desktop, native_usable_app, prefixed_stages, station_entry)
from private_artifacts import require
from request_composition import KioskRequestJourney
from access_choices import AccessChoiceJourney
from request_flow import approval_and_return
from ui_observations import SettingsObservation, compare_app_activity


ROWS = (('allowed', 'A', 'allowed'), ('hard', 'H', 'permanent'),
        ('soft', 'S', 'conditional'))
REQUESTS = {'first': ('other-child', 'parent', 30, False),
            'included': ('other-child', 'other-parent', 30, True),
            'replacement': ('other-child', 'parent', 30, False)}
SCREENS = app_policy_entry(child='existing', initial_rows=False,
                          allowance='time-explanation-setup-thirty-read')
ACCESS = {}
for name, role, access in ROWS:
    operation = 'access-flatpak-' + (name + '-' if role != 'A' else '')
    SCREENS.update({name + '-save': 'ui:' + operation + access,
                    name + '-row': 'ui:' + operation + 'row'})
    ACCESS[name + '-row'] = (FLATPAK_POLICY_APPS[role], access)
SCREENS.update(desktop_return('leave-parent', account='parent'))
INITIAL = prefixed_stages('initial', desktop_entry('other-child', source='gdm', entry='fresh'))
SCREENS.update({**INITIAL,
    **prefixed_stages('allowed', native_usable_app('command', role='A', kind='flatpak')),
    'allowed-capture': 'ui:flatpak-allowed-policy-activity',
    'initial-hard-denied': 'ui:flatpak-hard-command-blocked',
    'initial-soft-denied': 'ui:flatpak-soft-command-blocked'})
ACTIVITIES = {}
ENTRIES = {}
COUNTDOWNS = {}
BINDINGS = {}
for name, (_child, approver, seconds, soft) in REQUESTS.items():
    group = {
        **desktop_return('leave-child', account='other-child'),
        **station_entry(),
        **approval_and_return(prefix='open', entry='open', child='existing-fixture-child',
            approver='fixture-parent' if approver == 'parent' else 'other-fixture-parent',
            duration_seconds=seconds, allow_soft=soft, surface='kiosk', child_entry='retained'),
        **({'soft-closed': 'ui:flatpak-soft-policy-closed'} if name == 'replacement' else {}),
        'allowed-preserved': 'ui:flatpak-allowed-policy-activity',
        'allowed-submit': 'ui:flatpak-allowed-resubmit',
        'allowed-submitted': 'ui:flatpak-allowed-submitted',
        'allowed-original': 'ui:flatpak-allowed-policy-activity',
        'hard-denied': 'ui:flatpak-hard-command-blocked',
        **({**prefixed_stages('soft', native_usable_app('command', role='S', kind='flatpak')),
            'soft-capture': 'ui:flatpak-soft-policy-activity'} if soft else
           {'soft-denied': 'ui:flatpak-soft-command-blocked'}),
    }
    SCREENS.update(prefixed_stages(name, group))
    BINDINGS.update({name + '-' + stage: REQUESTS[name] for stage, tag in group.items()
                     if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS})
    ACTIVITIES.update({name + '-' + stage: ('allowed-capture', 'same')
                       for stage in ('allowed-preserved', 'allowed-original')})
    ENTRIES[name + '-retained-entry-guard'] = 'allowed-capture'
    COUNTDOWNS[name + '-countdown'] = (name + '-open-estimate', 'estimate', 1, 300)
ACTIVITIES['replacement-soft-closed'] = ('included-soft-capture', 'closed')
FINAL = prefixed_stages('final', desktop_entry('parent', source='desktop', entry='retained',
                                             source_account='other-child'))
SCREENS.update({**FINAL, 'final-apps': 'ui:existing-apps'})
for name, role, access in ROWS:
    SCREENS['final-' + name + '-row'] = 'ui:access-flatpak-' + (name + '-' if role != 'A' else '') + 'row'
    ACCESS['final-' + name + '-row'] = (FLATPAK_POLICY_APPS[role], access)
LOGINS = {'initial': ('other-child', 'initial-'), 'final': ('parent', 'final-'),
          **{name + '-retained': ('other-child', name + '-retained-') for name in REQUESTS}}
LOGIN_STAGES = {prefix + stage for account, prefix in LOGINS.values() for stage in fresh_desktop(account)}
STEP2 = tuple(SCREENS).index('first-leave-child-desktop')
STEP3 = tuple(SCREENS).index('final-source-desktop')
PLAN = JourneyPlan(
    prefix='flatpak-temporary-access', worker_mode='flatpak_temporary_access', screen_tags=SCREENS,
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
    kiosk_request=REQUESTS['first'], kiosk_requests=BINDINGS,
    countdown_checks=COUNTDOWNS, activity_checks=ACTIVITIES, activity_entries=ENTRIES,
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
        # These requests follow real child use and, later, a running grant.
        # Compare the resulting countdown with each freshly read estimate;
        # the initial unused-child Parent balance is no longer the operand.
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is not None:
            require(choice['request']['child'] == 'existing-fixture-child'
                    and choice['request']['duration_seconds'] == 30
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] >= 300,
                    'temporary-access:request-margin')

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if stage == 'included-soft-capture':
            observed['comparison'] = compare_app_activity(
                self.activity_observations[stage], self.activity_observations['allowed-capture'],
                result='separate')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=TemporaryAccessJourney)


E2E_CASES = {'flatpak-command-kiosk': execute}
