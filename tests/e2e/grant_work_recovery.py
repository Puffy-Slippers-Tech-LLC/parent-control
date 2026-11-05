"""Case 23: natural grant exhaustion and recovery without soft-app access."""

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS, countdown_seconds
from countdown import CountdownObservation, CountdownSample, check_countdown_balance
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, grant_only_time_profile,
                            native_activity_entry, native_activity_resume,
                            native_usable_app, prefixed_stages)
from named_app_set import named_app_set
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from policy_edits import AppPolicyJourney
from private_artifacts import require
from request_flow import approval_and_return


APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['H'], 'match-hard-precise', 'permanent'),
        (MATCH_APPS['S'], 'match-soft-wildcard', 'conditional'))
PREPARATION = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                    apps=APPS, prefix='rules'),
    **prefixed_stages('setup-return', desktop_entry('parent', source='gdm', entry='retained')),
    **grant_only_time_profile(source='desktop', entry='same-user', window='retained',
        initial_enabled=False, revoke_first=False, duration_seconds=600,
        request_initial='default', balance_readback=False),
    **prefixed_stages('fresh', desktop_entry('child', source='gdm', entry='fresh')),
    **native_activity_entry('activity', child='child'),
    **prefixed_stages('soft', native_usable_app('command', child='child', role='S')),
    'soft-capture': 'ui:overlay-native-policy-soft-activity',
}
EXHAUSTION = {
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
    **prefixed_stages('denial', desktop_entry('child', source='locked', entry='lock',
                                            expected='time-denied')),
    'return-greeter': 'system:child-return-greeter',
    'denied-returned': 'ui:gdm-returned',
    'retained-before': 'system:child-retained-locked',
}
RECOVERY = {
    **approval_and_return(prefix='new', entry='new', child='fixture-child',
        approver='fixture-parent', duration_seconds=1200, allow_soft=False,
        surface='kiosk', child_entry='retained'),
    'recovery-identity': 'system:child-entry-same',
    **native_activity_resume('resume', child='child'),
    'soft-closed': 'ui:overlay-native-policy-soft-closed',
    'hard-launch': 'ui:overlay-native-hard-command-blocked',
    'soft-launch': 'ui:overlay-native-soft-command-blocked',
    'allowed-work': 'ui:overlay-native-activity',
}
SCREENS = {**PREPARATION, **EXHAUSTION, **RECOVERY}
# FLOW19 owns the initial Parent entry through the single-use functional route.
# Only the later explicit desktop entries use declared invocation challenges.
LOGINS = {'setup-return-': 'parent', 'fresh-': 'child', 'retained-': 'child'}
LOGIN_STAGES = {prefix + stage for prefix, account in LOGINS.items()
                for stage in fresh_desktop(account)}
PLAN = JourneyPlan(
    prefix='grant-work-recovery', worker_mode='grant_work_recovery', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', PREPARATION), ('step-2', EXHAUSTION), ('step-3', RECOVERY))
           for stage in screens}, 'installed-greeter': 'start'},
    advance_after={'soft-capture': 'step-2', 'retained-before': 'step-3'},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    match_checks={f'rules-saved-{role.lower()}-match': (MATCH_APPS[role], rule)
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]),
                                     ('S', MATCH_RULES[4]))},
    access_checks={f'rules-saved-{role.lower()}-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    invocations=tuple(stage for stage, tag in SCREENS.items() if tag.startswith('ui:')
                      and (stage in LOGIN_STAGES or stage in
                           ('natural-expiry', 'lock-input-ready', 'lock-result'))),
    challenges={prefix.rstrip('-'):
        (account, prefix + ('child-' if account == 'child' else '') + 'recipient-qualified',
         prefix + ('child-' if account == 'child' else '') + 'recipient-rechecked')
        for prefix, account in LOGINS.items()},
    activity_entries={'natural-expiry': 'activity-capture',
                      'retained-entry-guard': 'activity-capture'},
    activity_checks={'resume-opened': ('activity-capture', 'same'),
                     'soft-closed': ('soft-capture', 'closed'),
                     'allowed-work': ('activity-capture', 'same')},
    kiosk_request=('child', 'parent', 1200, False),
    assertions_after={'allowed-work': 'visible-result'},
)


class GrantWorkRecoveryJourney(GrantOnlyProfileJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, grant_seconds=600,
            actions=actions if actions is not None else {
                **fixture_actions(include_refusal=False, profile='activity'),
                'natural-expiry': self.natural_expiry})
        self.estimates = {}
        self.initial_countdown = None
        self.natural_expiry_result = None
        self.retained_session = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('profile-request-new-estimate', 'new-estimate'):
            initial = stage.startswith('profile-')
            seconds, soft = (600, True) if initial else (1200, False)
            value = observed['ui']['valid_choice']
            require(value['request']['child'] == 'fixture-child'
                    and value['request']['approver'] == 'fixture-parent'
                    and value['request']['duration_seconds'] == seconds
                    and value['request']['allow_soft'] is soft
                    and value['estimate']['kind'] == 'fixed'
                    and value['estimate']['seconds'] == seconds,
                    'grant-recovery:approval-choices-and-zero-time-estimate')
            require(stage not in self.estimates, 'grant-recovery:replayed-estimate')
            self.estimates[stage] = value
        if stage in ('natural-expiry', 'countdown'):
            initial = stage == 'natural-expiry'
            key = 'profile-request-new-estimate' if initial else 'new-estimate'
            require(key in self.estimates, 'grant-recovery:missing-estimate')
            baseline = self.estimates[key]
            current = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
            require(countdown_seconds(current.text)[0] >= (300 if initial else 600),
                    'grant-recovery:insufficient-time-headroom')
            observed['comparison'] = check_countdown_balance(current,
                seconds=baseline['estimate']['seconds'],
                precision_seconds=baseline['estimate']['precision_seconds'],
                observed_monotonic_ns=baseline['observed_monotonic_ns'], max_elapsed_seconds=300)
            if initial:
                require(self.initial_countdown is None, 'grant-recovery:replayed-expiry')
                self.initial_countdown = CountdownSample.from_ui(
                    observed['ui'], boot_sha256=observed['boot_sha256'])
        if stage == 'retained-before':
            self.retained_session = observed['system']['session_sha256']
        if stage in ('retained-entry-guard', 'recovery-identity'):
            require(self.retained_session is not None
                    and observed['system']['session_sha256'] == self.retained_session,
                    'grant-recovery:retained-session-replaced')

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.natural_expiry_result is None
                and {'activity-capture', 'soft-capture'} <= journey.activity_observations.keys(),
                'grant-recovery:missing-or-replayed-activity')
        result = await_natural_expiry(journey, guard, journey.initial_countdown,
            journey.activity_observations['activity-capture'], maximum_seconds=600)
        journey.natural_expiry_result = result
        return result


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-009/excluded'
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=GrantWorkRecoveryJourney)


E2E_CASES = {'excluded': execute}
