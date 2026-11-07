"""Case 194: both local approval screens and revocation in one offline lifetime."""
from copy import deepcopy

from access_choices import AccessChoiceJourney
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from countdown import CountdownSample, await_countdown_progress, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop, native_usable_app,
                            parent_management, prefixed_stages, retained_parent_entry)
from journey_checks import require_zero_grant
from named_app_set import APPS, named_app_set
from native_fixtures import fixture_actions
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import approval_and_return
from vm_internet import InternetIsolation, restore
from vm_internet_qualification import internet_result
from watch_activity import operation


CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=180, allow_soft=True)
PREPARATION = {
    **fresh_desktop('parent'), **parent_management(),
    'offline-enter': 'ui:parent-window',
    'allowance': 'ui:time-explanation-setup-thirty-read',
    **named_app_set(source='desktop', entry='same-user', window='retained',
                    child='child', apps=APPS, prefix='rules'),
}


def app_results(prefix, *, retained):
    screens = prefixed_stages(prefix + '-allowed', native_usable_app(
        'command', child='child', role='A', desktop_observation=False))
    if retained:
        screens[prefix + '-allowed-capture'] = 'ui:overlay-native-activity'
    else:
        screens.update({prefix + '-allowed-close': 'ui:overlay-native-allowed-close',
                        prefix + '-allowed-closed': 'ui:overlay-native-allowed-closed'})
    # H and S share the secondary fixture slot. Check H before opening S.
    screens[prefix + '-hard-denied'] = 'ui:overlay-native-hard-command-blocked'
    screens.update(prefixed_stages(prefix + '-soft', native_usable_app(
        'command', child='child', role='S', desktop_observation=False)))
    if retained:
        screens[prefix + '-soft-capture'] = 'ui:overlay-native-policy-soft-activity'
    else:
        screens.update({prefix + '-soft-close': 'ui:overlay-native-soft-close',
                        prefix + '-soft-closed': 'ui:overlay-native-soft-closed'})
    return screens


OVERLAY = {
    **prefixed_stages('child', desktop_entry('child', source='gdm', entry='fresh')),
    'before-countdown': 'ui:child-countdown-present',
    'overlay-launch': 'ui:child-command-launch',
    **prefixed_stages('overlay', approval_and_return(prefix='open', entry='open', **CHOICES)),
    **app_results('first', retained=False),
}
STATION = {
    **desktop_return('logout', account='child', action='logout'),
    **prefixed_stages('station', approval_and_return(prefix='open', entry='new',
        surface='kiosk', child_entry='fresh', **CHOICES)),
    **app_results('second', retained=True),
}
REVOCATION = {
    **prefixed_stages('parent-return', desktop_entry('parent', source='desktop',
        entry='retained', source_account='child')),
    **prefixed_stages('supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'before-revoke': 'ui:revoke-saved-balances',
    'revoke-open': 'ui:revoke-open', 'revoke-confirm': 'ui:revoke-confirm',
    'after-revoke': 'ui:revoke-cleared-balances',
    **prefixed_stages('child-return', desktop_entry('child', source='desktop',
        entry='retained', source_account='parent')),
    'soft-closed': 'ui:overlay-native-policy-soft-closed',
    'allowed-retained': 'ui:overlay-native-activity',
    'allowed-submit': 'ui:overlay-native-resubmit',
    'allowed-submitted': 'ui:overlay-native-submitted',
    'soft-denied': 'ui:overlay-native-soft-command-blocked',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'offline-restore': 'ui:fresh-child-desktop',
}
SCREENS = {**PREPARATION, **OVERLAY, **STATION, **REVOCATION}
LOGINS = {'': ('parent', 'parent-login'), 'child-': ('child', 'child'),
          'station-fresh-': ('child', 'station-fresh'),
          'parent-return-': ('parent', 'parent-return'),
          'child-return-': ('child', 'child-return')}
LOGIN_STAGES = {prefix + stage for prefix, (role, _identity) in LOGINS.items()
                for stage in fresh_desktop(role)}
PLAN = JourneyPlan(
    prefix='offline-approvals', worker_mode='offline_approvals', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for group, phase in ((PREPARATION, 'step-1'), (OVERLAY, 'step-2'),
                (STATION, 'step-3'), (REVOCATION, 'step-4')) for stage in group},
            'installed-greeter': 'start'},
    advance_after={'installed-greeter': 'step-1', 'rules-gdm-switched': 'step-2',
                   'first-soft-closed': 'step-3', 'second-soft-capture': 'step-4'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={identity: (role, prefix + ('recipient-qualified' if role == 'parent'
                                         else 'child-recipient-qualified'),
                          prefix + ('recipient-rechecked' if role == 'parent'
                                    else 'child-recipient-rechecked'))
                for prefix, (role, identity) in LOGINS.items()},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    stage_actions={'desktop': 'native-verify', 'offline-enter': 'offline',
                   'overlay-countdown': 'ticks', 'station-countdown': 'ticks',
                   'offline-restore': 'online'},
    balance_checks={'allowance': 1800},
    match_checks={'rules-saved-' + role.lower() + '-match': (MATCH_APPS[role], rule)
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]), ('S', MATCH_RULES[4]))},
    access_checks={'rules-saved-' + role.lower() + '-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    overlay_request=('child', 'parent', 180, True), kiosk_request=('child', 'parent', 180, True),
    activity_checks={'soft-closed': ('second-soft-capture', 'closed'),
                     'allowed-retained': ('second-allowed-capture', 'same')},
    assertions_after={'first-soft-closed': 'overlay-result',
                      'second-soft-capture': 'kiosk-result', 'hard-denied': 'visible-result'},
)


def offline(journey, guard):
    with operation('Removing Internet access before local policy and approvals'):
        guard()
        require(not hasattr(journey, 'online_before'), 'offline-approvals:isolation-replay')
        journey.online_before = internet_result(journey.transport)
        require(any(probe['reachable'] for probe in journey.online_before['probes']),
                'offline-approvals:online-entry')
        InternetIsolation(journey.context.lease).enter(journey.transport)
        guard()
        result = internet_result(journey.transport)
        require(result['ipv6_default_route'] == journey.online_before['ipv6_default_route']
                and not any(probe['reachable'] for probe in result['probes']),
                'offline-approvals:offline-entry')
        return {'before': journey.online_before, 'offline': result}


def online(journey, guard):
    with operation('Restoring Internet after the final child app results'):
        guard()
        result = internet_result(journey.transport)
        require(not any(probe['reachable'] for probe in result['probes']),
                'offline-approvals:offline-through-final-result')
        restore(journey.context.lease)
        guard()
        after = internet_result(journey.transport)
        require(after['ipv6_default_route'] == journey.online_before['ipv6_default_route']
                and all(not before['reachable'] or current['reachable'] for before, current in
                    zip(journey.online_before['probes'], after['probes'], strict=True)),
                'offline-approvals:online-recovery')
        return {'offline_final': result, 'online_after': after}


def ticks(journey, guard):
    before = journey.latest_countdown
    current, result = await_countdown_progress(journey, guard, before,
        precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=180)
    journey.latest_countdown = current
    return result


class OfflineApprovalsJourney(KioskRequestJourney, AccessChoiceJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.estimates = {}
        self.latest_countdown = None
        self.saved_policy = None

    def check_estimate(self, observed):
        # The second approval extends the still-running first result. A normal
        # logout does not reset that public balance, unlike fresh qualifier data.
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is None:
            return
        require(choice['request']['child'] == CHOICES['child']
                and choice['estimate']['kind'] == 'fixed', 'offline-approvals:estimate-child')
        if self.latest_countdown is None:
            return super().check_estimate(observed)
        earlier = self.latest_countdown.countdown
        elapsed = (choice['observed_monotonic_ns'] - earlier.observed_monotonic_ns) / 1e9
        require(0 <= elapsed <= 600
                and earlier.seconds + 180 - elapsed - 2 <= choice['estimate']['seconds']
                <= earlier.seconds + 180 + 2, 'offline-approvals:estimate-increment')

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        value = observed.get('ui', {})
        if stage == 'allowance':
            require_zero_grant(value['time_explanation'])
            require(value['time_explanation']['daily']['seconds'] >= 900,
                    'offline-approvals:daily-margin')
        if stage in ('overlay-open-estimate', 'station-open-estimate'):
            self.estimates[stage.split('-')[0]] = deepcopy(value['valid_choice'])
        if stage in ('before-countdown', 'overlay-countdown', 'station-countdown'):
            current = CountdownSample.from_ui(value, boot_sha256=self.ui.boot_proof)
            if stage != 'before-countdown':
                estimate = self.estimates[stage.split('-')[0]]
                comparison = check_countdown_balance(current.countdown,
                    seconds=estimate['estimate']['seconds'], precision_seconds=1,
                    observed_monotonic_ns=estimate['observed_monotonic_ns'],
                    max_elapsed_seconds=300, sampling_seconds=0)
                earlier = self.latest_countdown.countdown
                elapsed = (current.countdown.observed_monotonic_ns - earlier.observed_monotonic_ns) / 1e9
                require(0 < elapsed <= 600 and abs(current.countdown.seconds
                    - (earlier.seconds + 180 - elapsed)) <= 2,
                    'offline-approvals:added-time')
                observed.setdefault('comparison', {}).update(comparison, added_seconds=180)
            self.latest_countdown = current
        if stage in ('before-revoke', 'after-revoke'):
            policy = value['revoke_cancel']
            balances = policy['balances']
            require(policy['settings'] == {'child': CHOICES['child'], 'limit_enabled': True,
                    'allowance': ['30 minutes']} and balances['daily']['seconds'] > 0,
                    'offline-approvals:daily-preserved')
            if stage == 'before-revoke':
                require(balances['one_time']['seconds'] > 0, 'offline-approvals:grant-before-revoke')
                self.saved_policy = deepcopy(policy)
            else:
                require_zero_grant(balances)
                require(all(policy[key] == self.saved_policy[key] for key in ('settings', 'apps', 'rules')),
                        'offline-approvals:policy-preserved')


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-043/both-surfaces'
    record_installed_journey(recorder, context, PLAN, timeout=3600,
        journey_type=OfflineApprovalsJourney,
        actions={**fixture_actions(include_refusal=False), 'offline': offline, 'online': online, 'ticks': ticks})


E2E_CASES = {'both-surfaces': execute}
